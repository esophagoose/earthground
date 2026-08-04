import logging
from types import MappingProxyType
from typing import Dict, Iterator, List, Mapping, Optional, Union

import earthground.components as cmp
import earthground.erc as erc
from earthground.erc import ElectricalCheck, ElectricalReport
import earthground.footprints.passives as passives
import earthground.layout as layout_lib
import earthground.standard_values as sv
import earthground.straps as straps
import earthground.thermal as thermal
import earthground.contracts as contracts
import earthground.sourcing as sourcing
import earthground.signal_integrity as signal_integrity
from earthground.analysis import DesignAnalysis
from earthground.signal_integrity import DiffPair, NetClass

log = logging.getLogger(__name__)


class SchematicError(Exception):
    pass


class SchematicValidationError(SchematicError):
    def __init__(self, design_name: str, errors: List[str]):
        self.design_name = design_name
        self.errors = list(errors)
        super().__init__(
            f"Validation failed for {design_name}: " + "; ".join(self.errors)
        )


class SchematicConnectionError(SchematicError):
    def __init__(self, message: str):
        self.message = f"Schematic connection error: {message}"
        super().__init__(self.message)


class Ports:
    """
    Ports are the interface between modules and their parent.
    Structurally, they present a module as a singular component with the ports being the pins
    """

    def __init__(self, ports: List[str], parent: "Design"):
        self.names = ports
        self.symbol = cmp.ModuleComponent(parent.short_name)
        self.symbol.virtual = True
        self.symbol.name = parent.name
        self.symbol.pins = cmp.PinContainer.from_list(ports, self)
        self.parent = parent
        for name in ports:
            setattr(self, name, self.symbol.pins.by_name(name))

    def __getitem__(self, port) -> cmp.Pin:
        if port not in self.names:
            raise ValueError(f"Unknown port: {port}. Options {self.names}")
        return getattr(self, port)

    def __setitem__(self, port, value) -> None:
        raise RuntimeError("Can't direct set ports! Connect in schematic")

    def __str__(self):
        return f"SchematicPorts<{self.parent.name}>"


class Design:
    def __init__(self, name, short_name=None, ports=[]):
        """
        A design is equivalent to a schematic page. Its function is to hold the relationships
        between objects in the design, such as components and other designs.

        :param name: The name of the design, serving as the schematic title.
        :type name: str
        :param short_name: Short name for the design used as a refdes prefix, optional.
        :type short_name: str, optional
        :param ports: List of port names for connecting this design in other designs, optional.
        :type ports: List[str], optional
        """
        self.name = name
        self.short_name = short_name
        if not short_name:
            self.short_name = self.name
        self._net_scope = self.short_name
        self.components: Dict[str, cmp.Component] = {}
        self.modules: List[Design] = []
        self._nets: Dict[str, cmp.Net] = {}
        self._pin_to_net: Dict[cmp.Pin, cmp.Net] = {}
        self._nets_view = MappingProxyType(self._nets)
        self._pin_to_net_view = MappingProxyType(self._pin_to_net)
        self.busses = {}
        self.default_passive_size = "0603"
        self.port = Ports(ports, self)
        self.ground = self.add_net("GND").name
        self.layout: layout_lib.Layout = layout_lib.Layout(self)
        self._ports = ports
        self._module_names: Dict[str, int] = {}
        self._cid_map: Dict[str, int] = {}
        self._declared_rails: Dict[str, sv.ValueBounds] = {}
        self._external_drives: Dict[str, Optional[sv.ValueBounds]] = {}
        self._ambient: Optional[sv.ValueBounds] = None
        self._strap_expectations: Dict[
            tuple[cmp.Component, str], straps.StrapExpectation
        ] = {}
        self._contract_waivers: Dict[tuple[cmp.Component, str], str] = {}
        self._net_classes: Dict[str, NetClass] = {}
        self._diff_pairs: list[DiffPair] = []
        self._sourcing_resolvers: list[sourcing.SourcingResolver] = []
        self._ambient_deferred_reason: Optional[str] = None

    def declare_net_class(self, net_class: NetClass) -> None:
        if not isinstance(net_class, NetClass):
            raise TypeError("declare_net_class() requires a NetClass")
        if net_class.name in self._net_classes:
            raise ValueError(f"Net class {net_class.name!r} is already declared")
        self._net_classes[net_class.name] = net_class

    def declare_diff_pair(self, pair: DiffPair) -> None:
        if not isinstance(pair, DiffPair):
            raise TypeError("declare_diff_pair() requires a DiffPair")
        if any(set(existing.nets) == set(pair.nets) for existing in self._diff_pairs):
            raise ValueError(f"Differential pair {pair.nets!r} is already declared")
        self._diff_pairs.append(pair)

    def declare_rail(self, name: str, voltage: sv.ValueBounds) -> None:
        sv.require_bounds(voltage, "V", "Rail voltage")
        if name == self.ground and voltage != sv.volts(0, typ=0, max=0):
            raise ValueError("GND is an implicit exact 0 V rail")
        self._declared_rails[name] = voltage

    def declare_external_drive(
        self, name: str, voltage: Optional[sv.ValueBounds] = None
    ) -> None:
        if voltage is not None:
            sv.require_bounds(voltage, "V", "External-drive voltage")
        self._external_drives[name] = voltage

    def declare_ambient(self, temperature: sv.ValueBounds) -> None:
        sv.require_bounds(temperature, "°C", "Ambient temperature")
        self._ambient = temperature
        self._ambient_deferred_reason = None

    def defer_ambient(self, reason: str) -> None:
        if not reason:
            raise ValueError("Ambient deferral requires a reason")
        self._ambient = None
        self._ambient_deferred_reason = reason

    def register_sourcing_resolver(self, resolver: sourcing.SourcingResolver) -> None:
        if not callable(resolver) and not callable(getattr(resolver, "resolve", None)):
            raise TypeError("Sourcing resolver must be callable or define resolve()")
        self._sourcing_resolvers.append(resolver)

    def expect_strap(
        self,
        component: cmp.Component,
        strap_id: str,
        level: str,
        reason: str,
    ) -> None:
        if component.parent is not self:
            raise ValueError("Strap expectation component must belong to this design")
        straps_by_id = {strap.id: strap for strap in component.strap_pins}
        if strap_id not in straps_by_id:
            raise ValueError(f"Unknown strap {strap_id!r} on {component}")
        if level not in {item.name for item in straps_by_id[strap_id].levels}:
            raise ValueError(f"Unknown level {level!r} for strap {strap_id!r}")
        if not reason:
            raise ValueError("Strap expectation requires a reason")
        self._strap_expectations[(component, strap_id)] = straps.StrapExpectation(
            level, reason
        )

    def check_straps(self) -> straps.StrapReport:
        return straps.check_design(self)

    def thermal_report(self) -> thermal.ThermalReport:
        return thermal.build_report(self)

    def waive_contract(
        self, component: cmp.Component, check_id: str, reason: str
    ) -> None:
        if component.parent is not self:
            raise ValueError("Contract waiver component must belong to this design")
        if not check_id:
            raise ValueError("Contract waiver requires a check id")
        if not reason:
            raise ValueError("Contract waiver requires a reason")
        self._contract_waivers[(component, check_id)] = reason

    def check_contracts(self) -> contracts.ContractReport:
        return contracts.check_design(self)

    @property
    def nets(self) -> Mapping[str, cmp.Net]:
        """Read-only net registry; mutate it through Design's net APIs."""
        return self._nets_view

    @property
    def pin_to_net(self) -> Mapping[cmp.Pin, cmp.Net]:
        """Read-only pin registry; mutate it through Design's net APIs."""
        return self._pin_to_net_view

    def scoped_net_name(self, raw_name: str) -> str:
        """
        Return the scoped net name for this design.

        - Global nets like GND are left unchanged.
        - Names already prefixed with this design's net scope are left unchanged.
        - All other names are prefixed with the design's net scope.
        """
        if raw_name == self.ground:
            return raw_name
        prefix = f"{self._net_scope}_"
        if raw_name.startswith(prefix):
            return raw_name
        return f"{prefix}{raw_name}"

    def add_module(self, module: "Design"):
        """
        Adds a module (sub-design) to the current design.

        This method allows for hierarchical designs by adding a module (another Design instance) as a sub-design
        to the current design. It automatically prefixes the module's short name with a unique identifier based
        on the number of times this module's short name has been used. This ensures that net names within the module
        are unique when integrated into the larger design. It also updates the net names within the module to reflect
        this new unique prefix.

        :param module: The module to be added as a sub-design.
        :type module: Design
        :raises ValueError: If the provided module is not an instance of Design.
        :return: The module that was added; with updated short name and net names.
        :rtype: Design
        """
        if not isinstance(module, Design):
            raise ValueError("Invalid module! Must be schematic.Design type")
        if module.short_name not in self._module_names:
            self._module_names[module.short_name] = 0
        self._module_names[module.short_name] += 1
        old_short_name = module.short_name
        # Assign a unique, stable short_name for this module instance
        module.short_name = f"{old_short_name}{self._module_names[old_short_name]}"
        if self.port.symbol.is_in_design:
            module._update_net_scope(f"{self._net_scope}_{module.short_name}")
        else:
            module._update_net_scope(module.short_name)
        # Ensure all existing module nets are scoped with the module's net scope
        module._enforce_scoped_net_names()
        if self.default_passive_size:
            for component in module.components.values():
                if isinstance(component, cmp.PASSIVE_TYPES):
                    self.set_passive_footprint(component)
        self.modules.append(module)
        self.add_component(module.port.symbol)
        # Restore the symbol's parent to the module, since it logically belongs to the module
        # even though it's placed in the parent design
        module.port.symbol.parent = module
        return module

    def add_component(self, component: cmp.Component) -> cmp.Component:
        """
        Adds a component to the current design

        :param component: The component to be added to the design.
        :type component: Component
        :return: The component that was added, with updated footprint if applicable.
        :rtype: Component
        """
        log.debug(f"Adding component {component}")
        if isinstance(component, cmp.PASSIVE_TYPES):
            self.set_passive_footprint(component)

        if not component.is_in_design:
            self._cid_map[component.refdes_prefix] = (
                self._cid_map.get(component.refdes_prefix, 0) + 1
            )
            cid = component.refdes_prefix + str(self._cid_map[component.refdes_prefix])
            self.components[cid] = component
            component.place(self)
            return component
        raise ValueError(f"Component is already in the design! {component}")

    def add_net(self, name: str) -> cmp.Net:
        """
        Creates a net in the design and returns it.

        :param name: The name of the net to be created.
        :type name: str
        :return: The newly created net.
        :rtype: earthground.components.Net
        """
        name = cmp.validate_net_name(name, owner="add_net()", argument="name")
        if name in self.nets:
            raise ValueError(f"add_net() net '{name}' already exists")
        net = cmp.Net(name)
        self._nets[name] = net
        return net

    def _add_to_net(self, pin: cmp.Pin, net: cmp.Net):
        if pin in self.pin_to_net:
            old_net = self.pin_to_net[pin]
            if old_net == net:
                return
            return self.change_net_name(old_net.name, net.name)
        self.nets[net.name].connections.add(pin)
        self._pin_to_net[pin] = net

    def _sync_child_port_net(
        self, pin: cmp.Pin, net_name: str, include_self: bool = False
    ) -> None:
        if not isinstance(pin.parent, Ports):
            return
        module_design: Design = pin.parent.parent
        if not include_self and module_design is self:
            return
        if pin in module_design.pin_to_net:
            module_design.change_net_name(module_design.pin_to_net[pin].name, net_name)

    def _get_net_name_from_pin(self, pin: cmp.Pin) -> str:
        if pin in self.pin_to_net:
            return self.pin_to_net[pin].name
        return f"AutoNet_{pin.name}"

    def _pin_belongs_to_design(self, pin: cmp.Pin) -> bool:
        if isinstance(pin.parent, Ports):
            port_design = pin.parent.parent
            if port_design is self:
                return True
            return any(module is port_design for module in self.modules)
        if not isinstance(pin.parent, cmp.Component):
            return False
        return pin.parent.parent is self and any(
            component is pin.parent for component in self.components.values()
        )

    def _validate_pin(self, pin: object, owner: str) -> None:
        if not isinstance(pin, cmp.Pin):
            raise TypeError(
                f"{owner} argument 'pin' must be a Pin, got {type(pin).__name__}"
            )
        if not self._pin_belongs_to_design(pin):
            raise SchematicConnectionError(
                f"{owner} pin does not belong to design '{self.name}': {pin}"
            )

    def _validate_connection_arguments(
        self,
        owner: str,
        pins=(),
        net_names=(),
    ) -> None:
        for pin in pins:
            self._validate_pin(pin, owner)
        for net_name in net_names:
            cmp.validate_net_name(net_name, owner=owner)

    def join_net(self, pin: cmp.Pin, net_name: str) -> cmp.Net:
        """
        Joins a pin to a specified net by its name. If the net does not exist, it is created.

        :param pin: The pin that needs to be joined to the net.
        :type pin: earthground.components.Pin
        :param net_name: The name of the net to which the pin will be joined.
        :type net_name: str
        :raises TypeError: If ``pin`` is not a Pin or ``net_name`` is not a string.
        :return: The net to which the pin was successfully joined.
        :rtype: earthground.components.Net
        """
        self._validate_connection_arguments("join_net()", [pin], [net_name])

        # If the pin is a port, then the net inside the module should be changed
        self._sync_child_port_net(pin, net_name, include_self=True)
        if net_name not in self.nets:
            self._nets[net_name] = cmp.Net(net_name)
        net = self.nets[net_name]
        self._add_to_net(pin, net)
        return self.nets[net_name]

    def change_net_name(self, old_net_name: str, new_net_name: str) -> None:
        """
        Renames an existing net in a design

        :param old_net_name: The current name of the net to be renamed.
        :type old_net_name: str
        :param new_net_name: The new name for the net.
        :type new_net_name: str
        :return: None
        """
        cmp.validate_net_names(
            "change_net_name()",
            old_net_name=old_net_name,
            new_net_name=new_net_name,
        )
        log.debug(f"Changing net name from {old_net_name} to {new_net_name}")
        if old_net_name not in self.nets:
            raise KeyError(f"Net '{old_net_name}' does not exist in design")
        if old_net_name == new_net_name:
            return
        old_net_connections = list(self.nets[old_net_name].connections)
        if new_net_name in self.nets:
            self.merge_nets(old_net_name, new_net_name)
        else:
            self._nets[new_net_name] = self._nets.pop(old_net_name)
            self._nets[new_net_name].name = new_net_name
        for pin in old_net_connections:
            self._sync_child_port_net(pin, new_net_name)
        if old_net_name in self._declared_rails:
            self._declared_rails[new_net_name] = self._declared_rails.pop(old_net_name)
        if old_net_name in self._external_drives:
            self._external_drives[new_net_name] = self._external_drives.pop(
                old_net_name
            )

    def _enforce_scoped_net_names(self) -> None:
        """
        Ensure all non-global nets in this design are scoped with its net scope.

        This is primarily used for modules so that, once added to a parent,
        all of their internal nets are uniquely namespaced. Global nets like
        GND are not modified.
        """
        for module in self.modules:
            module._enforce_scoped_net_names()

        # Work on a snapshot of keys since we may rename during iteration
        for net_name in list(self.nets.keys()):
            scoped = self.scoped_net_name(net_name)
            if scoped != net_name:
                self.change_net_name(net_name, scoped)
        for declarations in (self._declared_rails, self._external_drives):
            for net_name in list(declarations):
                scoped = self.scoped_net_name(net_name)
                if scoped != net_name:
                    declarations[scoped] = declarations.pop(net_name)

    def _update_net_scope(self, new_scope: str) -> None:
        """
        Update the private net scope for this design and nested child modules.

        This deliberately does not change short_name, which is also used for
        module symbols and flattened component reference designators.
        """
        old_scope = self._net_scope
        self._net_scope = new_scope
        old_prefix = f"{old_scope}_"
        new_prefix = f"{new_scope}_"
        for net_name in list(self.nets.keys()):
            if net_name.startswith(old_prefix):
                self.change_net_name(
                    net_name,
                    net_name.replace(old_prefix, new_prefix, 1),
                )

        for module in self.modules:
            module._update_net_scope(f"{new_scope}_{module.short_name}")

    def merge_nets(
        self, source_net_name: str, target_net_name: str, name: Optional[str] = None
    ) -> None:
        """
        Merges two nets together, moving all connections from the source net to the target net.

        :param source_net_name: The name of the net to merge from (will be removed after merging).
        :type source_net_name: str
        :param target_net_name: The name of the net to merge into (will contain all connections after merging).
        :type target_net_name: str
        :param name: Optional new name for the merged net. If None, uses target_net_name.
        :type name: Optional[str]
        :return: None
        :raises KeyError: If either source_net_name or target_net_name doesn't exist in the design.
        """
        names = {
            "source_net_name": source_net_name,
            "target_net_name": target_net_name,
        }
        if name is not None:
            names["name"] = name
        cmp.validate_net_names("merge_nets()", **names)
        if source_net_name not in self.nets:
            raise KeyError(f"Source net '{source_net_name}' does not exist in design")
        if target_net_name not in self.nets:
            raise KeyError(f"Target net '{target_net_name}' does not exist in design")
        if source_net_name == target_net_name:
            raise RuntimeError(
                f"Source and target net are the same: '{source_net_name}'"
            )

        source_net = self.nets[source_net_name]
        target_net = self.nets[target_net_name]
        source_connections = list(source_net.connections)

        # Move all pins from source net to target net
        for pin in source_connections:
            # Update pin_to_net mapping
            self._pin_to_net[pin] = target_net
            target_net.connections.add(pin)

        # Remove the source net
        del self._nets[source_net_name]

        # Rename target net if a new name is provided
        if name is not None and name != target_net_name:
            self.change_net_name(target_net_name, name)
        else:
            for pin in source_connections:
                self._sync_child_port_net(pin, target_net_name)

    def connect(
        self,
        list_of_pins: List[cmp.Pin],
        net_name: Optional[str] = None,
    ) -> None:
        """
        Connects a list of pins to a specified net. If no net name is provided, it automatically generates a net name.

        This method connects all provided pins to the same net. If the pins are already part of a net,
        it will merge these nets into one. If no net name is provided and the pins are not part of any existing net,
        it generates a new net name based on the first pin's name.

        :param list_of_pins: The list of pins to be connected.
        :type list_of_pins: List[cmp.Pin]
        :param net_name: The name of the net to connect the pins to. If None, a net name will be generated or chosen based on existing connections.
        :type net_name: Optional[str]

        :returns: None
        """

        if not isinstance(list_of_pins, list):
            raise TypeError(
                f"connect() argument 'list_of_pins' must be a list, "
                f"got {type(list_of_pins).__name__}"
            )
        if not list_of_pins:
            raise ValueError("connect() argument 'list_of_pins' cannot be empty")
        invalid_pins = [pin for pin in list_of_pins if not isinstance(pin, cmp.Pin)]
        if invalid_pins:
            invalid_pin = invalid_pins[0]
            raise SchematicConnectionError(
                f"Invalid pin: {type(invalid_pin).__name__} {invalid_pin}"
            )
        self._validate_connection_arguments(
            "connect()",
            list_of_pins,
            [] if net_name is None else [net_name],
        )
        if net_name is None:
            nets = [self.pin_to_net.get(p) for p in list_of_pins]
            if not any(nets):
                # All pins don't have a net associated with them
                net_name = f"AutoNet_{list_of_pins[0].name}"
            else:
                # Some pins have nets associated with them
                #   First valid net set as net for all pins
                net_name = [net.name for net in nets if net][0]
        for pin in list_of_pins:
            self.join_net(pin, net_name)

    def _get_bus_index(self, bus):
        bus_type = type(bus).__name__
        name, pin = next(iter(bus._asdict().items()))
        if pin in self.pin_to_net:
            net_name = self.pin_to_net[pin].name
            if net_name.startswith(bus_type) and net_name.endswith(name.upper()):
                return int(net_name[len(bus_type)])

    def set_passive_footprint(self, component: cmp.PASSIVE_TYPES):
        if component.footprint is not None:
            return
        package_size = component.package_size or self.default_passive_size
        name = component.refdes_prefix[0] + package_size
        package = passives.PassivePackage[name]
        component.footprint = passives.PassiveSmd(package)

    def connect_bus(self, busses: list, bus_index=None):
        """
        Connects two buses of the same type, optionally mergig with an existing bus via an index.

        This method connects all pins of two buses, ensuring they are of the same type. If a bus index is not provided, it will first check if either bus is already connected to a bus and merge them. Else
        it will auto-increment the index creating a new bus.

        :param bus1: The first bus to connect.
        :param bus2: The second bus to connect, must be of the same type as bus1.
        :param bus_index: (Optional[int]) The index of the bus to use. Use to merge with existing net.
        :type bus_index: Optional[int]
        :raises AssertionError: If the types of bus1 and bus2 do not match.
        :return: None
        """

        bus_types = [type(bus) for bus in busses]
        bus_type = bus_types[0].__name__
        assert all(
            t == type(busses[0]) for t in bus_types
        ), f"Mismatch busses! {bus_types}"
        if bus_index is None:
            # Check if either bus is already connected to a bus
            for bus in busses:
                if self._get_bus_index(bus) is not None:
                    bus_index = self._get_bus_index(bus)
                    if bus_index is not None:
                        break
            else:
                # Else assign a bus name
                bus_index = self.busses.get(bus_type, 0)
                self.busses[bus_type] = bus_index + 1
        net_name = f"{bus_type}{bus_index}"
        for bus in busses:
            for name, pin in bus._asdict().items():
                self.join_net(pin, "_".join([net_name, name.upper()]))

    def add_pullup_resistor(
        self, pin: cmp.Pin, ohms: Union[cmp.Resistor, int, str], net_name: str
    ):
        """
        Helper function to automatically add a pullup resistor to a pin
        """
        self._validate_connection_arguments("add_pullup_resistor()", [pin], [net_name])
        if not isinstance(ohms, cmp.Resistor):
            res = self.add_component(cmp.Resistor(ohms))
        else:
            res = ohms
            if not res.is_in_design:
                self.add_component(res)
            elif res.parent is not self:
                raise ValueError(
                    "add_pullup_resistor() resistor belongs to another design"
                )
        self.join_net(res.pins[1], net_name)
        self.connect([res.pins[2], pin])
        return res

    def add_series_res(
        self,
        pin1: cmp.Pin,
        ohms: Union[cmp.Resistor, int, str],
        pin2: cmp.Pin,
        net_name: Optional[str] = None,
    ):
        """
        Helper function to automatically add a series resistor in between two pins

        :param pin1: The first pin to connect the series resistor to.
        :param ohms: The resistance value or resistor component to be added in series.
        :param pin2: The second pin to connect the series resistor to.
        :param net_name: (Optional) The name of the net to which the series resistor will be connected. If not provided, it will be determined based on pin1.
        :type pin1: earthground.components.Pin
        :type ohms: Union[cmp.Resistor, int, str]
        :type pin2: earthground.components.Pin
        :type net_name: Optional[str]
        :return: The resistor component added in series.
        :rtype: earthground.components.Resistor
        """
        self._validate_connection_arguments(
            "add_series_res()",
            [pin1, pin2],
            [] if net_name is None else [net_name],
        )
        if net_name is None:
            net_name = self._get_net_name_from_pin(pin1)
        res = ohms
        if not isinstance(ohms, cmp.Resistor):
            res = cmp.Resistor(ohms)
        self.add_component(res)
        self.join_net(pin1, net_name)
        self.join_net(res.pins[1], net_name)
        next_name = net_name + "_R"
        if pin2 in self.pin_to_net:
            next_name = self.pin_to_net[pin2].name
        self.join_net(res.pins[2], next_name)
        self.join_net(pin2, next_name)
        return res

    def add_voltage_divider(
        self,
        input_pin: cmp.Pin,
        output_pin: cmp.Pin,
        divider: float,
        resistance: float,
        output_net_name: Optional[str] = None,
        ground_net_name: str = "GND",
    ) -> cmp.Pin:
        """
        Helper function to automatically add a voltage divider to a pin
        """
        names = {"ground_net_name": ground_net_name}
        if output_net_name is not None:
            names["output_net_name"] = output_net_name
        self._validate_connection_arguments(
            "add_voltage_divider()",
            [input_pin, output_pin],
            names.values(),
        )
        r1, r2 = sv.voltage_divider(1, divider, resistance)
        res1 = self.add_component(cmp.Resistor(r1))
        res2 = self.add_component(cmp.Resistor(r2))
        self.connect([res1.pins[1], input_pin])
        self.connect([res1.pins[2], res2.pins[1], output_pin], output_net_name)
        self.join_net(res2.pins[2], ground_net_name)

    def add_decoupling_capacitor(
        self,
        capacitor: cmp.Capacitor,
        net_name: str,
        ground_net_name: str = "GND",
    ) -> None:
        """
        Helper function to automatically add a decoupling capacitor to a pin

        :param capacitor: The decoupling capacitor to add.
        :param net_name: The name of the net to which the capacitor will be connected.
        :type capacitor: earthground.components.Capacitor
        :type net_name: str
        :return: None
        """
        if not isinstance(capacitor, cmp.Capacitor):
            raise ValueError(f"Invalid capacitor: {type(capacitor)} {capacitor}")
        cmp.validate_net_names(
            "add_decoupling_capacitor()",
            net_name=net_name,
            ground_net_name=ground_net_name,
        )
        self.add_component(capacitor)
        self.join_net(capacitor.pins[1], net_name)
        self.join_net(capacitor.pins[2], ground_net_name)

    def set_ports(self, port_connections: Dict[str, Union[str, cmp.Pin]]) -> None:
        """
        Sets connections for the design's ports.

        This method allows for connecting ports to either net names or pins.
        If a port is connected to a net name, the corresponding pin will be joined to that net.
        If a port is connected to a pin, both will be joined to the same net.

        :param port_connections: Dictionary mapping port names to either net names or pins
        :type port_connections: Dict[str, Union[str, cmp.Pin]]
        :return: None
        :raises ValueError: If a port name doesn't exist in the design
        """
        if not isinstance(port_connections, dict):
            raise TypeError(
                f"set_ports() argument 'port_connections' must be a dict, "
                f"got {type(port_connections).__name__}"
            )
        for port_name, connection in port_connections.items():
            if port_name not in self.port.names:
                raise ValueError(
                    f"Port '{port_name}' does not exist in design '{self.name}'"
                )
            if isinstance(connection, str):
                cmp.validate_net_names("set_ports()", connection=connection)
            elif isinstance(connection, cmp.Pin):
                self._validate_connection_arguments(
                    "set_ports()",
                    [connection],
                )
            else:
                raise ValueError(
                    f"Invalid connection type for port '{port_name}': "
                    f"{type(connection)}"
                )

        for port_name, connection in port_connections.items():
            port_pin = self.port[port_name]
            if isinstance(connection, str):
                # Connect port to a net name
                self.join_net(port_pin, connection)
            elif isinstance(connection, cmp.Pin):
                # Connect port to another pin
                if connection in self.pin_to_net:
                    # If the pin is already connected to a net, join the port to that net
                    net_name = self.pin_to_net[connection].name
                    self.join_net(port_pin, net_name)
                else:
                    # Create a new net based on the port name
                    net_name = f"{self.short_name}_{port_name}"
                    self.join_net(port_pin, net_name)
                    self.join_net(connection, net_name)

    def iter_designs(self) -> Iterator["Design"]:
        """Yield this design and every nested module depth-first."""
        yield self
        for module in self.modules:
            yield from module.iter_designs()

    def iter_modules(self) -> Iterator["Design"]:
        """Yield every nested module depth-first."""
        for module in self.modules:
            yield module
            yield from module.iter_modules()

    def iter_components(self) -> Iterator[cmp.Component]:
        """Yield components from this design and every nested module."""
        for design in self.iter_designs():
            yield from design.components.values()

    def check_electrical(self) -> ElectricalReport:
        return erc.check_design(self)

    def electrical_coverage(self):
        return erc.electrical_coverage(self)

    def datasheet_coverage(self):
        coverage = {
            "provenanced": [],
            "url_only": [],
            "undocumented": [],
            "not_applicable": [],
        }
        for resolved in DesignAnalysis(self).components:
            component = resolved.component
            if component.virtual or component.dnp:
                continue
            if component.documentation_mode is sourcing.EvidenceMode.NOT_APPLICABLE:
                category = "not_applicable"
                coverage[category].append(resolved.refdes)
                continue
            evidence = sourcing.resolve_documentation(self, component)
            datasheet = component.datasheet if evidence is None else evidence.datasheet
            revision = (
                component.datasheet_revision
                if evidence is None
                else evidence.datasheet_revision
            )
            sha256 = (
                component.datasheet_sha256
                if evidence is None
                else evidence.datasheet_sha256
            )
            if datasheet and (revision or sha256):
                category = "provenanced"
            elif datasheet:
                category = "url_only"
            else:
                category = "undocumented"
            coverage[category].append(resolved.refdes)
        return {key: tuple(values) for key, values in coverage.items()}

    def sourcing_report(self) -> sourcing.SourcingReport:
        return sourcing.check_design(self)

    def validate(
        self,
        skip_footprint_check=False,
        check_no_single_connections=False,
        check_electrical=False,
        check_straps=False,
        check_contracts=False,
        check_sourcing=False,
    ):
        errors = []
        errors.extend(signal_integrity.validate_design(self))
        components = list(self.iter_components())
        if not skip_footprint_check:
            for component in components:
                log.debug(f"Validated: {component}")
                if not component.footprint and not component.virtual:
                    errors.append(f"No footprint: {component.name}")
        errors.extend(self._validate_design(check_no_single_connections))
        for module in self.iter_modules():
            errors.extend(module._validate_design(False))
        if check_electrical:
            report = self.check_electrical()
            errors.extend(str(check) for check in report.blocking)
        if check_straps:
            report = self.check_straps()
            errors.extend(
                f"STRAP {result.status.value} at {result.refdes}.{result.pin}: "
                f"{result.message}"
                for result in report.results
                if result.status is not sv.CheckStatus.PASS
            )
        if check_contracts:
            report = self.check_contracts()
            errors.extend(
                str(check) for check in report.checks if not check.is_accepted
            )
        if check_sourcing:
            errors.extend(str(check) for check in self.sourcing_report().blocking)
        if errors:
            header = f" {self.name.upper()} VALIDATION FAILED "
            log.error("")
            log.error(header.center(60, "="))
            for e in errors:
                log.error(f" - {e}")
            log.error("")
            raise SchematicValidationError(self.name, errors)
        return components

    def _resolved_net_connections(self) -> Dict[str, set[cmp.Pin]]:
        """
        Return flattened net connection sets without modifying the design.

        Child nets are first merged by name, matching ``flatten()``, and are
        then merged into their parent nets through connected module ports.
        """
        resolved = {
            net_name: set(net.connections)
            for net_name, net in self.nets.items()
            if isinstance(net_name, str) and isinstance(net, cmp.Net)
        }

        for module in self.modules:
            module_connections = module._resolved_net_connections()
            port_net_mappings = {}
            for port_name in module.port.names:
                port = module.port[port_name]
                parent_net = self.pin_to_net.get(port)
                module_net = module.pin_to_net.get(port)
                if module_net and parent_net:
                    port_net_mappings[module_net.name] = parent_net.name

            for net_name, connections in module_connections.items():
                resolved.setdefault(net_name, set()).update(connections)

            for module_net_name, parent_net_name in port_net_mappings.items():
                if (
                    module_net_name not in resolved
                    or parent_net_name not in resolved
                    or module_net_name == parent_net_name
                ):
                    continue
                resolved[parent_net_name].update(resolved.pop(module_net_name))

        return resolved

    def _validate_design(self, check_no_single_connections: bool):
        errors = []
        default = set(vars(Ports([], self)))
        port_diff = set(vars(self.port).keys()) - set(self._ports) - default
        if port_diff:
            errors.append(f"Ports changed after initialization! {port_diff}")

        connected_pins = {}
        for net_key, net in self.nets.items():
            if not isinstance(net_key, str) or not net_key:
                errors.append(
                    f"Invalid net registry key: {net_key!r} ({type(net_key).__name__})"
                )
            if not isinstance(net, cmp.Net):
                errors.append(f"Invalid net value at {net_key!r}: {type(net).__name__}")
                continue
            if not isinstance(net.name, str) or not net.name:
                errors.append(f"Invalid net name at {net_key!r}: {net.name!r}")
            elif net_key != net.name:
                errors.append(
                    f"Net registry key/name mismatch: {net_key!r} != {net.name!r}"
                )
            for pin in net.connections:
                if not isinstance(pin, cmp.Pin):
                    errors.append(f"Invalid {type(pin).__name__} on net {net_key!r}")
                    continue
                if not self._pin_belongs_to_design(pin):
                    errors.append(f"Net pin not owned by design '{self.name}': {pin}")
                if pin in connected_pins and connected_pins[pin] is not net:
                    errors.append(
                        f"Pin appears on multiple nets: {pin} "
                        f"({connected_pins[pin].name!r}, {net.name!r})"
                    )
                connected_pins[pin] = net
                if self.pin_to_net.get(pin) is not net:
                    errors.append(f"pin_to_net mismatch: {pin} on {net.name!r}")

        for pin, net in self.pin_to_net.items():
            if not isinstance(pin, cmp.Pin):
                errors.append(f"Invalid pin_to_net key: {pin!r} ({type(pin).__name__})")
                continue
            if not isinstance(net, cmp.Net):
                errors.append(
                    f"Invalid pin_to_net value for {pin}: {type(net).__name__}"
                )
                continue
            registered_net = (
                self.nets.get(net.name)
                if isinstance(net.name, str) and net.name
                else None
            )
            if registered_net is not net:
                errors.append(f"pin_to_net references an unregistered net: {pin}")
            if pin not in net.connections:
                errors.append(f"pin_to_net connection missing from net: {pin}")

        if check_no_single_connections:
            errors.extend(
                f"Single connection! Net<{net_name}> - {connections}"
                for net_name, connections in self._resolved_net_connections().items()
                if len(connections) == 1
            )
        return errors

    def print_symbol(self):
        """
        Prints visual representation of the symbol of the design to the stdout

        Symbol is the design and all it's ports
        """
        if not self.port.names:
            return
        pad = max([len(n) for n in self.port.names]) + 2
        print(f"{self.short_name} ({self.name})")
        print("." + "-" * pad + ".")
        for name in self.port.names:
            connection = "<NO CONNECTION>"
            if self.port[name] and isinstance(self.port[name], cmp.Pin):
                if self.port[name] in self.pin_to_net:
                    connection = self.pin_to_net[self.port[name]].name
            elif self.port[name]:
                pins = [p for p in self.port[name]._asdict().values()]
                pin_names = [self.pin_to_net[p].name for p in pins]
                name = type(self.port[name]).__name__
                connection = f"{name} [{', '.join(pin_names)}]"
            print(f"|{name.rjust(pad).upper()}|-- {connection}")
        print("'" + "-" * pad + "'\n")

    def print(self):
        """
        Prints visual representation of a design to the stdout
        """
        for component in self.components.values():
            component.print()


def flatten(design) -> "Design":
    """
    Merges all modules into the design, flattening the hierarchical structure.

    This method:
    - Moves all components from modules into the parent design
    - Appends module short_name to component reference designators
    - Merges nets through ports (connects module internal nets to parent nets via ports)
    - Removes module symbols and clears the modules list

    :return: Design object
    :rtype: Design
    """
    # Process modules
    for module in list(design.modules):
        # Recursively flatten the module
        module = flatten(module)
        # Store port pin to net mappings for merging
        # Maps module net names to parent net names for nets connected through ports
        port_net_mappings = {}
        for name in module.port.names:
            port = module.port[name]
            # Check if port pin is connected to a parent net
            parent_net = design.pin_to_net.get(port)
            module_net = module.pin_to_net.get(port)
            if module_net and parent_net:
                port_net_mappings[module_net.name] = parent_net.name

        # Move all components from module to parent
        module_components = list(module.components.values())
        for component in module_components:
            # Skip the virtual port symbol
            if component.virtual:
                continue

            # Update refdes_postfix to include module short_name
            if not component.refdes_postfix:
                component.refdes_postfix = module.short_name
            else:
                component.refdes_postfix = (
                    f"{component.refdes_postfix}_{module.short_name}"
                )

            # Add to parent design, keyed by stable refdes string instead of hash.
            # refdes already includes any module-specific postfix and is unique.
            component.place(design)
            design.components[component.refdes] = component

        # Collect port symbol pins to exclude from pin_to_net copying
        port_symbol_pins = set()
        for port_name in module.port.names:
            port_pin = module.port[port_name]
            port_symbol_pins.add(port_pin)

        # Move all nets to parent first
        for net_name, net in list(module.nets.items()):
            if net_name not in design.nets:
                design._nets[net_name] = net
            else:
                # Net already exists, merge connections
                existing_net = design.nets[net_name]
                for pin in list(net.connections):
                    design._pin_to_net[pin] = existing_net
                    existing_net.connections.add(pin)

        # Copy pin_to_net mappings from module to parent (excluding port pins)
        # Point to the nets that are now in the parent design
        for pin, net in module.pin_to_net.items():
            if pin not in port_symbol_pins:
                net_name = net.name
                if net_name in design.nets:
                    design._pin_to_net[pin] = design.nets[net_name]

        # Merge nets through ports (this updates pin_to_net for all pins in merged nets)
        for module_net_name, parent_net_name in port_net_mappings.items():
            if module_net_name in design.nets and parent_net_name in design.nets:
                if module_net_name == parent_net_name:
                    continue
                design.merge_nets(module_net_name, parent_net_name)

    return design

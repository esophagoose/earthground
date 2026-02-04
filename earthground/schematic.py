import logging
from typing import Dict, List, NamedTuple, Optional, Union

import earthground.components as cmp
import earthground.library.footprints.passives as passives


class Position(NamedTuple):
    x: float
    y: float
    angle: float


class ComponentLayout(NamedTuple):
    id: Position
    component: Position


class Ports:
    def __init__(self, ports: List[str], parent: "Design"):
        self.names = [p.lower() for p in ports]
        self.symbol = cmp.Component("SUB")
        self.symbol.virtual = True
        self.symbol.name = parent.name
        self.symbol.pins = cmp.PinContainer.from_list(ports, self)
        for name in ports:
            setattr(self, name.lower(), self.symbol.pins.by_name(name))

    def __getitem__(self, port) -> cmp.Pin:
        port = port.lower()
        if port not in self.names:
            raise ValueError(f"Unknown port: {port}. Options {self.names}")
        return getattr(self, port)

    def __setitem__(self, port, value) -> None:
        raise RuntimeError("Can't direct set ports! Connect in schematic")


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
        self.components: Dict[str, cmp.Component] = {}
        self.modules: List[Design] = []
        self.nets: Dict[str, cmp.Net] = {}
        self.pin_to_net: Dict[cmp.Pin, cmp.Net] = {}
        self.busses = {}
        self.default_passive_size = "0603"
        self.port = Ports([p.lower() for p in ports], self)
        self.ground = self.add_net("GND").name
        self.layout: Dict[str, ComponentLayout] = {}
        self._ports = [p.lower() for p in ports]
        self._module_names: Dict[str, int] = {}

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
        prefix = module.short_name + str(self._module_names[module.short_name])
        self._module_names[module.short_name] += 1
        module.short_name = prefix
        net_names = [net.name for net in module.nets.values()]
        for net_name in net_names:
            module.change_net_name(net_name, "_".join([prefix, net_name]))
        if self.default_passive_size:
            for component in module.components.values():
                if isinstance(component, cmp.PASSIVE_TYPES):
                    self.set_passive_footprint(component)
        self.modules.append(module)
        self.add_component(module.port.symbol)
        return module

    def add_component(self, component: cmp.Component) -> cmp.Component:
        """
        Adds a component to the current design

        :param component: The component to be added to the design.
        :type component: Component
        :return: The component that was added, with updated footprint if applicable.
        :rtype: Component
        """
        logging.info(f"Adding component {component}")
        if isinstance(component, cmp.PASSIVE_TYPES) and self.default_passive_size:
            self.set_passive_footprint(component)

        if hash(component) not in self.components:
            self.components[hash(component)] = component
            component.place(self)
            return component
        raise ValueError(f"Component is already in the design! {component}")

    def add_net(self, name) -> cmp.Net:
        """
        Creates a net in the design and returns it.

        :param name: The name of the net to be created.
        :type name: str
        :return: The newly created net.
        :rtype: earthground.components.Net
        """
        net = cmp.Net(name)
        self.nets[name] = net
        return net

    def _add_to_net(self, pin: cmp.Pin, net: cmp.Net):
        if pin in self.pin_to_net:
            old_net = self.pin_to_net[pin]
            if old_net == net:
                return
            return self.change_net_name(old_net.name, net.name)
        self.nets[net.name].connections.add(pin)
        self.pin_to_net[pin] = net

    def _get_net_name_from_pin(self, pin: cmp.Pin) -> str:
        if pin in self.pin_to_net:
            return self.pin_to_net[pin].name
        return f"AutoNet_{pin.name}"

    def join_net(self, pin: cmp.Pin, net_name: str) -> cmp.Net:
        """
        Joins a pin to a specified net by its name. If the net does not exist, it is created.

        :param pin: The pin that needs to be joined to the net.
        :type pin: earthground.components.Pin
        :param net_name: The name of the net to which the pin will be joined.
        :type net_name: str
        :return: The net to which the pin was successfully joined.
        :rtype: earthground.components.Net
        """
        # error = f"Floating part {pin.parent}! Did you forget to add it?"
        # assert pin.parent in self.components.values(), error
        if net_name not in self.nets:
            self.nets[net_name] = cmp.Net(net_name)
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
        logging.warning(f"Overwriting net {old_net_name} to {new_net_name}")
        self.nets[new_net_name] = self.nets.pop(old_net_name)
        self.nets[new_net_name].name = new_net_name

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

        # Move all pins from source net to target net
        for pin in list(source_net.connections):
            # Update pin_to_net mapping
            self.pin_to_net[pin] = target_net
            target_net.connections.add(pin)

        # Remove the source net
        del self.nets[source_net_name]

        # Rename target net if a new name is provided
        if name and name != target_net_name:
            self.change_net_name(target_net_name, name)

    def connect(self, list_of_pins: List[cmp.Pin], net_name=None):
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

        if not net_name:
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

    def set_passive_footprint(self, component):
        name = type(component).__name__[0] + self.default_passive_size
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
        net_name = net_name or self._get_net_name_from_pin(pin1)
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

    def add_decoupling_capacitor(
        self, capacitor: cmp.Capacitor, net_name=None, ground_net_name="GND"
    ):
        """
        Helper function to automatically add a decoupling capacitor to a pin

        :param capacitor: The decoupling capacitor to add.
        :param net_name: (Optional) The name of the net to which the capacitor will be connected. If not provided, it will be determined based on the pin.
        :type capacitor: earthground.components.Capacitor
        :type net_name: Optional[str]
        :return: None
        """
        net_name = net_name or self._get_net_name_from_pin(self)
        self.add_component(capacitor)
        self.join_net(self, net_name)
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
        for port_name, connection in port_connections.items():
            port_name = port_name.lower()
            if port_name not in self.port.names:
                raise ValueError(
                    f"Port '{port_name}' does not exist in design '{self.name}'"
                )

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
            else:
                raise ValueError(
                    f"Invalid connection type for port '{port_name}': {type(connection)}"
                )

    def validate(self, skip_footprint_check=False, check_no_single_connections=False):
        errors = []
        components = list(self.components.values())
        for module in self.modules:
            components.extend(list(module.components.values()))
        if not skip_footprint_check:
            for component in components:
                logging.debug(f"Validated: {component}")
                if not component.footprint and not component.virtual:
                    errors.append(f"No footprint: {component.name}")
        errors.extend(self._validate_design(check_no_single_connections))
        if errors:
            header = f" {self.name.upper()} VALIDATION FAILED "
            logging.error("")
            logging.error(header.center(60, "="))
            for e in errors:
                logging.error(f" - {e}")
            logging.error("")
            assert not errors
        return components

    def _validate_design(self, check_no_single_connections: bool):
        errors = []
        default = set(vars(Ports([], self)))
        port_diff = set(vars(self.port).keys()) - set(self._ports) - default
        if port_diff:
            errors.append(f"Ports changed after initialization! {port_diff}")
        if check_no_single_connections:
            for net in self.nets.values():
                if len(net.connections) != 1:
                    continue
                errors.append(f"Single connection! {net} - {net.connections}")
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

            # Add to parent design
            component.place(design)
            design.components[hash(component)] = component

        # Collect port symbol pins to exclude from pin_to_net copying
        port_symbol_pins = set()
        for port_name in module.port.names:
            port_pin = module.port[port_name]
            port_symbol_pins.add(port_pin)

        # Move all nets to parent first
        for net_name, net in list(module.nets.items()):
            if net_name not in design.nets:
                design.nets[net_name] = net
            else:
                # Net already exists, merge connections
                existing_net = design.nets[net_name]
                for pin in list(net.connections):
                    design.pin_to_net[pin] = existing_net
                    existing_net.connections.add(pin)

        # Copy pin_to_net mappings from module to parent (excluding port pins)
        # Point to the nets that are now in the parent design
        for pin, net in module.pin_to_net.items():
            if pin not in port_symbol_pins:
                net_name = net.name
                if net_name in design.nets:
                    design.pin_to_net[pin] = design.nets[net_name]

        # Merge nets through ports (this updates pin_to_net for all pins in merged nets)
        for module_net_name, parent_net_name in port_net_mappings.items():
            if module_net_name in design.nets and parent_net_name in design.nets:
                if module_net_name == parent_net_name:
                    continue
                design.merge_nets(module_net_name, parent_net_name)

    return design

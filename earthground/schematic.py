import logging
from typing import Dict, List, Optional, Union

import earthground.components as cmp
import earthground.library.footprints.passives as passives


class Ports:
    def __init__(self, ports: List[str], parent: "Design"):
        self.names = [p.lower() for p in ports]
        self.symbol = cmp.Component("SYMBOL")
        self.symbol.name = parent.name
        self.symbol.pins = cmp.PinContainer.from_list(ports, self)
        for port in self.names:
            setattr(self, port, cmp.Pin(port, 0, parent))

    def __getitem__(self, port):
        port = port.lower()
        if port not in self.names:
            raise ValueError(f"Unknown port: {port}. Options {self.names}")
        return getattr(self, port)

    def __setitem__(self, port, value):
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
        self.default_passive_size = None
        self.port = Ports([p.lower() for p in ports], self)
        self.ground = self.add_net("GND").name
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
        return module

    def add_component(self, component):
        """
        Adds a component to the current design.

        :param component: The component to be added to the design.
        :type component: Component

        :return: The component that was added, with updated footprint if applicable.
        :rtype: Component
        """

        logging.info(f"Adding component {component}")
        if isinstance(component,
                      cmp.PASSIVE_TYPES) and self.default_passive_size:
            self.set_passive_footprint(component)
        self.components[hash(component)] = component
        component.parent = self
        return component

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
        # schematic = pin.parent
        # if not isinstance(schematic, Design):
        #     schematic = cast(Design, pin.parent.parent)
        # assert schematic, f"Floating part {pin.parent}! Did you forget to add it?"
        # if net_name not in schematic.nets:
        #     schematic.nets[net_name] = cmp.Net(net_name)
        # net = schematic.nets[net_name]
        # schematic._add_to_net(pin, net)
        # return schematic.nets[net_name]
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
                #  First valid net set as net for all pins
                net_name = [net.name for net in nets if net][0]
        for pin in list_of_pins:
            self.join_net(pin, net_name)

    def _get_bus_index(self, bus):
        bus_type = type(bus).__name__
        name, pin = next(iter(bus._asdict().items()))
        if pin in self.pin_to_net:
            net_name = self.pin_to_net[pin].name
            if net_name.startswith(bus_type) and net_name.endswith(
                    name.upper()):
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
        assert all(t == type(busses[0])
                   for t in bus_types), f"Mismatch busses! {bus_types}"
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

    def add_decoupling_cap(self, pin, capacitor: cmp.Capacitor, net_name=None):
        """
        Helper function to automatically add a decoupling cap to a pin

        :param pin: The pin to which the decoupling capacitor will be added.
        :param capacitor: The decoupling capacitor to add.
        :param net_name: (Optional) The name of the net to which the capacitor will be connected. If not provided, it will be determined based on the pin.
        :type pin: earthground.components.Pin
        :type capacitor: earthground.components.Capacitor
        :type net_name: Optional[str]
        :return: None
        """
        net_name = net_name or self._get_net_name_from_pin(pin)
        self.add_component(capacitor)
        self.join_net(pin, net_name)
        self.join_net(capacitor.pins[1], net_name)
        self.join_net(capacitor.pins[2], self.ground)

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

    def validate(self,
                 skip_footprints=False,
                 check_no_single_connections=False):
        errors = []
        components = list(self.components.values())
        for module in self.modules:
            components.extend(list(module.components.values()))
        for component in components:
            logging.debug(f"Validated: {component}")
            if not component.footprint and not skip_footprints:
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
                if len(net.connections) == 1:
                    errors.append(
                        f"Single connection! {net} - {net.connections}")
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
            pad = max([len(p.name) for p in component.pins]) + 2
            print(f"{component.refdes} ({component.name})")
            print("." + "-" * pad + ".")
            for pin in sorted(component.pins, key=lambda p: p.name):
                connection = "<NO CONNECTION>"
                if pin in self.pin_to_net:
                    connection = self.pin_to_net[pin].name
                print(f"|{pin.name.rjust(pad)}|-- {connection}")
            print("'" + "-" * pad + "'\n")
        for module in self.modules:
            module.print_symbol()

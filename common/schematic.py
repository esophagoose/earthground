import logging
from collections import defaultdict
from typing import Dict, List, Union, cast

import common.components as cmp
import library.footprints.passives as passives


class Ports:
    def __init__(self, ports: List[str]):
        self.names = ports
        for port in ports:
            setattr(self, port.lower(), None)

    def __getitem__(self, port):
        port = port.lower()
        if port not in self.names:
            raise ValueError(f"Unknown port: {port}. Options {self.names}")
        return getattr(self, port)

    def __setitem__(self, port, value):
        port = port.lower()
        if port not in self.names:
            raise ValueError(f"Unknown port: {port}. Options {self.names}")
        return setattr(self, port, value)


class Design:
    def __init__(self, name, short_name=None, ports=[]):
        self.name = name
        self.short_name = short_name
        if not short_name:
            self.short_name = self.name
        self.components: Dict[str, cmp.Component] = {}
        self.modules: List[Design] = []
        self._module_names: Dict[str, int] = {}
        self.designator_map = defaultdict(lambda: 0)
        self.nets: Dict[str, cmp.Net] = {}
        self.pin_to_net: Dict[cmp.Pin, cmp.Net] = {}
        self.busses = {}
        self.default_passive_size = None
        self.port = Ports([p.lower() for p in ports])
        self.add_net("GND")

    def add_module(self, module: "Design"):
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
        self.modules.append(module)
        return module

    def add_component(self, component):
        if isinstance(component, cmp.PASSIVE_TYPES) and self.default_passive_size:
            name = type(component).__name__[0] + self.default_passive_size
            package = passives.PassivePackage[name]
            component.footprint = passives.PassiveSmd(package)
        self.components[hash(component)] = component
        component.parent = self
        return component

    def add_net(self, name):
        net = cmp.Net(name)
        self.nets[name] = net
        return net

    def add_to_net(self, pin: cmp.Pin, net: cmp.Net):
        if pin in self.pin_to_net:
            old_net = self.pin_to_net[pin]
            if old_net == net:
                return
            return self.change_net_name(old_net.name, net.name)
        self.nets[net.name].add(pin)
        self.pin_to_net[pin] = net

    def join_net(self, pin: cmp.Pin, net_name: str):
        schematic = cast(Design, pin.parent.parent)
        assert schematic, f"Floating part {pin.parent}! Did you forget to add it?"
        if net_name not in schematic.nets:
            schematic.nets[net_name] = cmp.Net(net_name)
        net = schematic.nets[net_name]
        schematic.add_to_net(pin, net)
        return schematic.nets[net_name]

    def change_net_name(self, old_net_name: str, new_net_name: str):
        logging.warning(f"Overwriting net {old_net_name} to {new_net_name}")
        self.nets[new_net_name] = self.nets.pop(old_net_name)
        self.nets[new_net_name].name = new_net_name

    def connect(self, list_of_pins: List[cmp.Pin], net_name=None):
        if not net_name:
            nets = [self.pin_to_net.get(p) for p in list_of_pins]
            if not any(nets):
                # All pins don't have a net associated with them
                net_name = f"AutoNet<{list_of_pins[0].name}>"
            else:
                # Some pins have nets associated with them
                #  First valid net set as net for all pins
                net_name = next([net for net in nets if net])
        for pin in list_of_pins:
            self.join_net(pin, net_name)

    def _get_bus_index(self, bus):
        bus_type = type(bus).__name__
        name, pin = next(iter(bus._asdict().items()))
        if pin in self.pin_to_net:
            net_name = self.pin_to_net[pin].name
            if net_name.startswith(bus_type) and net_name.endswith(name.upper()):
                return int(net_name[len(bus_type)])

    def connect_bus(self, bus1, bus2, bus_index=None):
        assert isinstance(
            bus1, type(bus2)
        ), f"Type mismatch! {type(bus1)} != {type(bus2)}"
        bus_type = type(bus1).__name__
        if bus_index is None:
            # Check if either bus is already connected to a bus
            if self._get_bus_index(bus1) is not None:
                bus_index = self._get_bus_index(bus1)
            elif self._get_bus_index(bus2) is not None:
                bus_index = self._get_bus_index(bus2)
            else:
                # Else assign a bus name
                bus_index = self.busses.get(bus_type, 0)
                self.busses[bus_type] = bus_index + 1
        net_name = f"{bus_type}{bus_index}"
        for name, pin in bus1._asdict().items():
            self.join_net(pin, "_".join([net_name, name.upper()]))
        for name, pin in bus2._asdict().items():
            self.join_net(pin, "_".join([net_name, name.upper()]))

    def add_decoupling_cap(self, pin, capacitor):
        self.add_component(capacitor)
        net_name = f"AutoNet{pin.name}"
        if pin in self.pin_to_net:
            net_name = self.pin_to_net[pin].name
        self.join_net(pin, net_name)
        self.join_net(capacitor.pins[1], net_name)
        self.join_net(capacitor.pins[2], "GND")

    def add_series_res(
        self,
        pin1: cmp.Pin,
        ohms: Union[cmp.Resistor, int, str],
        pin2: cmp.Pin,
        net_name: str = None,
    ):
        if not net_name:
            net_name = f"AutoNet{pin1.name}"
            if pin1 in self.pin_to_net:
                net_name = self.pin_to_net[pin1]
        res = ohms
        if not isinstance(ohms, cmp.Resistor):
            res = cmp.Resistor(ohms)
        self.add_component(res)
        self.join_net(pin1, net_name)
        self.join_net(res.pins[1], net_name)
        next_name = net_name + "_R"
        if pin2 in self.pin_to_net:
            next_name = self.pin_to_net[pin2]
        self.join_net(res.pins[2], next_name)
        self.join_net(pin2, next_name)
        return res

    def validate(self):
        errors = []
        components = list(self.components.values())
        for module in self.modules:
            components.extend(list(module.values()))
        for component in components:
            logging.debug(f"Validated: {component}")
            if not component.footprint:
                errors.append(f"No footprint: {component.name}")
        if errors:
            logging.error(f" {self.name.upper()} VALIDATION FAILED ".center(60, "="))
            for e in errors:
                logging.error(f" - {e}")
            logging.error("")
            assert not errors
        return components

    def print_symbol(self):
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

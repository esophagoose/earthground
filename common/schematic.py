import logging
from collections import defaultdict
from typing import Dict, List

import common.components as cmp
import library.footprints.passives as passives


class Ports:
    def __init__(self, ports: List[str]):
        self.names = ports
        for port in ports:
            setattr(self, port, None)

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
            # net.name = "_".join([prefix, net.name])
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

    def join_net(self, pin: cmp.Pin, net: str):
        schematic = pin.parent.parent
        assert schematic, f"Floating part {pin.parent}! Did you forget to add it?"
        if net not in schematic.nets:
            schematic.nets[net] = cmp.Net(net)
        if pin.net and pin.net.name in schematic.nets:
            schematic.change_net_name(pin.net.name, net)
        else:
            schematic.nets[net].add(pin)
        return schematic.nets[net]

    def change_net_name(self, old_net_name: str, new_net_name: str):
        print(f"Changing from {old_net_name} to {new_net_name}")
        self.nets[new_net_name] = self.nets.pop(old_net_name)
        self.nets[new_net_name].name = new_net_name

    def connect(self, list_of_pins: List[cmp.Pin], net_name=None):
        if not net_name:
            if not any([p for p in list_of_pins if p.assigned]):
                net_name = f"AutoNet<{list_of_pins[0].name}>"
            else:
                net_name = next([p for p in list_of_pins if p.assigned]).net.name
        for pin in list_of_pins:
            self.join_net(pin, net_name)

    def connect_bus(self, bus1, bus2, net_name=None):
        assert isinstance(
            bus1, type(bus2)
        ), f"Type mismatch! {type(bus1)} != {type(bus2)}"
        if not net_name:
            bus_type = type(bus1).__name__
            i = self.busses.get(bus_type, 0)
            net_name = f"{bus_type}{i}"
            self.busses[bus_type] = i + 1
        for name, pin in bus1._asdict().items():
            self.join_net(pin, "_".join([net_name, name.upper()]))
        for name, pin in bus2._asdict().items():
            self.join_net(pin, "_".join([net_name, name.upper()]))

    def add_decoupling_cap(self, pin, capacitor):
        self.add_component(capacitor)
        self.join_net(pin, pin.net.name)
        self.join_net(capacitor.pins[1], pin.net.name)
        self.join_net(capacitor.pins[2], "GND")

    def add_series_res(self, pin1, ohms, pin2, net_name=None):
        if not net_name:
            net_name = pin1.net.name if pin1.net else f"AutoNet{pin1.name}"
        res = cmp.Resistor(ohms)
        self.add_component(res)
        self.join_net(pin1, net_name)
        self.join_net(res.pins[1], net_name)
        next_name = pin2.net.name if pin2.net else net_name + "_R"
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

    def print_design_symbol(self):
        pad = max([len(n) for n in self.port.names]) + 2
        print(f"{self.short_name} ({self.name})")
        print("." + "-" * pad + ".")
        for name in self.port.names:
            connection = "<NO CONNECTION>"
            if self.port[name] and isinstance(self.port[name], cmp.Pin):
                if self.port[name].net:
                    connection = self.port[name].net
            elif self.port[name]:
                c = [p.net.name for p in self.port[name]._asdict().values()]
                name = type(self.port[name]).__name__
                connection = f"{name} [{', '.join(c)}]"
            print(f"|{name.rjust(pad).upper()}|-- {connection}")
        print("'" + "-" * pad + "'\n")

    def print_design(self):
        for component in self.components.values():
            pad = max([len(p.name) for p in component.pins]) + 2
            print(f"{component.refdes} ({component.name})")
            print("." + "-" * pad + ".")
            for pin in sorted(component.pins, key=lambda p: p.name):
                connection = pin.net if pin.net else "<NO CONNECTION>"
                print(f"|{pin.name.rjust(pad)}|-- {connection}")
            print("'" + "-" * pad + "'\n")
        for module in self.modules:
            module.print_design_symbol()

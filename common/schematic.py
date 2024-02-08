import logging
from collections import defaultdict
from typing import Dict, List

import common.components as cmp
import library.footprints.passives as passives


class Net:
    def __init__(self, name) -> None:
        self.name = name
        self.connections = []

    def __repr__(self) -> str:
        return f"Net<{self.name}>"

    def __str__(self) -> str:
        return f"Net<{self.name}>"

    def add(self, pin: cmp.Pin):
        if pin.net == self:
            return
        if pin.net and not pin.net.name.startswith("AutoNet"):
            logging.warning(f"Overwriting net! {pin.net} -> {self}")
        pin.net = self
        self.connections.append(pin)

    def extend(self, pins: List[cmp.Pin]):
        for pin in pins:
            self.connections.append(pin)


class Design:
    def __init__(self, name, short_name=None):
        self.name = name
        self.short_name = short_name
        if not short_name:
            self.short_name = self.name
        self.components = {}
        self.modules: List[Design] = []
        self._module_names: Dict[str, int] = {}
        self.designator_map = defaultdict(lambda: 0)
        self.nets: Dict[str, Net] = {}
        self.busses = {}
        self._pin_to_net = {}
        self.default_passive_size = None

    def add_module(self, module: "Design"):
        if not isinstance(module, Design):
            raise ValueError("Invalid module! Must be schematic.Design type")
        if module.short_name not in self._module_names:
            self._module_names[module.short_name] = 0
        prefix = module.short_name + str(self._module_names[module.short_name])
        self._module_names[module.short_name] += 1
        module.short_name = prefix
        nets = {}
        for name, net in module.nets.items():
            net.name = "_".join([prefix, net.name])
            nets["_".join([prefix, name])] = net
        module.nets = nets
        self.modules.append(module)
        self.nets.update(module.nets)
        return module

    def add_component(self, component):
        if isinstance(component, cmp.PASSIVE_TYPES) and self.default_passive_size:
            name = type(component).__name__[0] + self.default_passive_size
            package = passives.PassivePackage[name]
            component.footprint = passives.PassiveSmd(package)
        self.components[hash(component)] = component
        return component

    def add_net(self, name):
        net = Net(name)
        self.nets[name] = net
        return net

    def join_net(self, pin: cmp.Pin, net):
        if net not in self.nets:
            self.nets[net] = Net(net)
        self.nets[net].add(pin)
        self._pin_to_net[pin] = net
        if hash(pin.parent) not in self.components:
            self.add_component(pin.parent)
        return self.nets[net]

    def change_net_name(self, old_net_name: str, new_net_name: str):
        old_net = self.nets[old_net_name]
        old_net.name = new_net_name
        self.nets[new_net_name] = self.nets[old_net_name]
        del self.nets[old_net_name]

    def connect(self, pin1, pin2, net_name=None):
        if not net_name:
            net_name = self._pin_to_net.get(pin1)
            net_name = net_name or self._pin_to_net.get(pin2, f"AutoNet{pin1.name}")
        self.join_net(pin1, net_name)
        self.join_net(pin2, net_name)

    def connect_bus(self, bus1, bus2, net_name=None):
        assert isinstance(
            bus1, type(bus2)
        ), f"Type mismatch! {type(bus1)} != {type(bus2)}"
        if not net_name:
            bus_type = type(bus1).__name__
            i = len(self.busses)
            net_name = f"{bus_type}{i}"
        for name, pin in bus1._asdict().items():
            self.join_net(pin, "_".join([net_name, name.upper()]))
        for name, pin in bus2._asdict().items():
            self.join_net(pin, "_".join([net_name, name.upper()]))

    def connect_all(self, net_name):
        for module in self.modules:
            full_name = "_".join([module.short_name, net_name])
            if full_name in module.nets:
                self.nets[net_name].extend(module.nets[full_name].connections)
        return self.nets[net_name]

    def add_decoupling_cap(self, pin, capacitor):
        net_name = self._pin_to_net.get(pin, f"AutoNet{pin.name}")
        self.join_net(pin, net_name)
        self.join_net(capacitor.pins[1], net_name)
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

from __future__ import annotations

import dataclasses
from typing import Dict, List

import earthground.schematic as sch_lib
from earthground.interfaces import ConnectorEndpoint, PinMap


class AssemblyError(ValueError):
    pass


class AssemblyValidationError(AssemblyError):
    def __init__(self, assembly_name: str, errors: List[str]):
        self.assembly_name = assembly_name
        self.errors = list(errors)
        super().__init__(
            f"Assembly validation failed for {assembly_name}: " + "; ".join(self.errors)
        )


@dataclasses.dataclass(frozen=True)
class Interconnect:
    name: str
    host: ConnectorEndpoint
    mate: ConnectorEndpoint


class Assembly:
    def __init__(self, name: str):
        self.name = name
        self.boards: Dict[str, sch_lib.Design] = {}
        self.interconnects: List[Interconnect] = []

    def add_board(self, name: str, design: sch_lib.Design) -> sch_lib.Design:
        if name in self.boards:
            raise AssemblyError(f"Board already exists in assembly: {name}")
        self.boards[name] = design
        return design

    def add_interconnect(
        self,
        name: str,
        host_endpoint: ConnectorEndpoint,
        mate_endpoint: ConnectorEndpoint,
    ) -> Interconnect:
        interconnect = Interconnect(name, host_endpoint, mate_endpoint)
        self.interconnects.append(interconnect)
        return interconnect

    def validate(self) -> None:
        errors = []
        for interconnect in self.interconnects:
            errors.extend(self._validate_interconnect(interconnect))
        if errors:
            raise AssemblyValidationError(self.name, errors)

    def _validate_interconnect(self, interconnect: Interconnect) -> List[str]:
        errors = []
        host = interconnect.host
        mate = interconnect.mate

        if host.role != "host":
            errors.append(f"{interconnect.name}: first endpoint role is {host.role}")
        if mate.role != "mate":
            errors.append(f"{interconnect.name}: second endpoint role is {mate.role}")
        if host.interface != mate.interface:
            errors.append(
                f"{interconnect.name}: endpoint interfaces do not match "
                f"({host.interface.name} != {mate.interface.name})"
            )
            return errors
        host_expected = PinMap.straight().resolve(host.interface, host.component)
        if host.pin_map != host_expected:
            errors.append(f"{interconnect.name}: host endpoint is not 1-to-1")
        mate_expected = mate.interface.pin_map.resolve(mate.interface, mate.component)
        if mate.pin_map != mate_expected:
            errors.append(
                f"{interconnect.name}: mate endpoint does not match interface pin_map"
            )

        for endpoint in (host, mate):
            errors.extend(self._validate_endpoint(interconnect.name, endpoint))
        return errors

    def _validate_endpoint(
        self, interconnect_name: str, endpoint: ConnectorEndpoint
    ) -> List[str]:
        errors = []
        design = endpoint.component.parent
        if design is None:
            return [
                f"{interconnect_name}: {endpoint.role} endpoint component "
                f"{endpoint.component} has not been added to a design"
            ]
        if design not in self.boards.values():
            errors.append(
                f"{interconnect_name}: {endpoint.role} endpoint design "
                f"{design.name} is not registered in assembly"
            )

        for contact in endpoint.interface.signal_contacts:
            signal = contact.signal
            pin = endpoint.component.pins.by_name(signal.name)
            if signal.required and pin not in design.pin_to_net:
                errors.append(
                    f"{interconnect_name}: {endpoint.role} signal "
                    f"{signal.name} is required but unconnected"
                )

        for pin in endpoint.no_connect_pins:
            if pin in design.pin_to_net:
                net_name = design.pin_to_net[pin].name
                errors.append(
                    f"{interconnect_name}: {endpoint.role} no-connect "
                    f"{pin.name} is connected to {net_name}"
                )
        return errors

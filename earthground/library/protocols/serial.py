from dataclasses import dataclass
from typing import List

import earthground.components as cmp


@dataclass(frozen=True)
class SerialInterface:
    pass

    def name(self) -> str:
        return self.__class__.__name__

    def fields(self) -> List[str]:
        return list(self.__dataclass_fields__.keys())

    def as_dict(self) -> List[str]:
        return self.__dict__


@dataclass(frozen=True)
class I2C(SerialInterface):
    sda: cmp.Pin
    scl: cmp.Pin


@dataclass(frozen=True)
class USB(SerialInterface):
    dm: cmp.Pin
    dp: cmp.Pin


@dataclass(frozen=True)
class SPI(SerialInterface):
    mosi: cmp.Pin
    miso: cmp.Pin
    sck: cmp.Pin
    cs: cmp.Pin


@dataclass(frozen=True)
class UART(SerialInterface):
    rx: cmp.Pin
    tx: cmp.Pin


@dataclass(frozen=True)
class JTAG(SerialInterface):
    tdo: cmp.Pin
    tdi: cmp.Pin
    tms: cmp.Pin
    tck: cmp.Pin


@dataclass(frozen=True)
class SWD(SerialInterface):
    clk: cmp.Pin
    io: cmp.Pin

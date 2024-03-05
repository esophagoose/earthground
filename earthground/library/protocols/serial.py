from typing import NamedTuple

import earthground.components as cmp


class I2C(NamedTuple):
    sda: cmp.Pin
    scl: cmp.Pin


class SPI(NamedTuple):
    mosi: cmp.Pin
    miso: cmp.Pin
    sck: cmp.Pin
    cs: cmp.Pin


class UART(NamedTuple):
    rx: cmp.Pin
    tx: cmp.Pin

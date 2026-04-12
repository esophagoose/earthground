"""
Generic Microcontroller Component

This is a generic microcontroller component and design generator.
Specific MCUs (like MSP430FR5739-EP) should subclass and implement required pin and interface details.
"""

import logging
from typing import Dict, List

import earthground.components as cmp
import earthground.footprint_types as ft
import earthground.layout as layout
import earthground.schematic as sch
from earthground.library.protocols import serial

log = logging.getLogger(__name__)


class GenericMicrocontroller(cmp.Component):
    """
    Generic microcontroller part. Extend or instantiate directly for MCU evaluation/reference designs.
    """

    def __init__(self, refdes_prefix: str = "U"):
        super().__init__(refdes_prefix=refdes_prefix)
        self.uart: List[serial.UART] = []
        self.spi: List[serial.SPI] = []
        self.i2c: List[serial.I2C] = []
        self.jtag: serial.JTAG = None
        self.swd: serial.SWD = None
        self.gpio: List[cmp.Pin] = []
        self.adc: List[cmp.Pin] = []
        self.pwm: List[cmp.Pin] = []
        self._port_to_pin_name = {}
        self._used_pins = []

    def _use_peripheral(self, peripheral_name: str, index: int):
        peripheral_list: List[serial.SerialInterface] = getattr(self, peripheral_name)
        if not peripheral_list:
            raise RuntimeError(
                f"Attempting to use {peripheral_name} which is unavailable on {self.name}"
            )
        peripheral_list = (
            peripheral_list if isinstance(peripheral_list, list) else [peripheral_list]
        )
        for i, peripheral in enumerate(peripheral_list):
            if not isinstance(peripheral, serial.SerialInterface):
                raise RuntimeError(
                    f"Invalid peripheral type for {peripheral_name}: {type(peripheral)}"
                )
            if any([p.name in self._used_pins for p in peripheral.as_dict().values()]):
                log.debug("Skipping %s%s: pins are already used", peripheral_name, i)
                continue
            log.debug("Assigning %s%s: pins are not used", peripheral_name, i)
            for pin_name, pin in peripheral.as_dict().items():
                net_name = f"{peripheral_name.upper()}{index}_{pin_name.upper()}"
                if net_name in self._port_to_pin_name:
                    log.debug("Skipping %s: pin is already assigned", net_name)
                    continue
                self._port_to_pin_name[net_name] = pin.name
                self._used_pins.append(pin.name)
            return self
        raise RuntimeError(f"Not enough pins available for {peripheral_name}")

    def _use_generic_pin(self, list_name: str, index: int):
        pin_list: List[cmp.Pin] = getattr(self, list_name)
        if not pin_list:
            raise RuntimeError(
                f"Attempting to use {list_name} which is unavailable on {self.name}"
            )
        for pin in pin_list:
            if pin.name in self._used_pins:
                log.debug("Skipping %s: pin is already used", pin.name)
                continue
            log.debug("Assigning %s: pin is not used", pin.name)
            self._port_to_pin_name[f"{list_name.upper()}{index}"] = pin.name
            self._used_pins.append(pin.name)
            return self
        raise RuntimeError(f"Not enough pins available for {list_name}")

    def assign_pins(
        self,
        adc: int = 0,
        uart: int = 0,
        spi: int = 0,
        i2c: int = 0,
        pwm: int = 0,
        gpio: int = 0,
        jtag: bool = False,
        swd: bool = False,
        enforce_pins: Dict[str, str] = {},
    ):
        self._port_to_pin_name = enforce_pins
        self._used_pins = list(enforce_pins.values())

        for i in range(adc):
            self._use_generic_pin("adc", i)
        for i in range(uart):
            self._use_peripheral("uart", i)
        if jtag:
            self._use_peripheral("jtag", 0)
        if swd:
            self._use_peripheral("swd", 0)
        for i in range(spi):
            self._use_peripheral("spi", i)
        for i in range(i2c):
            self._use_peripheral("i2c", i)
        for i in range(pwm):
            self._use_generic_pin("pwm", i)
        for i in range(gpio):
            self._use_generic_pin("gpio", i)
        return self._port_to_pin_name

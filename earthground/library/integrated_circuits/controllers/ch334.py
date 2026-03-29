import earthground.components as cmp
import earthground.library.protocols.serial as serial
import earthground.schematic as sch_lib


class CH334F(cmp.Component):
    def __init__(self):
        super().__init__()
        self.manufacturer = "WCH"
        self.mpn = "CH334F"
        self.description = "IC USB CONTROLLER 24QFN"
        self.datasheet = "https://www.wch-ic.com/downloads/file/327.html"
        self.lcsc_part_number = "C5187527"
        self.pins = cmp.PinContainer.from_dict(
            {
                14: "DMU",  # USB Upstream port D-
                15: "DPU",  # USB Upstream port D+
                11: "DM1",  # USB 1 downstream port D-
                12: "DP1",  # USB 1 downstream port D+
                9: "DM2",  # USB 2 downstream port D-
                10: "DP2",  # USB 2 downstream port D+
                7: "DM3",  # USB 3 downstream port D-
                8: "DP3",  # USB 3 downstream port D+
                5: "DM4",  # USB 4 downstream port D-
                6: "DP4",  # USB 4 downstream port D+
                4: "XI",  # Crystal oscillator input
                3: "XO",  # Crystal oscillator inverted output
                16: "RESET#",  # External reset input with built-in pull-up, active low
                19: "V5",  # 5V or 3.3V power input, external 1uF or larger capacitor
                20: "VDD33",  # Main power supply, LDO output and 3.3V input. External 0.1uF+10uF decoupling capacitor, or 1uF decoupling capacitor
                0: "GND",  # Common ground terminal (EPAD)
                1: "OVCUR#",  # GANG integral mode line port overcurrent detection input pin.
                24: "PWREN#",  # GANG integral mode line port power output control pins; 1# Downstream port power output control pin, low on
                18: "PSELF",  # Configure power supply mode with built-in pull-up resistor: default high level is self-powered, low level is set for bus power
                22: "LED1",  # LED1: port status  1. PSELF: configure power supply mode during reset, built-in pull-up, default high for self-power, plus pull-down to set low for bus power
                23: "LED2",  # LED2: port status  2. PGANG: configure power overcurrent protection mode during reset, built-in pull-up, default high for overall overcurrent detection and overall power control, plus pull-down to set low for independent overcurrent detection
                13: "LED3",  # LED3: port status  3. SCL: Output for EEPROM clock signal line during reset
                21: "LED4",  # LED4: port status  4. SDA: EEPROM bi-directional data signal line during reset
                2: "NC",  # Empty pins or reserved pins
                17: "NC",  # Empty pins or reserved pins
            },
            self,
        )

        self.i2c = serial.I2C(
            sda=self.pins.by_name("LED4"), scl=self.pins.by_name("LED")
        )
        self.downstream_usb = [
            serial.USB(dm=self.pins.by_name("DM1"), dp=self.pins.by_name("DP1")),
            serial.USB(dm=self.pins.by_name("DM2"), dp=self.pins.by_name("DP2")),
            serial.USB(dm=self.pins.by_name("DM3"), dp=self.pins.by_name("DP3")),
            serial.USB(dm=self.pins.by_name("DM4"), dp=self.pins.by_name("DP4")),
        ]
        self.upstream_usb = serial.USB(
            dm=self.pins.by_name("DMU"), dp=self.pins.by_name("DPU")
        )


def bus_powered_design(xtal_12mhz: cmp.Component):
    ports = ["VBUS", "P3V3", "I2C", "INT"]
    design = sch_lib.Design("BusPoweredHub", "BPH", ports)
    design.default_passive_size = "0402"
    hub = design.add_component(CH334F())
    design.add_decoupling_cap(hub.pins.by_name("VDD33"), cmp.Capacitor(1, 10))
    design.add_decoupling_cap(hub.pins.by_name("VDD33"), cmp.Capacitor(10, 10))
    design.add_decoupling_cap(hub.pins.by_name("V5"), cmp.Capacitor(1, 10))
    design.add_decoupling_cap(hub.pins.by_name("V5"), cmp.Capacitor(10, 10))
    assert xtal_12mhz.frequency == 12.0, "Invalid xtal freq! requires 12MHz"
    design.connect(hub.pins.by_name("XI"), xtal_12mhz.pins[1])
    design.connect(hub.pins.by_name("XO"), xtal_12mhz.pins[2])
    return design

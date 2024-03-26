import enum

import earthground.components as cmp
import earthground.schematic as sch
from earthground.library.footprints.manufacturer_specific import ti
from earthground.library.protocols.serial import I2C


class Package(enum.Enum):
    SSOP = "DGS"
    BGA = "YZF"


PINOUT = {
    Package.SSOP: {
        1: "REG",  # 1.8-V regulator output. A 1-μF capacitor required
        2: "SCL",  # I2C clock
        3: "SDA",  # I2C data
        4: "IN/TRIG",  # Multi-mode Input - if not used, ground it
        5: "EN",  # Device enable
        6: "VDD/NC",  # Optional supply input
        7: "OUT+",  # Positive haptic driver differential output
        8: "GND",  # Supply ground
        9: "OUT-",  # Negative haptic driver differential output
        10: "VDD",  # Supply Input (2 V to 5.2 V). A 1-μF capacitor is required.
    },
    Package.BGA: {
        "A1": "EN",  # Device enable
        "A2": "REG",  # 1.8-V regulator output. A 1-μF capacitor is required.
        "A3": "OUT+",  # Positive haptic driver differential output
        "B1": "IN/TRIG",  # Multi-mode Input - if not used, ground it
        "B2": "SDA",  # I2C data
        "B3": "GND",  # Supply ground
        "C1": "SCL",  # I2C clock
        "C3": "OUT-",  # Negative haptic-driver differential output
        "C2": "VDD",  # Supply input (2 to 5.2 V). A 1-μF capacitor is required
    },
}


class DRV2605L(cmp.Component):
    I2C_ADDRESS = 0x5A

    def __init__(self, package: Package):
        super().__init__()
        self.name = "DRV2605L"
        self.description = f"IC MOTOR DRIVER 2V-5.5V {package.name}"
        self.manufacturer = "Texas Instruments"
        self.mpn = "DRV2605L" + package.value
        self.datasheet = "https://www.ti.com/general/docs/suppproductinfo.tsp?distId=10&gotoUrl=https%3A%2F%2Fwww.ti.com%2Flit%2Fgpn%2Fdrv2605l"
        self.parameters = {
            "Interface": "I2C",
            "Operating Temperature": "-40°C ~ 150°C (TJ)",
            "Output Configuration": "Half Bridge (2)",
            "Voltage - Supply": "2V ~ 5.5V",
            "Applications": "Haptic Feedback",
            "Technology": "Power MOSFET",
            "Voltage - Load": "2V ~ 5.5V",
            "Motor Type": "ERM, LRA",
        }
        self.pins = cmp.PinContainer.from_dict(PINOUT[package], self)
        self.i2c = I2C(sda=self.pins.by_name("SDA"), scl=self.pins.by_name("SCL"))
        self.footprint = ti.DGS_VSSOP(10)


def generate_design(package: Package):
    ports = ["VCC", "GND", "I2C", "SDA", "SCL", "ENABLE", "TRIGGER", "OUT_P", "OUT_N"]
    design = sch.Design("DRV2605L_Design", "Haptic", ports)
    driver = design.add_component(DRV2605L(package))
    design.join_net(driver.pins.by_name("VDD"), "VCC")
    if package == Package.SSOP:
        design.join_net(driver.pins.by_name("VDD/NC"), "VCC")
    design.join_net(driver.pins.by_name("GND"), "GND")
    design.join_net(driver.pins.by_name("IN/TRIG"), "IN")

    # Add voltage supply and decoupling caps
    design.add_decoupling_cap(driver.pins.by_name("VDD"), cmp.Capacitor("1u", 10))
    design.add_decoupling_cap(driver.pins.by_name("REG"), cmp.Capacitor("1u", 10))

    # Assign ports
    design.connect([driver.pins.by_name("VDD"), design.port.vcc])
    design.port.i2c = I2C(sda=design.port.sda, scl=design.port.scl)
    design.connect([driver.pins.by_name("IN/TRIG"), design.port.trigger])
    design.connect([driver.pins.by_name("EN"), design.port.enable])
    design.connect([driver.pins.by_name("OUT+"), design.port.out_p])
    design.connect([driver.pins.by_name("OUT-"), design.port.out_n])
    design.connect([driver.pins.by_name("GND"), design.port.gnd])
    design.validate(skip_footprint_check=True)
    return design

import earthground.schematic as sch
import earthground.components as cmp
import earthground.library.protocols.serial as serial
from earthground.library.footprints import qfn


class CY8CMBR3116(cmp.Component):
    TOTAL_SENSE_PINS = 16

    def __init__(self):
        super().__init__()
        self.name = "CY8CMBR3116"
        self.description = "IC CAP SENSE 24QFN"
        self.mpn = "CY8CMBR3116-LQXI"
        self.manufacturer = "Infineon Technologies"
        self.lead_time = "10 week(s)"
        self.datasheet = "https://www.infineon.com/dgdl/Infineon-CY8CMBR3002_CY8CMBR3102_CY8CMBR3106S_CY8CMBR3108_CY8CMBR3110_CY8CMBR3116-DataSheet-v18_00-EN.pdf?fileId=8ac78c8c7d0d8da4017d0ebe3508318e"
        self.parameters = {
            "Operating Temperature": "-40°C ~ 85°C",
            "Voltage - Supply": "1.8V ~ 5.5V",
            "Current - Supply": "140mA",
            "Number of Inputs": 16,
            "Supplier Device Package": "QFN24",
            "Proximity Detection": True,
        }
        self.pins = cmp.PinContainer.from_dict(
            {
                1: "CS0/PS0",
                2: "CS1/PS1",
                3: "CS2/GUARD",
                4: "CS3",
                5: "CMOD",
                6: "VCC",
                7: "VDD",
                8: "VSS",
                9: "CS15/SH/HI",
                10: "CS14/GPO6",
                11: "CS13/GPO5",
                12: "CS12/GPO4",
                13: "CS11/GPO3",
                14: "CS10/GPO2",
                15: "CS9/GPO1",
                16: "CS8/GPO0",
                17: "CS7",
                18: "CS6",
                19: "CS5",
                20: "CS4",
                21: "SDA",
                22: "SCL",
                23: "HI/BUZ/GPO7",
                24: "XRES",
                25: "EPAD",
            },
            self,
        )
        self.i2c = serial.I2C(sda=self.pins.by_name("SDA"),
                              scl=self.pins.by_name("SCL"))
        self.footprint = qfn.Qfn(pin_count=24,
                                 size=qfn.PackageSize.S4_0MMx4_0MM,
                                 pitch=0.5,
                                 ep=(2.65, 2.65))

    def get_sense_pin(self, index):
        name = f"CS{index}"
        for pin_name in self.pins.names:
            if pin_name.startswith(name):
                return self.pins.by_name(pin_name)


def generate_design(vdd: float, i2c_pullup="4.7k", i2c_series_res="330"):
    assert 1.8 <= vdd <= 5.5, "Invalid voltage range! 1.8V - 5.5V"
    total_pins = CY8CMBR3116.TOTAL_SENSE_PINS
    ports = [f"CS{i}"
             for i in range(total_pins)] + ["VDD", "GND", "I2C", "nRESET"]
    design = sch.Design("Mbr3Design", "MBR", ports)
    mbr3 = design.add_component(CY8CMBR3116())

    # Connect power
    for ground_pin in ["VSS", "EPAD"]:
        design.join_net(mbr3.pins.by_name(ground_pin), "GND")
    design.port.gnd = mbr3.pins.by_name("VSS")
    design.port.vdd = mbr3.pins.by_name("VDD")
    design.port.nreset = mbr3.pins.by_name("XRES")

    # Decoupling capacitors
    design.add_decoupling_cap(mbr3.pins.by_name("CMOD"),
                              cmp.Capacitor("2.2n", 10))
    design.add_decoupling_cap(mbr3.pins.by_name("VDD"),
                              cmp.Capacitor("1u", 10))
    design.add_decoupling_cap(mbr3.pins.by_name("VDD"),
                              cmp.Capacitor("0.1u", 10))
    if vdd < 1.89:
        design.connect([mbr3.pins.by_name("VDD"), mbr3.pins.by_name("VCC")])
    else:
        design.add_decoupling_cap(mbr3.pins.by_name("VCC"),
                                  cmp.Capacitor("0.1u", 10))

    # I2C series resistors
    design.port.i2c = mbr3.i2c
    if i2c_series_res:
        sda_r = design.add_component(cmp.Resistor(i2c_series_res))
        scl_r = design.add_component(cmp.Resistor(i2c_series_res))
        design.connect([sda_r.pins[1], mbr3.pins.by_name("SDA")], "SDA")
        design.connect([scl_r.pins[1], mbr3.pins.by_name("SCL")], "SCL")
        design.port.i2c = serial.I2C(sda=sda_r.pins[2], scl=scl_r.pins[2])

    # Pull-up resistors for I2C
    if i2c_pullup:
        design.add_series_res(mbr3.pins.by_name("VDD"), i2c_pullup,
                              mbr3.pins.by_name("SCL"))
        design.add_series_res(mbr3.pins.by_name("VDD"), i2c_pullup,
                              mbr3.pins.by_name("SDA"))

    # Add CapSense pins to ports
    for i in range(total_pins):
        design.port[f"cs{i}"] = mbr3.get_sense_pin(i)
    return design

import earthground.components as cmp
import earthground.footprints.tssop as tssop
import earthground.schematic as sch
import earthground.standard_values as sv
from earthground.library.protocols.serial import I2C

GPIO_COUNT = 16


class TCA9535PWR(cmp.Component):
    def __init__(self):
        super().__init__()
        self.name = "TCA9535PWR"
        self.detailed_description = "I/O Expander 16 I²C, SMBus 400 kHz 24-TSSOP"
        self.manufacturer = "Texas Instruments"
        self.lead_time = sv.weeks(typ=6)
        self.mpn = "TCA9535PWR"
        self.datasheet = "https://www.ti.com/general/docs/suppproductinfo.tsp?distId=10&gotoUrl=https%3A%2F%2Fwww.ti.com%2Flit%2Fgpn%2Ftca9535"
        self.description = "IC XPND 400KHZ I2C SMBUS 24TSSOP"
        self.parameters = {
            "Output Type": "Push-Pull",
            "Number of I/O": "16",
            "Operating Temperature": "-40°C ~ 85°C",
            "Voltage - Supply": "1.65V ~ 5.5V",
            "Clock Frequency": "400 kHz",
            "Interrupt Output": "Yes",
            "Supplier Device Package": "24-TSSOP",
        }
        self.pins = cmp.PinContainer.from_dict(
            {
                21: "A0",
                2: "A1",
                3: "A2",
                12: "GND",
                1: "INT",
                4: "P00",
                5: "P01",
                6: "P02",
                7: "P03",
                8: "P04",
                9: "P05",
                10: "P06",
                11: "P07",
                13: "P10",
                14: "P11",
                15: "P12",
                16: "P13",
                17: "P14",
                18: "P15",
                19: "P16",
                20: "P17",
                22: "SCL",
                23: "SDA",
                24: "VCC",
            },
            self,
        )
        self.i2c = I2C(sda=self.pins.by_name("SDA"), scl=self.pins.by_name("SCL"))
        self.footprint = tssop.TSSOP(
            count=24,
            width=tssop.Width.W4_4MM,
            pitch=tssop.Pitch.P0_65MM,
            pad_size=(1.475, 0.4),
        )

    def gpio(self, index):
        bank = int(index / 8)
        port = index % 8
        return self.pins.by_name(f"P{bank}{port}")

    @property
    def address(self):
        high_net = self.pins.by_name("VCC").net
        low_net = self.pins.by_name("GND").net
        address = 1 << 6
        for bit in range(3):
            pin = self.pins.by_name(f"A{bit}")
            if pin.net is high_net:
                address |= 1 << bit
            elif pin.net is not low_net:
                raise ValueError(
                    f"Address pin {pin.name} must be connected to VCC or GND"
                )
        return address


def generate_design(address=0, interrupt_pullup="10k", decoupling_cap=None):
    if not (0 <= address <= 7):
        raise ValueError(f"Invalid address {address}; range 0-7")
    ports = [f"IO{i}" for i in range(GPIO_COUNT)] + ["VCC", "GND", "I2C", "INT"]
    design = sch.Design("Tca9535Design", "EXPANDER", ports)
    expander = design.add_component(TCA9535PWR())
    design.join_net(expander.pins.by_name("VCC"), "VCC")
    design.join_net(expander.pins.by_name("GND"), "GND")

    # Set address pins
    for bit in range(3):
        net_name = "VCC" if address & (1 << bit) else "GND"
        design.join_net(expander.pins.by_name(f"A{bit}"), net_name)

    # Add decoupling cap and interrupt pull-up
    if decoupling_cap is None:
        decoupling_cap = cmp.Capacitor("1u", 10)
    expander.pins.by_name("VCC").add_decoupling_capacitor(decoupling_cap)
    if interrupt_pullup:
        design.add_series_res(
            pin1=expander.pins.by_name("INT"),
            ohms=interrupt_pullup,
            pin2=expander.pins.by_name("VCC"),
            net_name="I2C_INT",
        )

    # Assign ports
    port_connections = {
        name: expander.pins.by_name(name) for name in ["VCC", "GND", "INT"]
    }
    port_connections.update(
        {f"IO{index}": expander.gpio(index) for index in range(GPIO_COUNT)}
    )
    design.set_ports(port_connections)
    design.port.i2c = expander.i2c
    return design

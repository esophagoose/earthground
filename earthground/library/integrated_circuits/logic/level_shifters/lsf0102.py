import enum
from collections import namedtuple

import earthground.components as cmp
from earthground.ratings import Ratings
import earthground.schematic as sch
import earthground.standard_values as sv

COMPONENT_CREATOR_VERSION = "0.0.1"

PartNumberParams = namedtuple(
    "PartNumberParams",
    ["package_drawing", "package_type"],
)

PINOUT = {
    "LEADED": {
        3: "A1",  # Auto-Bidirectional Data port
        4: "A2",  # Auto-Bidirectional Data port
        6: "B1",  # Auto-Bidirectional Data port
        5: "B2",  # Auto-Bidirectional Data port
        8: "EN",  # Enable input, connect pull-up
        1: "GND",  # Ground
        2: "VREF_A",  # Reference supply voltage
        7: "VREF_B",  # Reference supply voltage
    },
    "BGA": {
        "C1": "A1",  # Auto-Bidirectional Data port
        "D1": "A2",  # Auto-Bidirectional Data port
        "C2": "B1",  # Auto-Bidirectional Data port
        "D2": "B2",  # Auto-Bidirectional Data port
        "B1": "VREF_A",  # Reference supply voltage
        "B2": "VREF_B",  # Reference supply voltage
        "A2": "EN",  # Enable input, connect pull-up
        "A1": "GND",  # Ground
    },
}


class LSF0102PartNumbers(enum.Enum):
    """LSF0102 Part Number Configurations"""

    LSF0102DCTR = PartNumberParams(package_type="SSOP", package_drawing="DCT")
    LSF0102DCUR = PartNumberParams(package_type="VSSOP", package_drawing="DCU")
    LSF0102DDFR = PartNumberParams(package_type="SOT-23-THIN", package_drawing="DDF")
    LSF0102DQER = PartNumberParams(package_type="X2SON", package_drawing="DQE")
    LSF0102DTMR = PartNumberParams(package_type="X2SON", package_drawing="DTM")
    LSF0102YZTR = PartNumberParams(package_type="DSBGA", package_drawing="YZT")


class LSF0102(cmp.Component):
    """
    The LSF0102 is a 2-channel auto-bidirectional multi-voltage level translator designed
    for open-drain and push-pull applications, supporting a wide range of voltage levels and
    up to 100MHz data rates. It facilitates bidirectional voltage translation without a
    direction pin, making it suitable for various interfaces in telecom and industrial
    applications.
    """

    abs_max = Ratings(
        vi=sv.volts(-0.5, max=7),  # Input voltage
        vi_o=sv.volts(-0.5, max=7),  # Input/output voltage
        i_channel=sv.ValueBounds("mA", min=sv.UNBOUNDED, max=128),
        i_ik=sv.ValueBounds("mA", min=sv.UNBOUNDED, max=-50),
        tj=sv.celsius(min=sv.UNBOUNDED, max=150),
        tstg=sv.celsius(-65, max=150),
    )
    recommended = Ratings(
        vi_o=sv.volts(0, max=5.5),
        vref_a=sv.volts(0.95, max=5.5),
        vref_b=sv.volts(1.8, max=5.5),
        v_en=sv.volts(0, max=5.5),
        i_pass=sv.ValueBounds("mA", min=sv.UNBOUNDED, max=64),
        ta=sv.celsius(-40, max=125),
        vik=sv.volts(min=sv.UNBOUNDED, max=-1.2),
        i_ih=sv.ValueBounds("µA", min=sv.UNBOUNDED, max=5),
        i_cc=sv.ValueBounds("µA", typ=6),
        ci_ref=sv.ValueBounds("pF", typ=11),
        ci_en=sv.ValueBounds("pF", typ=11),
        cio_off=sv.ValueBounds("pF", typ=4, max=6),
        cio_on=sv.ValueBounds("pF", typ=10.5, max=12.5),
    )

    def __init__(self, full_part_number: LSF0102PartNumbers):
        super().__init__()
        self.manufacturer = "Texas Instruments"
        self.description = "Voltage Level Translator Bidirectional 1 Circuit 2 Channel"
        self.datasheet = "https://www.ti.com/general/docs/suppproductinfo.tsp?distId=10&gotoUrl=https%3A%2F%2Fwww.ti.com%2Flit%2Fgpn%2Flsf0102"
        self.lead_time = 6.0
        self.state = "Active"
        self.parameters = full_part_number.value
        pinout = PINOUT["LEADED"]
        if full_part_number.value.package_type == "DSBGA":
            pinout = PINOUT["BGA"]
        specs = {}
        for index, name in pinout.items():
            if name in ("A1", "A2", "B1", "B2"):
                spec = cmp.DigitalPinSpec.bidirectional(
                    name=name,
                    voltage_abs_max=self.abs_max["vi_o"],
                    voltage_operating=self.recommended["vi_o"],
                )
            elif name == "EN":
                spec = cmp.DigitalPinSpec.input(
                    name=name,
                    voltage_abs_max=self.abs_max["vi"],
                    voltage_operating=self.recommended["v_en"],
                )
            elif name == "GND":
                spec = cmp.PowerPinSpec(
                    name=name,
                    role=cmp.PowerRole.GROUND,
                    abs_max=sv.volts(0, typ=0, max=0),
                    voltage=sv.volts(0, typ=0, max=0),
                )
            else:
                rating = "vref_a" if name == "VREF_A" else "vref_b"
                spec = cmp.PowerPinSpec(
                    name=name,
                    role=cmp.PowerRole.INPUT,
                    abs_max=self.abs_max["vi"],
                    voltage=self.recommended[rating],
                )
            specs[index] = spec
        self.pins = cmp.PinContainer.from_dict(specs, self)


def generate_design(
    mpn: LSF0102PartNumbers,
    r_bias=cmp.Resistor("200k"),
    c_filter=cmp.Capacitor("0.1uF", 10),
):
    """
    Generate the reference design for the LSF0102 level translator as shown in the provided schematic.
    Default parameters match the example: 3.3 V supply, 1.8 V VREF_A, bias resistor 200kΩ, and filter cap 0.1uF.
    Pull-up resistors on A and B side IO lines are optional and used if needed depending on specific application.
    """

    ports = ["VA", "VB", "A1", "A2", "B1", "B2", "GND"]
    design = sch.Design("Lsf0102ReferenceDesign", "LSF0102", ports)
    lsf = LSF0102(mpn)
    design.add_component(lsf)

    # Power supply net
    design.connect(
        [lsf.pins.by_name("VREF_B"), lsf.pins.by_name("EN"), r_bias.pins[1]], "VREF_B"
    )
    design.add_decoupling_capacitor(c_filter, "VREF_B")
    design.connect([r_bias.pins[2], design.port.vb])
    design.connect([lsf.pins.by_name("VREF_A"), design.port.va])
    design.connect([lsf.pins.by_name("GND"), design.port.gnd])

    # Ports output for reference
    design.port.a1 = lsf.pins.by_name("A1")
    design.port.a2 = lsf.pins.by_name("A2")
    design.port.b1 = lsf.pins.by_name("B1")
    design.port.b2 = lsf.pins.by_name("B2")

    return design

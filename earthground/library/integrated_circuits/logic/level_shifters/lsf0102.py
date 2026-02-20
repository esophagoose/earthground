import enum
from collections import namedtuple

import earthground.components as cmp
import earthground.schematic as sch
import earthground.standard_values as sv

COMPONENT_CREATOR_VERSION = "0.0.1"

AbsMax = namedtuple("AbsMax", ["vi", "vi_o", "i_channel", "i_ik", "tj", "tstg"])
Recommended = namedtuple(
    "Recommended",
    [
        "vi_o",
        "vref_a",
        "vref_b",
        "v_en",
        "i_pass",
        "ta",
        "vik",
        "i_ih",
        "i_cc",
        "ci_ref",
        "ci_en",
        "cio_off",
        "cio_on",
    ],
)
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

    abs_max = AbsMax(
        vi=sv.ValueBounds(min=-0.5, max=7, units="V"),  # Input voltage
        vi_o=sv.ValueBounds(min=-0.5, max=7, units="V"),  # Input/output voltage
        i_channel=sv.ValueBounds(max=128, units="mA"),  # Continuous channel current
        i_ik=sv.ValueBounds(max=-50, units="mA"),  # Input clamp current
        tj=sv.ValueBounds(max=150, units="°C"),  # Junction Temperature
        tstg=sv.ValueBounds(min=-65, max=150, units="°C"),  # Storage temperature range
    )
    recommended = Recommended(
        vi_o=sv.ValueBounds(min=0, max=5.5, units="V"),  # Input/output voltage
        vref_a=sv.ValueBounds(min=0.95, max=5.5, units="V"),  # Reference voltage
        vref_b=sv.ValueBounds(min=1.8, max=5.5, units="V"),  # Reference voltage
        v_en=sv.ValueBounds(min=0, max=5.5, units="V"),  # Enable voltage
        i_pass=sv.ValueBounds(max=64, units="mA"),  # Pass transistor current
        ta=sv.ValueBounds(
            min=-40, max=125, units="°C"
        ),  # Operating free-air temperature
        vik=sv.ValueBounds(max=-1.2, units="V"),  # I = -18mA, I, VEN = 0
        i_ih=sv.ValueBounds(max=5.0, units="µA"),  # VI = 5V, VEN = 0
        i_cc=sv.ValueBounds(
            typ=6, units="µA"
        ),  # VREF_B = VEN = 5.5V, VREF_A = 4.5V, I O = 0, V I = VCC or GND
        ci_ref=sv.ValueBounds(typ=11, units="pF"),  # VI = 3V or 0
        ci_en=sv.ValueBounds(typ=11, units="pF"),  # VI = 3V or 0
        cio_off=sv.ValueBounds(typ=4.0, max=6.0, units="pF"),  # VO = 3V or 0
        cio_on=sv.ValueBounds(typ=10.5, max=12.5, units="pF"),  # VO = 3V or 0, VEN = 3V
    )

    def __init__(self, full_part_number: LSF0102PartNumbers):
        super().__init__()
        self.manufacturer = "Texas Instruments"
        self.description = "Voltage Level Translator Bidirectional 1 Circuit 2 Channel"
        self.datasheet = "https://www.ti.com/general/docs/suppproductinfo.tsp?distId=10&gotoUrl=https%3A%2F%2Fwww.ti.com%2Flit%2Fgpn%2Flsf0102"
        self.lead_time = 6.0
        self.state = "Active"
        self.parameters = full_part_number.value
        self.pins = cmp.PinContainer.from_dict(PINOUT["LEADED"], self)
        if full_part_number.value.package_type == "DSBGA":
            self.pins = cmp.PinContainer.from_dict(PINOUT["BGA"], self)


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

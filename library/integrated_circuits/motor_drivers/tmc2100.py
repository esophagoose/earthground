import enum

import common.components as cmp
import common.schematic as sch


class ChopperMode(enum.Enum):
    SPREAD_CYCLE = 1
    STEALTH_CHOP = 2


class ClockSource(enum.Enum):
    INTERNAL = 1
    EXTERNAL = 2


MICROSTEPS = [1, 2, 4, 16]


class TMC2100_LA_T(cmp.Component):
    def __init__(self):
        super().__init__()
        self.detailed_description = (
            "Bipolar Motor Driver Power MOSFET Logic 36-QFN (5x6)"
        )
        self.manufacturer = "Analog Devices Inc."
        self.lead_time = "18 week(s)"
        self.mpn = "TMC2100-LA-T"
        self.datasheet = ""
        self.description = "IC MTR DRV BIPOLAR 5.5-46V 36QFN"
        self.parameters = {
            "Function": "Driver - Fully Integrated, Control and Power Stage",
            "Current - Output": "1.2A",
            "Operating Temperature": "-40°C ~ 125°C (TJ)",
            "Output Configuration": "Half Bridge (4)",
            "Voltage - Supply": "5.5V ~ 46V",
            "Voltage - Load": "5.5V ~ 46V",
            "Supplier Device Package": "36-QFN (5x6)",
            "Motor Type - Stepper": "Bipolar",
            "Step Resolution": "1 ~ 1/256",
        }
        self.pins = cmp.PinContainer.from_dict(
            {
                1: "CLK",  # CLK input or tie to GND for internal clock
                2: "CFG3",  # Configuration input
                3: "CFG2",  # Configuration input
                4: "CFG1",  # Configuration input
                5: "CFG0",  # Configuration input
                6: "STEP",  # STEP input
                7: "DIR",  # DIR input
                8: "VCC_IO",  # 3.3 - 5 V IO supply voltage for all digital pins.
                9: "DNC",  # Do not connect. Leave open!
                10: "GNDD",  # Digital GND. Connect to GND
                11: "N.C.",  # Unused pin, connect to GND
                12: "GNDP",  # Power GND. Connect to GND plane near pin.
                13: "OB1",  # Motor coil B output 1
                14: "BRB",  # Sense resistor connection for coil B or tie to GND when using internal sense resistors.
                15: "OB2",  # Motor coil B output 2
                16: "VS",  # Motor supply voltage. Provide filter near pin to GNDP pin
                17: "DNC",  # Do not connect. Leave open!
                18: "CFG4",  # Configuration input
                19: "CFG5",  # Configuration input
                20: "ERROR",  # Driver error (Open drain output with 50k resistor to 2.5V)
                21: "INDEX",  # Microstep table position index (Open drain output with 100k pulldown resistor – use sufficient pullup resistor of 22k max.)
                22: "CFG6_ENN",  # Enable input (high to disable) and power down configuration
                23: "AIN_IREF",  # Analog reference voltage for current scaling or reference current for use of internal sense resistors (optional mode)
                24: "GNDA",  # Analog GND. Tie to GND plane.
                25: "5VOUT",  # Output of internal 5 V regulator. Attach 2.2 μF to 10μF ceramic capacitor to GNDA near to pin for best performance.
                26: "VCC",  # 5V supply input for digital circuitry within chip and charge pump. Attach 470nF capacitor to GND (GND plane). Supply by 5VOUT. Use a 2.2 or 3.3 Ohm resistor for decoupling noise from 5VOUT. When using an external supply, make sure, that VCC comes up before or in parallel to 5VOUT!
                27: "CPO",  # Charge pump capacitor output.
                28: "CPI",  # Charge pump capacitor input. Tie to CPO using 22 nF 50 V capacitor.
                29: "VCP",  # Charge pump voltage. Tie to VS using 100 nF 16 V capacitor.
                30: "VSA",  # Analog supply voltage for 5V regulator. Normally tied to VS. Provide a 100 nF filtering capacitor.
                31: "VS",  # Motor supply voltage. Provide filtering capacity near pin with short loop to nearest GNDP pin (respectively via GND plane).
                32: "OA2",  # Motor coil A output 2
                33: "BRA",  # Sense resistor connection for coil A. Place sense resistor to GND near pin. Tie to GND when using internal sense resistors.
                34: "OA1",  # Motor coil A output 1
                35: "GNDP",  # Power GND
                36: "TST_MODE",  # Test mode input - tie to GND
                37: "EP",  # Exposed die pad - connect to GND plane. Provide vias for heat transfer
            },
            self,
        )

    def get_cfg1_and_cfg2(
        self, microsteps: int, interpolation: bool, chopper_mode: ChopperMode
    ):
        assert microsteps in MICROSTEPS, "Invalid microstep config!"
        if microsteps == 1 and not interpolation:
            return "GND", "GND"  # Fullstep, SpreadCycle
        elif microsteps == 2 and not interpolation:
            return "VCC_IO", "GND"
        elif microsteps == 2 and interpolation:
            return None, "GND"
        elif microsteps == 4 and not interpolation:
            return "GND", "VCC_IO"
        elif microsteps == 16 and not interpolation:
            return "VCC_IO", "VCC_IO"
        elif microsteps == 4 and interpolation:
            return None, "VCC_IO"
        elif (
            microsteps == 16
            and interpolation
            and chopper_mode == ChopperMode.SPREAD_CYCLE
        ):
            return "VCC_IO", None
        elif (
            microsteps == 4
            and interpolation
            and chopper_mode == ChopperMode.STEALTH_CHOP
        ):
            return "VCC_IO", None
        elif microsteps == 16 and interpolation:
            return None, None
        else:
            raise ValueError("Invalid config!")

    def validate(self):
        assert self.pins.by_name("CLK").connections, "Need to connect CLK!"
        for dnc in self.pins.all_with_name("DNC"):
            assert not dnc.connections, "DNC connected!"
        for nc in self.pins.all_with_name("NC"):
            assert "GND" in nc.connections[0].name, "Connect NC pins to GND"


class ChopperOffTime(enum.Enum):
    LOW = "GND"  # 140 t_clk - Recommended
    MEDIUM = "VCC_IO"  # 236 t_clk
    HIGH = None  # 332 t_clk

    @property
    def pin(self):
        return "CFG0"


class ChopperHysteresis(enum.Enum):
    LOW = "GND"  # Recommended
    MEDIUM = "VCC_IO"
    HIGH = None

    @property
    def pin(self):
        return "CFG4"


class ChopperBlankTime(enum.Enum):
    LOW = "GND"  # Best performance for StealthChop
    MEDIUM = "VCC_IO"  # Recommended
    HIGH = None  # For high-capacitive load

    @property
    def pin(self):
        return "CFG5"


class CurrentSetting(enum.Enum):
    INT_AIN_REF__EXT_RES = "GND"
    INT_AIN_REF__INT_RES = "VCC_IO"
    EXT_AIN_REF__EXT_RES = None

    @property
    def pin(self):
        return "CFG3"


def generate_design(
    driver=TMC2100_LA_T(),
    clock=None,
    current_limit=None,
    sense_resistor=None,
    use_internal_5v=True,
    blank_time=ChopperBlankTime.MEDIUM,
    slow_decay_duration=ChopperOffTime.LOW,
    chopper_hysteresis=ChopperHysteresis.LOW,
    current_setting=CurrentSetting.INT_AIN_REF__INT_RES,
):
    ports = ["vmotor", "vio", "gnd", "enable", "cfg1", "cfg2"]
    schematic = sch.Design("TMC2100Design", "MOTOR", ports)
    grounded_pins = ["EP", "GNDP", "GNDD", "GNDA", "NC", "TST_MODE"]
    vio = driver.pins.by_name("VCC_IO")
    if not clock:
        grounded_pins.append("CLK")
    else:
        raise NotImplementedError("External clock not supported")
    schematic.add_series_res(vio, "47k", driver.pins.by_name("ERROR"))
    schematic.add_series_res(vio, "10k", driver.pins.by_name("INDEX"))
    schematic.add_decoupling_cap(driver.pins.by_name("5VOUT"),
                                 cmp.Capacitor("10u", 10))
    # Charge pumps
    charge_pump = cmp.Capacitor("22n", 50)
    schematic.connect([driver.pins.by_name("CPI"), charge_pump.pins[1]])
    schematic.connect([driver.pins.by_name("CPO"), charge_pump.pins[2]])
    motor_cp = cmp.Capacitor("100n", 50)
    schematic.connect([driver.pins.by_name("VCP"), motor_cp.pins[1]])
    schematic.connect([driver.pins.by_name("VS"), motor_cp.pins[2]])
    # Decoupling capacitor
    schematic.add_decoupling_cap(driver.pins.by_name("VSA"),
                                 cmp.Capacitor("100n", 10))
    for pin in driver.pins.all_with_name("VS"):
        schematic.add_decoupling_cap(pin, cmp.Capacitor("1u", 50))
    schematic.add_decoupling_cap(driver.pins.by_name("VS"),
                                 cmp.Capacitor("47u", 50))
    schematic.add_decoupling_cap(driver.pins.by_name("VCC"),
                                 cmp.Capacitor("47u", 50))
    # Set configuration pins
    #   CFG0, CFG3, CFG4, CFG5
    for config in [
            slow_decay_duration,
            blank_time,
            chopper_hysteresis,
            current_setting,
    ]:
        if config.value:
            pin = driver.pins.by_name(blank_time.value)
            schematic.connect([pin, driver.pins.by_name(config.pin)])
    #  CFG1, CFG2, CFG6
    schematic.port.cfg1 = driver.pins.by_name("CFG1")
    schematic.port.cfg2 = driver.pins.by_name("CFG2")
    schematic.port.enable = driver.pins.by_name("CFG6_ENN")

    if sense_resistor:
        schematic.add_series_res(driver.pins.by_name("BRA"), sense_resistor,
                                 driver.pins.by_name("GNDP"))
        schematic.add_series_res(driver.pins.by_name("BRB"), sense_resistor,
                                 driver.pins.by_name("GNDP"))
    else:
        grounded_pins.append("BRA")
        grounded_pins.append("BRB")

    if current_limit:
        driver.pins.by_name("AIN_IREF")
    if use_internal_5v:
        schematic.add_series_res(driver.pins.by_name("5VOUT"), 2.2,
                                 driver.pins.by_name("VCC"))
    for grounded_pin in driver.pins.all_with_name(grounded_pins):
        schematic.join_net(grounded_pin, "GND")

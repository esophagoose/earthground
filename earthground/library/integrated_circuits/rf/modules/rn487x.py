import enum
from collections import namedtuple

import earthground.components as cmp
import earthground.standard_values as sv

COMPONENT_CREATOR_VERSION = "0.0.1"

Recommended = namedtuple(
    "Recommended",
    [
        "v_supply",
        "v_il",
        "v_ih",
        "v_ol",
        "v_oh",
        "t_reset_low",
        "r_pull_up",
        "r_pull_down",
    ],
)
PartNumberParams = namedtuple(
    "PartNumberParams", ["has_antenna", "pin_count", "shielding", "temperature_range"]
)

PINOUT = {
    "RN4870U": {
        1: "GND",  # Ground reference.
        2: "VBAT",  # Positive supply input. Range: 1.9V ~ 3.6V.
        3: "P2_2",  # GPIO, PWM1 (only for RN4870), Default: Input; pulled high.
        4: "VDD_IO",  # I/O positive supply. Do not connect.
        5: "VDD_IO",  # I/O positive supply. Do not connect.
        6: "ULPC_O",  # 1.2V ULPC LDO output, diagnostic purposes.
        7: "P2_3",  # GPIO, PWM2 (only for RN4870), Default: Input; pulled high.
        8: "BK_O",  # 1.55V Buck power supply output. Do not connect.
        9: "P2_7",  # UART_TX_IND output pin, TX indication.
        10: "P1_1",  # GPIO; Input; BLEDK_STATUS1_IND.
        11: "P1_2",  # GPIO; Input; I2C SCL pin.
        12: "P1_3",  # GPIO; Input; I2C SDA pin.
        13: "P0_0",  # GPIO; Input; UART_CTS pin.
        14: "P1_0",  # GPIO; Input; BLEDK_STATUS2_IND.
        15: "P3_6",  # GPIO; Input; UART_RTS pin.
        16: "P2_0",  # System config input; Application mode.
        17: "P2_4",  # GPIO; Input; Default high.
        18: "NC",  # No connection.
        19: "RST_N",  # Module Reset; active-low.
        20: "UART_RX",  # UART data input.
        21: "UART_TX",  # UART data output.
        22: "P3_1",  # GPIO; RSSI_IND, SPI NCS Bus.
        23: "P3_2",  # GPIO; LINK_DROP, SPI MISO pin.
        24: "P3_3",  # GPIO; UART RX indication, SPI MOSI.
        25: "P3_4",  # GPIO; PAIRING_KEY, SPI SCLK pin.
        26: "P3_5",  # GPIO; LED1; on/off indication.
        27: "P0_7",  # GPIO; LOW_BATTERY_INDICATOR pin.
        28: "P0_2",  # AD2, LED0; On/Off mode indication.
        29: "GND",  # Ground reference.
        30: "BT_RF",  # External antenna connection (50 Ohms).
    },
    "RN4870": {
        1: "GND",  # Ground reference.
        2: "GND",  # Ground reference.
        3: "GND",  # Ground reference.
        4: "VBAT",  # Positive supply input. Range: 1.9V ~ 3.6V.
        5: "P2_2",  # GPIO, PWM1 (only for RN4870), Default: Input; pulled high.
        6: "VDD_IO",  # I/O positive supply. Do not connect.
        7: "VDD_IO",  # I/O positive supply. Do not connect.
        8: "ULPC_O",  # 1.2V ULPC LDO output, diagnostic purposes.
        9: "P2_3",  # GPIO, PWM2 (only for RN4870), Default: Input; pulled high.
        10: "BK_O",  # 1.55V Buck power supply output. Do not connect.
        11: "P2_7",  # UART_TX_IND output pin, TX indication.
        12: "P1_1",  # GPIO; Input; BLEDK_STATUS1_IND.
        13: "P1_2",  # GPIO; Input; I2C SCL pin.
        14: "P1_3",  # GPIO; Input; I2C SDA pin.
        15: "P0_0",  # GPIO; Input; UART_CTS pin.
        16: "P1_0",  # GPIO; Input; BLEDK_STATUS2_IND.
        17: "P3_6",  # GPIO; Input; UART_RTS pin.
        18: "P2_0",  # System config input; Application mode.
        19: "P2_4",  # GPIO; Input; Default high.
        20: "NC",  # No connection.
        21: "RST_N",  # Module Reset; active-low.
        22: "UART_RX",  # UART data input.
        23: "UART_TX",  # UART data output.
        24: "P3_1",  # GPIO; RSSI_IND, SPI NCS Bus.
        25: "P3_2",  # GPIO; LINK_DROP, SPI MISO pin.
        26: "P3_3",  # GPIO; UART RX indication, SPI MOSI.
        27: "P3_4",  # GPIO; PAIRING_KEY, SPI SCLK pin.
        28: "P3_5",  # GPIO; LED1; on/off indication.
        29: "P0_7",  # GPIO; LOW_BATTERY_INDICATOR pin.
        30: "P0_2",  # AD2, LED0; On/Off mode indication.
        31: "GND",  # Ground reference.
        32: "GND",  # Ground reference.
        33: "GND",  # Ground reference.
    },
    "RN4871U": {
        1: "BT_RF",  # External antenna connection (50 Ohms).
        2: "P1_2",  # GPIO; Input; I2C SCL pin.
        3: "P1_3",  # GPIO; Input; I2C SDA pin.
        4: "UART_TX",  # UART data output.
        5: "UART_RX",  # UART data input.
        6: "P3_6",  # GPIO; Input; UART_RTS pin.
        7: "RST_N",  # Module Reset; active-low.
        8: "P0_0",  # GPIO; Input; UART_CTS pin.
        9: "P0_2",  # AD2, LED0; On/Off mode indication.
        10: "BK_IN",  # Buck power supply input.
        11: "VBAT",  # Positive supply input. Range: 1.9V ~ 3.6V.
        12: "GND",  # Ground reference.
        13: "P1_6",  # Configurable pin.
        14: "P1_7",  # Configurable pin.
        15: "P2_7",  # UART_TX_IND output pin, TX indication.
        16: "P2_0",  # System config input; Application mode.
        17: "GND",  # Ground reference.
    },
    "RN4871": {
        2: "GND",  # Ground reference.
        3: "P1_2",  # GPIO; Input; I2C SCL pin.
        4: "P1_3",  # GPIO; Input; I2C SDA pin.
        5: "P1_7",  # Configurable pin.
        6: "P1_6",  # Configurable pin.
        7: "UART_RX",  # UART data input.
        8: "UART_TX",  # UART data output.
        9: "P3_6",  # GPIO; Input; UART_RTS pin.
        10: "RST_N",  # Module Reset; active-low.
        11: "P0_0",  # GPIO; Input; UART_CTS pin.
        12: "P0_2",  # AD2, LED0; On/Off mode indication.
        13: "GND",  # Ground reference.
        14: "VBAT",  # Positive supply input. Range: 1.9V ~ 3.6V.
        15: "P2_7",  # UART_TX_IND output pin, TX indication.
        16: "P2_0",  # System config input; Application mode.
    },
}


class RN487xPartNumbers(enum.Enum):
    """RN4871 Part Number Configurations"""

    RN4870_I_RMXXX = PartNumberParams(
        has_antenna=True,
        shielding=True,
        temperature_range="-40°C to +85°C",
        pin_count=33,
    )
    RN4870_V_RMXXX = PartNumberParams(
        has_antenna=True,
        shielding=True,
        temperature_range="-20°C to +70°C",
        pin_count=33,
    )
    RN4870U_V_RMXXX = PartNumberParams(
        has_antenna=False,
        shielding=False,
        temperature_range="-20°C to +70°C",
        pin_count=30,
    )
    RN4871_I_RMXXX = PartNumberParams(
        has_antenna=True,
        shielding=True,
        temperature_range="-40°C to +85°C",
        pin_count=16,
    )
    RN4871_V_RMXXX = PartNumberParams(
        has_antenna=True,
        shielding=True,
        temperature_range="-20°C to +70°C",
        pin_count=16,
    )
    RN4871U_V_RMXXX = PartNumberParams(
        has_antenna=False,
        shielding=False,
        temperature_range="-20°C to +70°C",
        pin_count=17,
    )


class RN487x(cmp.Component):
    """
    The RN4870/71 is a Bluetooth ® Low Energy Module qualified for Bluetooth SIG v5.0 and
    supports various applications including health devices, IoT sensor tags, and smart home
    solutions. It features a compact design, on-board BLE stack, and remote configuration
    capabilities, making it versatile for various use cases.
    """

    # Supply Voltage (VDD)
    v_supply = sv.ValueBounds(min=1.9, max=3.6, units="V")
    # Input Logic Levels Low (VIL)
    v_il = sv.ValueBounds(min=0, max=0.3 * v_supply, units="V")
    # Input Logic Levels High (VIH)
    v_ih = sv.ValueBounds(min=0.7 * v_supply, max=v_supply, units="V")
    # Output Logic Levels Low (VOL)
    v_ol = sv.ValueBounds(min=0, max=0.2 * v_supply, units="V")
    # Output Logic Levels High (VOH)
    v_oh = sv.ValueBounds(min=0.8 * v_supply, max=v_supply, units="V")
    # Reset Low Duration
    t_reset_low = sv.ValueBounds(min=63, units="ns")
    # Pull-up Resistance
    r_pull_up = sv.ValueBounds(min=34, typ=48, max=74, units="k Ω")
    # Pull-Down Resistance
    r_pull_down = sv.ValueBounds(min=29, typ=47, max=86, units="k Ω")

    def __init__(self, full_part_number: RN487xPartNumbers):
        super().__init__()
        self.manufacturer = "Microchip Technology"
        self.description = "Bluetooth Bluetooth v5.0 Transceiver Module 2.402GHz ~ 2.48GHz Integrated, Chip Surface"
        self.datasheet = "https://ww1.microchip.com/downloads/aemDocuments/documents/WSG/ProductDocuments/DataSheets/RN4870-71-Bluetooth-Low-Energy-Module-DS50002489.pdf"
        self.lead_time = 12.0
        self.state = "Active"
        self.parameters = full_part_number.value
        self.base_mpn = full_part_number.name.split("_")[0]
        self.pins = cmp.PinContainer.from_dict(PINOUT[self.base_mpn], self)
        self.programming_interface = [
            self.pins.by_name("P2_0"),
            self.pins.by_name("VBAT"),
            self.pins.by_name("UART_RX"),
            self.pins.by_name("UART_TX"),
            self.pins.by_name("GND"),
        ]

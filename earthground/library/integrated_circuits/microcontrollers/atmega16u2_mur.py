import earthground.components as cmp
from earthground.library.protocols import serial


class ATMEGA16U2_MU(cmp.Component):
    def __init__(self):
        super().__init__()
        self.detailed_description = "AVR AVR® ATmega Microcontroller IC 8-Bit 16MHz 16KB (8K x 16) FLASH 32-VQFN (5x5)"
        self.manufacturer = "Microchip Technology"
        self.lead_time = "29 week(s)"
        self.mpn = "ATMEGA16U2-MU"
        self.datasheet = "https://ww1.microchip.com/downloads/en/DeviceDoc/doc7799.pdf"
        self.description = "IC MCU 8BIT 16KB FLASH 32VQFN"
        self.parameters = {
            "Package / Case": "32-VFQFN Exposed Pad",
            "Speed": "16MHz",
            "Program Memory Size": "16KB (8K x 16)",
            "RAM Size": "512 x 8",
            "Operating Temperature": "-40°C - 85°C",
            "Oscillator Type": "Internal",
            "Program Memory Type": "FLASH",
            "EEPROM Size": "512 x 8",
            "Core Processor": "AVR",
            "Supply Voltage": "2.7V - 5.5V",
            "Connectivity": "SPI, UART/USART, USB",
            "Number of I/O": "22",
        }
        self.pins = cmp.PinContainer.from_dict(
            {
                4: "VCC",
                3: "GND",
                32: "AVCC",  # Analog supply voltage; connect through RC to VCC
                14: "PB0",  # nSS, PCINT0
                15: "PB1",  # SCLK, PCINT1
                16: "PB2",  # MOSI, PCINT2
                17: "PB3",  # MISO, PCINT3, PDO
                18: "PB4",  # TIMER1, PCINT4
                19: "PB5",  # PCINT5
                20: "PB6",  # PCINT6
                21: "PB7",  # PCINT7, OC.0A, OC.1C
                5: "PC2",  # AIN2, PCINT11
                22: "PC7",  # INT4, ICP1, CLKO
                23: "PC6",  # PCINT8, OC.1A
                25: "PC5",  # PCINT9, OC.1B
                26: "PC4",  # PCINT10
                6: "PD0",  # INT0, OC.0B
                7: "PD1",  # AIN0, INT1
                8: "PD2",  # RXD1, AIN1, INT2
                9: "PD3",  # TXD1, INT3
                10: "PD4",  # INT5, AIN3
                11: "PD5",  # XCK, AIN4, PCINT12
                12: "PD6",  # nRTS, AIN5, INT6
                13: "PD7",  # nCTS, nHWB, AIN6, T0, INT7
                30: "D-",  # USB Full Speed Negative Data
                29: "D+",  # USB Full Speed Positive Data
                28: "UGND",  # USB Ground
                31: "UVCC",  # USB supply voltage
                27: "UCAP",  # USB supply voltage decoupling cap (1uf)
                24: "RESET/PC1/dW",  # Reset, active low
                1: "XTAL1",
                2: "PC0",  # XTAL2
            },
            self,
        )

        ains = ["PD1", "PD2", "PD4", "PD5", "PD6", "PD7"]
        self.analog_in = [self.pins.by_name(a) for a in ains]
        self.uart = serial.UART(rx=self.pins[8], tx=self.pins[9])
        self.spi = serial.SPI(
            mosi=self.pins[16], miso=self.pins[17], sck=self.pins[15], cs=self.pins[14]
        )

import earthground.components as cmp
from earthground.library.protocols import serial


class ATMEGA328P_PU(cmp.Component):
    def __init__(self):
        super().__init__()
        self.detailed_description = "AVR AVR® ATmega Microcontroller IC 8-Bit 20MHz 32KB (16K x 16) FLASH 28-PDIP"
        self.manufacturer = "Microchip Technology"
        self.mpn = "ATMEGA328P-PU"
        self.datasheet = "https://ww1.microchip.com/downloads/en/DeviceDoc/ATmega48A-PA-88A-PA-168A-PA-328-P-DS-DS40002061B.pdf"
        self.description = "IC MCU 8BIT 32KB FLASH 28DIP"
        self.parameters = {
            "Package / Case": '28-DIP (0.300", 7.62mm)',
            "Mounting Type": "Through Hole",
            "Speed": "20MHz",
            "Program Memory Size": "32KB (16K x 16)",
            "RAM Size": "2K x 8",
            "Operating Temperature": "-40°C ~ 85°C",
            "Oscillator Type": "Internal",
            "Program Memory Type": "FLASH",
            "EEPROM Size": "1K x 8",
            "Core Processor": "AVR",
            "Data Converters": "A/D 6x10b",
            "Core Size": "8-Bit",
            "Supply Voltage": "1.8V ~ 5.5V",
            "Connectivity": "I2C, SPI, UART/USART",
            "Supplier Device Package": "28-PDIP",
            "Number of I/O": "23",
        }
        self.pins = cmp.PinContainer.from_dict(
            {
                28: "PC5",  # ADC5
                27: "PC4",  # ADC4
                26: "PC3",  # ADC3
                25: "PC2",  # ADC2
                24: "PC1",  # ADC1
                23: "PC0",  # ADC0
                19: "PB5",  # SCK
                18: "PB4",  # MISO
                17: "PB3",  # MOSI
                16: "PB2",  # SS
                15: "PB1",  # OC1
                14: "PB0",  # ICP
                13: "PD7",  # AIN1
                12: "PD6",  # AIN0
                11: "PD5",  # T1
                6: "PD4",  # T0
                5: "PD3",  # INT1
                4: "PD2",  # INT0
                3: "PD1",  # TXD
                2: "PD0",  # RXD
                8: "GND",
                7: "VCC",
                20: "AVCC",
                21: "AREF",
                9: "XTAL1",
                10: "XTAL2",
                1: "PC6",  # RESET
            },
            self,
        )

        ains = ["PD1", "PD2", "PD4", "PD5", "PD6", "PD7"]
        self.analog_in = [self.pins.by_name(a) for a in ains]
        self.uart = serial.UART(rx=self.pins[8], tx=self.pins[9])
        self.spi = serial.SPI(
            mosi=self.pins[16], miso=self.pins[17], sck=self.pins[15], cs=self.pins[14]
        )

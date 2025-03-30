import earthground.components as cmp
import earthground.library.protocols.serial as serial

class RP2040(cmp.Component):
    def __init__(self):
        super().__init__()
        self.manufacturer = "Raspberry Pi"
        self.mpn = "SC0914(7)"
        self.description = "IC MCU 32BIT EXT MEM 56QFN"
        self.datasheet = (
            "https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf"
        )
        self.parameters = {
            "Package / Case": "56-VFQFN Exposed Pad",
            "Speed": "133MHz",
            "RAM Size": "264K x 8",
            "Operating Temperature": "-40°C ~ 85°C (TC)",
            "Core Processor": "ARM® Cortex®-M0+",
            "Core Size": "32-Bit Dual-Core",
            "Voltage - Supply (Vcc/Vdd)": "1.8V ~ 3.3V",
            "Number of I/O": "30",
        }

        self.pins = cmp.PinContainer.from_dict(
            {
                1: "IOVDD",
                2: "GPIO0",
                3: "GPIO1",
                4: "GPIO2",
                5: "GPIO3",
                6: "GPIO4",
                7: "GPIO5",
                8: "GPIO6",
                9: "GPIO7",
                10: "IOVDD",
                11: "GPIO8",
                12: "GPIO9",
                13: "GPIO10",
                14: "GPIO11",
                15: "GPIO12",
                16: "GPIO13",
                17: "GPIO14",
                18: "GPIO15",
                19: "XIN",
                20: "XOUT",
                21: "TESTEN",
                22: "IOVDD",
                23: "DVDD",
                24: "SWCLK",
                25: "SWDIO",
                26: "RUN",
                27: "GPIO16",
                28: "GPIO17",
                29: "GPIO18",
                30: "GPIO19",
                31: "GPIO20",
                32: "GPIO21",
                33: "IOVDD",
                34: "GPIO22",
                35: "GPIO23",
                36: "GPIO24",
                37: "GPIO25",
                38: "GPIO26/ADC0",
                39: "GPIO27/ADC1",
                40: "GPIO28/ADC2",
                41: "GPIO29/ADC3",
                42: "IOVDD",
                43: "ADC_AVDD",
                44: "VREG_VIN",
                45: "VREG_VOUT",
                46: "USB_DM",
                47: "USB_DP",
                48: "USB_VDD",
                49: "IOVDD",
                50: "DVDD",
                51: "QSPI_SD3",
                52: "QSPI_SCLK",
                53: "QSPI_SD0",
                54: "QSPI_SD2",
                55: "QSPI_SD1",
                56: "QSPI_SS_N",
                57: "EPAD",
            },
            self,
        )


GPIO F1 F2 F3 F4 F5 F6 F7 F8 F9
PIN0 SPI0_RX UART0_TX I2C0_SDA PWM0_A USB_OVCUR_DET
PIN1 SPI0_CSn UART0_RX I2C0_SCL PWM0_B USB_VBUS_DET
PIN2 SPI0_SCK UART0_CTS I2C1_SDA PWM1_A USB_VBUS_EN
PIN3 SPI0_TX UART0_RTS I2C1_SCL PWM1_B USB_OVCUR_DET
PIN4 SPI0_RX UART1_TX I2C0_SDA PWM2_A USB_VBUS_DET
PIN5 SPI0_CSn UART1_RX I2C0_SCL PWM2_B USB_VBUS_EN
PIN6 SPI0_SCK UART1_CTS I2C1_SDA PWM3_A USB_OVCUR_DET
PIN7 SPI0_TX UART1_RTS I2C1_SCL PWM3_B USB_VBUS_DET
PIN8 SPI1_RX UART1_TX I2C0_SDA PWM4_A USB_VBUS_EN
PIN9 SPI1_CSn UART1_RX I2C0_SCL PWM4_B USB_OVCUR_DET
PIN10 SPI1_SCK UART1_CTS I2C1_SDA PWM5_A USB_VBUS_DET
PIN11 SPI1_TX UART1_RTS I2C1_SCL PWM5_B USB_VBUS_EN
PIN12 SPI1_RX UART0_TX I2C0_SDA PWM6_A USB_OVCUR_DET
PIN13 SPI1_CSn UART0_RX I2C0_SCL PWM6_B USB_VBUS_DET
PIN14 SPI1_SCK UART0_CTS I2C1_SDA PWM7_A USB_VBUS_EN
PIN15 SPI1_TX UART0_RTS I2C1_SCL PWM7_B USB_OVCUR_DET
PIN16 SPI0_RX UART0_TX I2C0_SDA PWM0_A USB_VBUS_DET
PIN17 SPI0_CSn UART0_RX I2C0_SCL PWM0_B USB_VBUS_EN
PIN18 SPI0_SCK UART0_CTS I2C1_SDA PWM1_A USB_OVCUR_DET
PIN19 SPI0_TX UART0_RTS I2C1_SCL PWM1_B USB_VBUS_DET
PIN20 SPI0_RX UART1_TX I2C0_SDA PWM2_A CLOCK GPIN0 USB_VBUS_EN
PIN21 SPI0_CSn UART1_RX I2C0_SCL PWM2_B CLOCK GPOUT0 USB_OVCUR_DET
PIN22 SPI0_SCK UART1_CTS I2C1_SDA PWM3_A CLOCK GPIN1 USB_VBUS_DET
PIN23 SPI0_TX UART1_RTS I2C1_SCL PWM3_B CLOCK GPOUT1 USB_VBUS_EN
PIN24 SPI1_RX UART1_TX I2C0_SDA PWM4_A CLOCK GPOUT2 USB_OVCUR_DET
PIN25 SPI1_CSn UART1_RX I2C0_SCL PWM4_B CLOCK GPOUT3 USB_VBUS_DET
PIN26 SPI1_SCK UART1_CTS I2C1_SDA PWM5_A USB_VBUS_EN
PIN27 SPI1_TX UART1_RTS I2C1_SCL PWM5_B USB_OVCUR_DET
PIN28 SPI1_RX UART0_TX I2C0_SDA PWM6_A USB_VBUS_DET
PIN29 SPI1_CSn UART0_RX I2C0_SCL PWM6_B USB_VBUS_EN

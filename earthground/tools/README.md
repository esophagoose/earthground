# Earthground Tools
## Component Creator
The component creator will automatically create component python definitions from a Digikey link

### Walkthrough - I/O Expander ([PI4IOE5V6416ZDEX](https://www.digikey.com/en/products/detail/diodes-incorporated/PI4IOE5V6416ZDEX/9769326))
Run the tool:
```
python3 -m earthground.tools.component_creator
```
Here's the interaction to use the tool:


- tool> `? Enter the DigiKey part number: `
- user> `PI4IOE5V6416ZDEXDICT-ND`
- tool> `? Would you like to use AI to generate the pins?`

Answering yes, will use OpenAI GPT-4-Turbo to attempt to parse the pin table. I've found it to be quite accurate but it's never guaranteed to be right. Also make sure to setup the OpenAI API key. This does cost money but this example costed about 4 cents (USD)

- user> `y`
- tool> 
```
Open the datasheet in your browser: https://www.diodes.com/assets/Datasheets/PI4IOE5V6416.pdf

? Copy the pin table here:
```

Here you should copy the text from the PDF. Don't worry about the formatting.
Text copied from datasheet:

![image to datasheet pin map](/docs/images/datasheet_pin_map_example.png)

How it looked pasted into the terminal:
- user>
```
Document Number DS40821 Rev 3-2 3 © Diodes Incorporated
PI4IOE5V6416
Pin Description
Pin Name 24-pin
TSSOP
24-pin
TQFN
24-pin
VFBGA Description
INT 1 22 A3 Interrupt output. Connect to VDD(I2C-bus) or VDD(P) through a pull-up
resistor.
VDD(I2C_bus) 2 23 B3 Supply voltage of I2C-bus. Connect directly to the VDD of the
external I2C master. Provides voltage-level translation.
RESET 3 24 A2 Active LOW reset input. Connect to VDD(I2C-bus) through a pull-up
resistor if no active connection is used.
P0_0 4 1 A1 Port 0 input/output 0.
P0_1 5 2 C3 Port 0 input/output 1.
P0_2 6 3 B1 Port 0 input/output 2.
P0_3 7 4 C1 Port 0 input/output 3.
P0_4 8 5 C2 Port 0 input/output 4.
P0_5 9 6 D1 Port 0 input/output 5.
P0_6 10 7 E1 Port 0 input/output 6.
P0_7 11 8 D2 Port 0 input/output 7.
VSS 12 9 E2 Ground
P1_0 13 10 E3 Port 1 input/output 0.
P1_1 14 11 E4 Port 1 input/output 1.
P1_2 15 12 D3 Port 1 input/output 2.
P1_3 16 13 E5 Port 1 input/output 3.
P1_4 17 14 D4 Port 1 input/output 4.
P1_5 18 15 D5 Port 1 input/output 5.
P1_6 19 16 C5 Port 1 input/output 6.
P1_7 20 17 C4 Port 1 input/output 7.
ADDR 21 18 B5 Address input. Connect directly to VDD(P) or ground.
SCL 22 19 A5 Serial clock bus. Connect to VDD(I2C-bus) through a
pull-up resistor.
SDA 23 20 A4 Serial data bus. Connect to VDD(I2C-bus) through a
pull-up resistor.
VDD(P) 24 21 B4 Supply voltage of PI4IOE5V6416 for Port P
```

- tool> `? If there's multiple columns of pin indices for different footprints, describe which colum
n to use. Else leave blank`
- user> `use the third column labeled "24-pin VFBGA"`
- tool> 
```
  A3: INT  # Interrupt output. Connect to VDD(I2C-bus) or VDD(P) through a pull-up resistor.
  B3: VDD(I2C_bus)  # Supply voltage of I2C-bus. Connect directly to the VDD of the external I2C master. Provides voltage-level translation.
  A2: RESET  # Active LOW reset input. Connect to VDD(I2C-bus) through a pull-up resistor if no active connection is used.
  A1: P0_0  # Port 0 input/output 0.
  C3: P0_1  # Port 0 input/output 1.
  B1: P0_2  # Port 0 input/output 2.
  C1: P0_3  # Port 0 input/output 3.
  C2: P0_4  # Port 0 input/output 4.
  D1: P0_5  # Port 0 input/output 5.
  E1: P0_6  # Port 0 input/output 6.
  D2: P0_7  # Port 0 input/output 7.
  E2: VSS  # Ground
  E3: P1_0  # Port 1 input/output 0.
  E4: P1_1  # Port 1 input/output 1.
  D3: P1_2  # Port 1 input/output 2.
  E5: P1_3  # Port 1 input/output 3.
  D4: P1_4  # Port 1 input/output 4.
  D5: P1_5  # Port 1 input/output 5.
  C5: P1_6  # Port 1 input/output 6.
  C4: P1_7  # Port 1 input/output 7.
  B5: ADDR  # Address input. Connect directly to VDD(P) or ground.
  A5: SCL  # Serial clock bus. Connect to VDD(I2C-bus) through a pull-up resistor.
  A4: SDA  # Serial data bus. Connect to VDD(I2C-bus) through a pull-up resistor.
  B4: VDD(P)  # Supply voltage of PI4IOE5V6416 for Port P
? Is this correct?
```
- user> `y`
- tool> `Successfully wrote earthground/library/integrated_circuits/io_expanders/pi4ioe5v6416zdex.py`


Opening the file:
```
import earthground.components as cmp


class PI4IOE5V6416ZDEX(cmp.Component):
    def __init__(self):
        super().__init__()
        self.manufacturer = "Diodes Incorporated"
        self.mpn = "PI4IOE5V6416ZDEX"
        self.description = "IC XPNDR 400KHZ I2C 24TQFN"
        self.datasheet = "https://www.diodes.com/assets/Datasheets/PI4IOE5V6416.pdf"
        self.parameters = {
            "Packaging": "Cut Tape (CT)",
            "Features": "POR",
            "Package / Case": "24-VFQFN Exposed Pad",
            "Output Type": "Open Drain, Push-Pull",
            "Mounting Type": "Surface Mount",
            "Interface": "I2C",
            "Number of I/O": "16",
            "Operating Temperature": "-40°C ~ 85°C",
            "Voltage - Supply": "1.65V ~ 5.5V",
            "Clock Frequency": "400 kHz",
            "Interrupt Output": "Yes",
            "Supplier Device Package": "24-TQFN (4x4)",
            "Current - Output Source/Sink": "10mA, 25mA",
            "DigiKey Programmable": "Not Verified",
        }
        self.pins = cmp.PinContainer.from_dict(
            {
                "A3": "INT",  # Interrupt output. Connect to VDD(I2C-bus) or VDD(P) through a pull-up resistor.
                "B3": "VDD(I2C_bus)",  # Supply voltage of I2C-bus. Connect directly to the VDD of the external I2C master. Provides voltage-level translation.
                "A2": "RESET",  # Active LOW reset input. Connect to VDD(I2C-bus) through a pull-up resistor if no active connection is used.
                "A1": "P0_0",  # Port 0 input/output 0.
                "C3": "P0_1",  # Port 0 input/output 1.
                "B1": "P0_2",  # Port 0 input/output 2.
                "C1": "P0_3",  # Port 0 input/output 3.
                "C2": "P0_4",  # Port 0 input/output 4.
                "D1": "P0_5",  # Port 0 input/output 5.
                "E1": "P0_6",  # Port 0 input/output 6.
                "D2": "P0_7",  # Port 0 input/output 7.
                "E2": "VSS",  # Ground
                "E3": "P1_0",  # Port 1 input/output 0.
                "E4": "P1_1",  # Port 1 input/output 1.
                "D3": "P1_2",  # Port 1 input/output 2.
                "E5": "P1_3",  # Port 1 input/output 3.
                "D4": "P1_4",  # Port 1 input/output 4.
                "D5": "P1_5",  # Port 1 input/output 5.
                "C5": "P1_6",  # Port 1 input/output 6.
                "C4": "P1_7",  # Port 1 input/output 7.
                "B5": "ADDR",  # Address input. Connect directly to VDD(P) or ground.
                "A5": "SCL",  # Serial clock bus. Connect to VDD(I2C-bus) through a pull-up resistor.
                "A4": "SDA",  # Serial data bus. Connect to VDD(I2C-bus) through a pull-up resistor.
                "B4": "VDD(P)",  # Supply voltage of PI4IOE5V6416 for Port P
            },
            self,
        )
```


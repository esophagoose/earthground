# Example Project - Making an IO Expander Breakout Board
Let's design a breakout board for the [TCA9535](https://www.ti.com/lit/ds/symlink/tca9535.pdf), an IO expander! To show the full power of this library, this breakout board will have two TCA9535s, on different I2C addresses; a QWIIC connector for I2C connectivity; and a 40-pin connector for the GPIO outputs. The final project can be found in `io_expander_example.py`

## Schematic
You can structure this project as a script or class. The advantage of using a class is easy modularity of your designs at the expense of some complexity. For this example, we will make this a script. Let's start by definining our schematic:
```
import common.schematic as sch_lib

schematic = sch_lib.Design("IO Expander Example")
schematic.default_passive_size = "0603"
```
The name we pass into the `Design` class is the equivalent of a schematic page name.
Note: if we were to make this a class, we would inherits the `Design` class:
```
import common.schematic as schematic

class IoExpanderExample(schematic.Design):
    def __init__(self) -> None:
        super().__init__(f"IO Expander Example")
        self.default_passive_size = "0603"
```
We also set here the default package size for resistors and capacitors. Although this is optional, it helps save time to not have to fill out a footprint for every passive. And you can always override the footprint. 
    
### Adding the Connectors
Let's add our two connectors. One QWIIC connector and one 40-pin standard 0.1" header. One of the features of software-defined circuits is parameterized components. In the connector library, there's functions like `standard_0_1_inch_header` that allow you to define custom pin count and row connectors dynamically. We also add here a [QWIIC connector](https://www.sparkfun.com/qwiic) which has the part number PRT_14417.
```
gpio_connector = conn_lib.standard_0_1_inch_header(pin_count=40, row_count=2)
schematic.add_component(gpio_connector)
qwiic = schematic.add_component(jst.PRT_14417())
```
### Defining the IO Expanders
Next we are going to make a list of the two IO expanders used in this project. Using a `for`-loop, we can add their ground and power pins to the respective nets in this design. 
Since QWIIC is designed for I2C, we defined the interface in the part so connecting it to the expanders is simple. Lastly, we will set the expander's address to the index of the expanders (zero for the first one and one for the second) and connect their I2C bus.
```
from library.integrated_circuits.io_expanders import tca9535pwr

expander_count = 2
expanders = []

# We then iterate over the expanders to set up their pins and address.
for i in range(expander_count):
    # QWIIC doesn't use I2C interrupts so let's remove the pullup
    expander = tca9535pwr.generate_design(address=i, interrupt_pullup=None)
    schematic.add_module(expander)
    schematic.join_net(expander.port.vcc, "P3V3")
    schematic.join_net(expander.port.gnd, "GND")
    schematic.connect_bus(expander.port.i2c, qwiic.i2c)
    expanders.append(expander)
```        
This small code snippet shows some powerful concepts of this library. First is the simplicity of reuse. Changing this code to five IO expanders would be a one line code change. Second is how the context of the part is found entirely in that part's definition. All datasheet quirks and information can be found and abstracted there so that when it comes to the design phase we know this part is correct. Gone are the days of checking datasheets for every part in the schematic review. Abstraction is wonderful. Let's look a bit deeper:
#### How Address Assignment Works
Part of a `for`-loop to set the address is this:
```
expander = tca9535pwr.generate_design(address=i, interrupt_pullup=None)
```
Looking at the expander's definition, there's a number of interesting features:
```
def generate_design(
    address=0, interrupt_pullup="10k", decoupling_cap=cmp.Capacitor("1u", 10)
):
    if not (0 <= address <= 7):
        raise ValueError(f"Invalid address {address}; range 0-7")
    ports = [f"IO{i}" for i in range(GPIO_COUNT)] + ["VCC", "GND", "I2C", "INT"]
    design = sch.Design("Tca9535Design", "EXPANDER", ports)
    expander = design.add_component(TCA9535PWR())
    design.join_net(expander.pins.by_name("VCC"), "VCC")
    design.join_net(expander.pins.by_name("GND"), "GND")

    # Set address pins
    converter = utils.ElectricalBool("VCC", "GND")
    a0 = converter.to_net(address & 1)
    a1 = converter.to_net((address >> 1) & 1)
    a2 = converter.to_net((address >> 2) & 1)
    design.join_net(expander.pins.by_name("A0"), a0)
    design.join_net(expander.pins.by_name("A1"), a1)
    design.join_net(expander.pins.by_name("A2"), a2)

    # Add decoupling cap and interrupt pull-up
    design.add_decoupling_cap(expander.pins.by_name("VCC"), decoupling_cap)
    if interrupt_pullup:
        design.add_series_res(
            pin1=expander.pins.by_name("INT"),
            ohms=interrupt_pullup,
            pin2=expander.pins.by_name("VCC"),
            net_name="I2C_INT",
        )

    # Assign ports
    for name in ["VCC", "GND", "INT"]:
        design.port[name] = expander.pins.by_name(name)
    for i in range(GPIO_COUNT):
        design.port[f"IO{i}"] = expander.gpio(i)
    design.port.i2c = expander.i2c
    return design
```
First it creates and returns a design (schematic page) for this reference design. It has options for a decoupling capacitor and pullup resistors that default to the datasheet recommended values.

It also handles addressing! It will take in an integer address index, validate it, and then automatically converts that index to the correct configurations of its pins. This level of abstraction can be replicated in other ways like on an LDO. The user could add a `set_output_voltage` function that when called with a voltage as the argument would set the correct feedback resistors and correctly renamed the VOUT net to something like `P3V3_LDO`. You can also put bounds on output voltage to prevent mistakes and even calculate efficency based on VIN and warn the user if they are making a thermally precarious design.

Another example, is on the TCA9535 expander. Its output pins are named "P00", "P01", etc but after "P07" is "P10". This is all abstracted by the `gpio` function:
```
    def gpio(self, index):
        bank = int(index / 8)
        port = index % 8
        return self.pins.by_name(f"P{bank}{port}")
```
Now the user can say `expander.gpio(0)` to get the first GPIO pin and not have to worry about this specific naming convention each manufacturer uses.

Another interesting function of this library is that parts can designator generic pins. For the TCA9535, all its outputs are identical and thus can all be interchanged. You can ask for a generic GPIO and later in layout, the library will automatically assign the most optimized pin.

Ok, now back to the design.

### Connecting Everything Up
Add the power rails to the QWIIC connector:
```
schematic.join_net(qwiic.pins.by_name("VCC"), "VCC")
schematic.join_net(qwiic.pins.by_name("GND"), "GND")
```
For the 40-pin output connector, let's make the first and last 4 pins ground and the rest the IO expander's GPIO (32 total since each expander has 16-channels). To assign this we can once again use loops to make this simple.
```
for i, expander in enumerate(expanders):
    for io in range(tca9535pwr.GPIO_COUNT):
        pin = i * tca9535pwr.GPIO_COUNT + io + 1
        pin += 4  # First 4 pins will be ground
        net = f"IO{i+1}_P{pin:02}_OUT"
        schematic.connect([expander.port[f"IO{io}"], gpio_connector.pins[pin]], net)

for ground_pin in range(4):
    start = ground_pin + 1
    end = gpio_connector.pin_count - ground_pin
    schematic.join_net(gpio_connector.pins[start], "GND")
    schematic.join_net(gpio_connector.pins[end], "GND")
```
Congrats! We are now we are done with the schematic!

## Validating the Design
### Visual
To make sure you connected everything properly, you can visualize the components and modules (schematic sub-pages) and what they are connected with:
```
schematic.print_design()
```
This will print to the console the schematic. Here's an example:
```
EXPANDER1 (Tca9535Design)
.------.
|   IO0|-- IO2_P21_OUT
|   IO1|-- IO2_P22_OUT
|   IO2|-- IO2_P23_OUT
|   IO3|-- IO2_P24_OUT
|   IO4|-- IO2_P25_OUT
|   IO5|-- IO2_P26_OUT
|   IO6|-- IO2_P27_OUT
|   IO7|-- IO2_P28_OUT
|   IO8|-- IO2_P29_OUT
|   IO9|-- IO2_P30_OUT
|  IO10|-- IO2_P31_OUT
|  IO11|-- IO2_P32_OUT
|  IO12|-- IO2_P33_OUT
|  IO13|-- IO2_P34_OUT
|  IO14|-- IO2_P35_OUT
|  IO15|-- IO2_P36_OUT
|   VCC|-- P3V3
|   GND|-- GND
|   I2C|-- I2C [I2C0_SDA, I2C0_SCL]
|   INT|-- <NO CONNECTION>
'------'
```

## Layout
Lastly, let's export this design to layout. Currently, the only supported exporter is KiCad. Running the exporter will generate the `kicad_pcb` file.

```
# Export the layout to KiCad
exporters.kicad.KicadExporter(schematic).save()
```
# Example Project - Making an IO Expander Breakout Board
Let's design a breakout board for the TCA9535, an IO expander! To show the full power of this library, this breakout board will have two TCA9535, all on different I2C addresses; a QWIIC connector for I2C connectivity; and a 40-pin connector for the GPIO outputs. The final project can be found in `io_expander_example.py`

## Schematic
You can structure this project as a script or class. The advantage of using a class is easy modularity of your designs at the expense of some complexity. For this example, we will make this a script. Let's start by definining our schematic:
```
import common.schematic as schematic

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
    
### Defining the IO Expanders
We are going to make a list of the two IO expanders used in this project. Using a `for`-loop, we can add their ground and power pins to the respective nets in this design. We can also easily add a decoupling capacitor as well. Lastly, we will set the expander's address to the index of the expanders (zero for the first one and one for the second) and connect their I2C bus.

Code:
```
from library.integrated_circuits.io_expanders import tca9535pwr

expanders = [tca9535pwr.TCA9535PWR(), tca9535pwr.TCA9535PWR()]

# We then iterate over the expanders to set up their pins and address.
for i, expander in enumerate(expanders):
    vcc = expander.pins.by_name("VCC")
    gnd = expander.pins.by_name("GND")
    schematic.join_net(vcc, "3V3")
    schematic.join_net(gnd, "GND")
    schematic.add_decoupling_cap(vcc, cmp.Capacitor("1u", 10))
    expander.address = i

# We connect the I2C bus of the two expanders.
schematic.connect_bus(expanders[0].i2c, expanders[1].i2c)
```        
This small code snippet shows some powerful concepts of this library. First is the simplicity of reuse. Changing this code to five IO expanders would be a one line code change. Second is how the context of the part is found entirely in that part's definition. All datasheet quirks and information can be found and abstracted there so that when it comes to the design phase we know this part is correct. Gone are the days of checking datasheets for every part in the design review. Abstraction is wonderful. Let's look a bit deeper:
#### How Address Assignment Works
Part of a `for`-loop to set the address is this:
```
    expander.address = i
```
Looking at the expander's definition has this for setting the address
```
    @address.setter
    def address(self, value):
        assert 0 <= value <= 7, f"Invalid address {value}"
        a0 = "VCC" if value & 1 else "GND"
        a1 = "VCC" if (value >> 1) & 1 else "GND"
        a2 = "VCC" if (value >> 2) & 1 else "GND"
        self.pins.by_name("A0").net = a0
        self.pins.by_name("A1").net = a1
        self.pins.by_name("A2").ndt = a2
```
In the part definition it handles invalid addresses and automatically converts an index to the correct configurations of its pins. This level of abstraction can be replicated in other ways like on an LDO. The user could add a `set_output_voltage` function that when called with a voltage as the argument would set the correct feedback resistors and correctly renamed the VOUT net to something like `P3V3_LDO`. You can also put bounds on output voltage to prevent mistakes and even calculate efficency based on VIN and warn the user if they are making a thermally precarious design.

Another example, is that the output pins are named "P00", "P01", etc and after "P07" is "P10". This is all abstracted by the `gpio` function:
```
    def gpio(self, index):
        bank = int(index / 8)
        port = index % 8
        return self.pins.by_name(f"P{bank}{port}")
```
Now the user can say `expander.gpio(0)` to get the first GPIO pin and not have to worry about this specific naming convention each manufacturer uses.

Another interesting function of this library is that parts can designator generic pins. For the TCA9535, all its outputs are identical and thus can all be interchanged. You can ask for a generic GPIO and later in layout, the library will automatically assign the most optimized pin.

Ok, now back to the design.

### Adding the Connectors
Let's add our two connectors. One QWIIC connector and one 40-pin standard 0.1" header
```
gpio_connector = conn_lib.standard_0_1_inch_header(pin_count=40, row_count=2)
qwiic = jst.PRT_14417()  # PRT_14417 is Sparkfun's QWIIC connector
```
Since QWIIC is designed for I2C, we defined the interface in the part so connecting it to the expanders is as simple as:
```
schematic.connect_bus(qwiic.i2c, expanders[0].i2c)
schematic.join_net(qwiic.pins.by_name("VCC"), "VCC")
schematic.join_net(qwiic.pins.by_name("GND"), "GND")
```
For the 40-pin output connector, let's make the first and last 4 pins ground and the rest the IO expander's GPIO (32 total since each expander has 16-channels). To assign this we can once again use loops to make this simple.
```
for i, expander in enumerate(expanders):
    for pin in range(tca9535pwr.GPIO_COUNT):
        connector_pin = i * tca9535pwr.GPIO_COUNT + pin + 1
        connector_pin += 4  # First 4 pins will be ground
        schematic.connect(expander.gpio(pin), gpio_connector.pins[connector_pin])

for ground_pin in range(4):
    i = ground_pin + 1
    schematic.join_net(gpio_connector.pins[i], "GND")
    schematic.join_net(gpio_connector.pins[gpio_connector.pin_count - i + 1], "GND")
```
Congrats! We are now we are done with the schematic!


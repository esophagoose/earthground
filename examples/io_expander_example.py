import common.components as cmp
import common.layout as layout_lib
import common.schematic as sch_lib
import common.stackup as stackup
import library.headers.connectors as conn_lib
import library.headers.jst as jst
from library.integrated_circuits.io_expanders import tca9535pwr

# Schematic definition
schematic = sch_lib.Design("IO Expander Example", "IOExample")
schematic.default_passive_size = "0603"
expanders = [tca9535pwr.TCA9535PWR(), tca9535pwr.TCA9535PWR()]

for i, expander in enumerate(expanders):
    schematic.add_component(expander)
    vcc = expander.pins.by_name("VCC")
    gnd = expander.pins.by_name("GND")
    schematic.join_net(vcc, "VCC")
    schematic.join_net(gnd, "GND")
    schematic.add_decoupling_cap(vcc, cmp.Capacitor("1u", 10))
    expander.address = i
schematic.connect_bus(expanders[0].i2c, expanders[1].i2c)

gpio_connector = conn_lib.standard_0_1_inch_header(pin_count=40, row_count=2)
qwiic = jst.PRT_14417()
schematic.connect_bus(qwiic.i2c, expanders[0].i2c)
schematic.join_net(qwiic.pins.by_name("VCC"), "VCC")
schematic.join_net(qwiic.pins.by_name("GND"), "GND")

# For the output connector, the first 4 and last 4 will be ground
for i, expander in enumerate(expanders):
    for pin in range(tca9535pwr.GPIO_COUNT):
        connector_pin = i * tca9535pwr.GPIO_COUNT + pin + 1
        connector_pin += 4  # First 4 pins will be ground
        net = f"IO{i+1}_P{pin:03}_OUT"
        schematic.connect(expander.gpio(pin), gpio_connector.pins[connector_pin], net)

for ground_pin in range(4):
    i = ground_pin + 1
    schematic.join_net(gpio_connector.pins[i], "GND")
    schematic.join_net(gpio_connector.pins[gpio_connector.pin_count - i + 1], "GND")

# Creating the layout
two_layers = stackup.Stackup(stackup.TWO_LAYER_STACKUP)
layout = layout_lib.Layout(schematic, two_layers)

layout.generate_layout("examples/io_expander_example.yaml")
layout.to_svg("io_expander_example.svg")

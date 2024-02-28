import common.schematic as sch_lib
import library.headers.connectors as conn_lib
import library.headers.jst as jst
from library.integrated_circuits.io_expanders import tca9535pwr

# Schematic definition
schematic = sch_lib.Design("IO Expander Example")
schematic.default_passive_size = "0603"
expander_count = 2
expanders = []

# Add components
gpio_connector = conn_lib.standard_0_1_inch_header(pin_count=40, row_count=2)
schematic.add_component(gpio_connector)
qwiic = schematic.add_component(jst.PRT_14417())

for i in range(expander_count):
    # QWIIC doesn't use I2C interrupts so let's remove the pullup
    expander = tca9535pwr.generate_design(address=i, interrupt_pullup=None)
    schematic.add_module(expander)
    schematic.join_net(expander.port.vcc, "P3V3")
    schematic.join_net(expander.port.gnd, "GND")
    schematic.connect_bus(expander.port.i2c, qwiic.i2c)
    expanders.append(expander)

schematic.join_net(qwiic.pins.by_name("VCC"), "P3V3")
schematic.join_net(qwiic.pins.by_name("GND"), "GND")

# For the output connector, the first 4 and last 4 will be ground
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

schematic.print()

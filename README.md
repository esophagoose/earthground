# earthground: A Python Library for Creating Software-Defined Electrical Designs

## Overview
Earthground encompasses a comprehensive suite of tools and libraries aimed at facilitating software-defined electronic schematics.

[Documentation](https://earthground.readthedocs.io/en/latest/)

## Getting Started
### Setup
```
pip install earthground
```

### Simple Example - Resistor Divider

```
import earthground.exporters.kicad
import earthground.components as cmp
import earthground.library.headers.connectors as conn_lib
import earthground.schematic as sch_lib
import earthground.standard_values as sv

# Setup the schematic page
schematic = sch_lib.Design("Resistor Divider Example")
schematic.default_passive_size = "0603"

# Create the components
r1, r2 = sv.find_closest_ratio(5 / 3.3)  # finds closest values in E24
r_top = schematic.add_component(cmp.Resistor(f"{r1}k"))
r_bottom = schematic.add_component(cmp.Resistor(f"{r2}k"))
input_connector = schematic.add_component(conn_lib.standard_0_1_inch_header(pin_count=2))
output_connector = schematic.add_component(conn_lib.standard_0_1_inch_header(pin_count=2))

# Connect them and print schematic to console
schematic.connect([r_top.pins[1], input_connector.pins[1]], "SIG_5V0")
schematic.connect([r_top.pins[2], r_bottom.pins[1], output_connector.pins[1]], "SIG_3V3")
schematic.connect([input_connector.pins[2], r_bottom.pins[2], output_connector.pins[2]], "GND")
schematic.print()

# Export the layout to KiCad
earthground.exporters.kicad.KicadExporter(schematic).save()
```

### Project Walkthrough - 32 Port I/O Expander

[Read the example](https://github.com/esophagoose/earthground/tree/main/examples)
- Located in ``examples/io_expander_example.py``
- Run using: ``python3 -m examples.io_expander_example``


## Advantages of Software-Defined Circuits
### Extensive Tooling
Text-based schematics means engineers can leverage existing software engineering tooling to create error-free designs faster
- Use version control software to save progress, create easy-to-read diffs between versions, and do design review
- Use dev tooling like CI/CD tools to automatically run design rule checkers and application-specific validators to ensure a correct design
- One-click releases - Automatically generate Gerbers, pick-n-place files, cost rollups, power budgets, bringup test plans
### Modular
Finally have stable and correct part libraries and circuits that you can quickly piece together to create complex projects quickly
### Extendable
Earthground can be extended to many purposes because it's written in Python
- If your PCB being connecting to another PCB via harness, you could write an exporter so your favorite harness program always has the latest design
- If there's a microcontroller in your design, you could add an exporter to generate a BSP package or Micropython definition from the schematic that will automatically create a new file on every revision
- If you are concerned about supply chain and components going out-of-stock, you could have your schematic track which components are in stock and define part variations
### Powerful
With a Python backend, it's simple to create powerful component libraries that allow you to create complex designs quickly. Just read the datasheet once and you are good to go
- Abstract complex hardware configuration pins to the component library so your schematics are highly readable (and therefore easily reviewable)
- Rather than noting the position of every configuration on a microcontroller and matching it to the datasheet for every design review you do. You could review your component definition once then in every design do readable things like `mcu.set_boot_location(mcu.EXTERNAL_FLASH)` to easily catch issues
- Quickly set addresses are know they are right:
    ```
    for i, device in enumerate(i2c_devices):
        device.set_i2c_address(i)
    ```
- Add validators for datasheet errata and buried issues so if anyone uses a component in a nonrecommended way on the current design or any future design, Earthground will flag it.
- Parameterize passive component selection for ICs
- For buck converters, Earthground can automatically size inductors based on datasheet parameters
- For LDOs, given an output voltage, Earthground will select the feedback resistors, round them to E24 values, and warn you if the result output voltage is beyond a specified percentage


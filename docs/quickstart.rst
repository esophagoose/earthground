Quickstart
==========

Setup
-----
Installing the dependencies

.. code-block:: python
    pip3 install -r requirements.txt


Simple Example - Resistor Divider
---------------------------------

.. code-block:: python
    import common.components as cmp
    import common.schematic as sch_lib
    import common.standard_values as sv
    import library.headers.connectors as conn_lib

    schematic = sch_lib.Design("Resistor Divider Example")
    schematic.default_passive_size = "0603"
    r1, r2 = sv.find_closest_ratio(5 / 3.3)  # finds closest values in E24
    r_top = schematic.add_component(cmp.Resistor(f"{r1}k"))
    r_bottom = schematic.add_component(cmp.Resistor(f"{r2}k"))
    input_connector = schematic.add_component(conn_lib.standard_0_1_inch_header(pin_count=2))
    output_connector = schematic.add_component(conn_lib.standard_0_1_inch_header(pin_count=2))
    schematic.connect([r_top.pins[1], input_connector.pins[1]], "SIG_5V0")
    schematic.connect([r_top.pins[2], r_bottom.pins[1], output_connector.pins[1]], "SIG_3V3")
    schematic.connect([input_connector.pins[2], r_bottom.pins[2], output_connector.pins[2]], "GND")
    schematic.print()

This design will print to console:
::
    R1 (RES_1.0kΩ)
    .---.
    |  1|-- SIG_5V0
    |  2|-- SIG_3V3
    '---'

    R2 (RES_1.5kΩ)
    .---.
    |  1|-- SIG_3V3
    |  2|-- GND
    '---'

    J1 (CONNECTOR_2x1)
    .---.
    |  1|-- SIG_5V0
    |  2|-- GND
    '---'

    J2 (CONNECTOR_2x1)
    .---.
    |  1|-- SIG_3V3
    |  2|-- GND
    '---'


Example Project
---------------
To get started with the project, clone the repository and install the required dependencies listed in ``requirements.txt``. Explore the example projects and the documentation provided in `examples/README.md` for guidance on using the libraries and tools.
``python3 -m examples.io_expander_example``

```{include} ../../examples/README.md
```

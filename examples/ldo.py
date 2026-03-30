import earthground.exporters.kicad as kicad
import earthground.layout as layout_lib
import earthground.library.integrated_circuits.voltage_regulators.linear.lm317 as lm317

if True:
    design = lm317.LM317AMDTX.generate_design(3.3)
    design.add_module(lm317.LM317AMDTX.generate_design(3.3))
    kicad.KicadExporter(design).save()

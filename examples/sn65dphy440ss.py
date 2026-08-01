"""Run the SN65DPHY440SS Tier 2 analysis example."""

import earthground.standard_values as sv
from earthground.library.integrated_circuits.transceivers.sn65dphy440ss import (
    generate_design,
)

example = generate_design()

print("Straps:")
for result in example.check_straps().results:
    print(f"  {result.refdes}.{result.pin}: {result.status.value} - {result.message}")

print("\nNon-passing contracts:")
for check in example.check_contracts().checks:
    if check.status is not sv.CheckStatus.PASS:
        print(f"  {check}")

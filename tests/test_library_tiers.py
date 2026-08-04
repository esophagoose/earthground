import pytest

import earthground.components as cmp
from earthground.library._intent import typed_pin_map
from earthground.library.connectors.connectors import Throughhole
from earthground.library.connectors.dsub import Dsub
from earthground.library.connectors.fpc.te_2328702 import TE_2328702
from earthground.library.integrated_circuits.controllers.ch334 import CH334F
from earthground.library.integrated_circuits.controllers.fusb302b import FUSB302BVMPX
from earthground.library.integrated_circuits.interface_sensor.cypress_mbr3 import (
    CY8CMBR3116,
)
from earthground.library.integrated_circuits.interface_sensor.iqs550blqnr import (
    IQS550BLQNR,
)
from earthground.library.integrated_circuits.io_expanders.pi4ioe5v6416zdex import (
    PI4IOE5V6416ZDEX,
)
from earthground.library.integrated_circuits.io_expanders.tca9535pwr import (
    TCA9535PWR,
)
from earthground.library.integrated_circuits.logic.level_shifters.lsf0102 import (
    LSF0102,
    LSF0102PartNumbers,
)
from earthground.library.integrated_circuits.microcontrollers.atmega16u2_au import (
    ATMEGA16U2,
    Package as ATmega16Package,
)
from earthground.library.integrated_circuits.microcontrollers.atmega16u2_mur import (
    ATMEGA16U2_MU,
)
from earthground.library.integrated_circuits.microcontrollers.atmega328p_pu import (
    ATMEGA328P_PU,
)
from earthground.library.integrated_circuits.microcontrollers.attiny_1series import (
    ATtiny,
)
from earthground.library.integrated_circuits.microcontrollers.rp2040 import RP2040
from earthground.library.integrated_circuits.motor_drivers.drv2605l import (
    DRV2605L,
    Package as DRV2605Package,
)
from earthground.library.integrated_circuits.motor_drivers.tmc2100 import TMC2100_LA_T
from earthground.library.integrated_circuits.rf.modules.rn487x import (
    RN487x,
    RN487xPartNumbers,
)
from earthground.library.integrated_circuits.transceivers.sn65dphy440ss import (
    SN65DPHY440SS,
)
from earthground.library.integrated_circuits.voltage_regulators.linear.ap7330 import (
    AP7330,
)
from earthground.library.integrated_circuits.voltage_regulators.linear.lm317 import (
    LM317AMDTX,
)
from earthground.library.integrated_circuits.voltage_regulators.switching.lmr51606 import (
    LMR51606,
)
from earthground.library.misc.mounting_holes import M3
from earthground.library.misc.testpoints import CircleSmdTestpoint, ObroundTestpoint
from earthground.library.modules.blackpill import BlackPill
from earthground.library.modules.raspberry_pi_hat import RaspberryPiHat
from earthground.ratings import Ratings

PART_FACTORIES = (
    CH334F,
    FUSB302BVMPX,
    CY8CMBR3116,
    IQS550BLQNR,
    PI4IOE5V6416ZDEX,
    TCA9535PWR,
    lambda: LSF0102(LSF0102PartNumbers.LSF0102DCTR),
    lambda: ATMEGA16U2(ATmega16Package.QFN),
    lambda: ATMEGA16U2(ATmega16Package.TSSOP),
    ATMEGA16U2_MU,
    ATMEGA328P_PU,
    lambda: ATtiny("ATTINY1616-SN"),
    lambda: ATtiny("ATTINY1617-MN"),
    RP2040,
    lambda: DRV2605L(DRV2605Package.SSOP),
    lambda: DRV2605L(DRV2605Package.BGA),
    TMC2100_LA_T,
    lambda: RN487x(RN487xPartNumbers.RN4870_I_RMXXX),
    lambda: RN487x(RN487xPartNumbers.RN4871U_V_RMXXX),
    SN65DPHY440SS,
    AP7330,
    LM317AMDTX,
    LMR51606,
)

PIN_FACTORIES = PART_FACTORIES + (
    lambda: Throughhole(4, 2),
    lambda: Dsub(9),
    lambda: TE_2328702(6),
    M3,
    lambda: CircleSmdTestpoint(1.0),
    lambda: ObroundTestpoint(1.5, 1.0),
    BlackPill,
    RaspberryPiHat,
)


@pytest.mark.parametrize("factory", PIN_FACTORIES)
def test_library_parts_have_tier_one_typed_pin_coverage(factory):
    part = factory()

    assert part.pins
    assert all(not isinstance(pin.spec, cmp.UnspecifiedPinSpec) for pin in part.pins)


@pytest.mark.parametrize("factory", PART_FACTORIES)
def test_library_parts_have_tier_two_analysis_intent(factory):
    part = factory()

    assert isinstance(part.abs_max, Ratings)
    assert isinstance(part.recommended, Ratings)
    assert part.abs_max or part.recommended or part.requires or part.thermal


@pytest.mark.parametrize("factory", PART_FACTORIES)
def test_library_parts_have_tier_three_identity_and_provenance(factory):
    part = factory()

    assert part.name
    assert part.mpn
    assert part.manufacturer
    assert part.description
    assert part.datasheet
    assert isinstance(part.lifecycle, cmp.Lifecycle)


def test_typed_pin_map_rejects_partial_or_ambiguous_migrations():
    with pytest.raises(ValueError, match="exactly one"):
        typed_pin_map({1: "A", 2: "B"}, digital_inputs={"A"})

    with pytest.raises(ValueError, match="exactly one"):
        typed_pin_map(
            {1: "A"},
            digital_inputs={"A"},
            digital_outputs={"A"},
        )


def test_differential_library_interfaces_are_machine_readable():
    rp2040 = RP2040()
    assert rp2040.interfaces["usb"].target_impedance.units == "Ω"
    assert (
        rp2040.pins.by_name("USB_DP").spec.interface.polarity
        is cmp.DifferentialPolarity.POSITIVE
    )

    retimer = SN65DPHY440SS()
    assert len(retimer.interfaces) == 10
    assert all(
        interface.target_impedance.units == "Ω"
        for interface in retimer.interfaces.values()
    )

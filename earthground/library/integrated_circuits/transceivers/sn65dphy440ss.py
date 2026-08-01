"""SN65DPHY440SS component and reference design.

The model demonstrates unit-safe ratings, configuration straps,
required-external contracts, power estimation, and thermal metadata. A package
footprint is intentionally not assigned because Earthground does not currently
ship the exact TI RHR WQFN-28 land pattern.
"""

import earthground.components as cmp
import earthground.contracts as contracts
import earthground.schematic as sch
import earthground.standard_values as sv
import earthground.straps as straps
import earthground.thermal as thermal
from earthground.library.misc.testpoints import CircleSmdTestpoint
from earthground.ratings import Ratings

SOURCE = "SN65DPHY440SS datasheet SLLSEF5D"


def _strap_levels(meanings):
    ranges = {
        "VIL": sv.ratio(0, max=0.2),
        "VIM": sv.ratio(0.4, max=0.6),
        "VIH": sv.ratio(0.8, max=1),
    }
    return tuple(
        straps.StrapLevel(name=name, ratio=ratio, meaning=meanings[name])
        for name, ratio in ranges.items()
    )


def _strap(identifier, pin, meanings):
    internal = sv.ohms(
        100_000,
        typ=100_000,
        max=100_000,
        source=f"{SOURCE} §6.5",
    )
    return straps.StrapPin(
        id=identifier,
        pin=pin,
        reference="VCC",
        levels=_strap_levels(meanings),
        internal_pull_up=internal,
        internal_pull_down=internal,
        sampled_on="rising edge of RSTN",
        source=f"{SOURCE} §8.3",
    )


class SN65DPHY440SS(cmp.Component):
    """Texas Instruments four-lane MIPI D-PHY retimer."""

    def __init__(self):
        super().__init__(refdes_prefix="U")
        self.name = "SN65DPHY440SSRHR"
        self.mpn = "SN65DPHY440SSRHR"
        self.manufacturer = "Texas Instruments"
        self.datasheet = "https://www.ti.com/lit/ds/symlink/sn65dphy440ss.pdf"
        self.description = "MIPI D-PHY 1.1 retimer, four data lanes plus clock"

        self.abs_max = Ratings(
            vcc=sv.volts(-0.3, max=2.175, source=f"{SOURCE} §6.1"),
            tj=sv.celsius(min=sv.UNBOUNDED, max=105, source=f"{SOURCE} §6.1"),
        )
        self.recommended = Ratings(
            vcc=sv.volts(1.62, typ=1.8, max=1.98, source=f"{SOURCE} §6.3"),
            ta=sv.celsius(-40, max=85, source=f"{SOURCE} §6.3"),
        )

        self.strap_pins = (
            _strap(
                "rx-equalization",
                "EQ_SCL",
                {
                    "VIL": "RX EQ 0 dB",
                    "VIM": "RX EQ 2.5 dB",
                    "VIH": "RX EQ 5 dB",
                },
            ),
            _strap(
                "edge-rate",
                "ERC_SDA",
                {
                    "VIL": "edge rate 200 ps",
                    "VIM": "edge rate 150 ps",
                    "VIH": "edge rate 250 ps",
                },
            ),
            _strap(
                "pre-emphasis",
                "PRE_CFG1",
                {
                    "VIL": "pre-emphasis 0 dB",
                    "VIM": "pre-emphasis 0 dB",
                    "VIH": "pre-emphasis 2.5 dB",
                },
            ),
            _strap(
                "output-swing",
                "VSADJ_CFG0",
                {
                    "VIL": "output swing 180 mV",
                    "VIM": "output swing 200 mV",
                    "VIH": "output swing 220 mV",
                },
            ),
        )

        self.requires = (
            contracts.Decoupling(
                id="vcc-decoupling",
                pin="VCC",
                capacitance=sv.farads(min="100n", max=sv.UNBOUNDED),
                source=f"{SOURCE} §9",
            ),
            contracts.Decoupling(
                id="vreg-decoupling",
                pin="VREG_OUT",
                capacitance=sv.farads(min="100n", max=sv.UNBOUNDED),
                source=f"{SOURCE} §9",
            ),
            contracts.Decoupling(
                id="vdd-decoupling",
                pin="VDD",
                capacitance=sv.farads(min="100n", max=sv.UNBOUNDED),
                source=f"{SOURCE} §9",
            ),
            contracts.SameNet(
                id="vreg-vdd-link",
                pins=("VREG_OUT", "VDD"),
                source=f"{SOURCE} §9",
            ),
            contracts.RoutingConstraint(
                id="vreg-vdd-width",
                pins=("VREG_OUT", "VDD"),
                min_trace_width_mm=0.254,
                note="VREG_OUT to VDD must use a 10-mil-or-wider trace",
                source=f"{SOURCE} §9",
            ),
            contracts.Bypass(
                id="rstn-bypass",
                pin="RSTN",
                capacitance=sv.farads(min="200n", max=sv.UNBOUNDED),
                source=f"{SOURCE} §9",
            ),
            contracts.TieIfUnused(
                id="unused-da-inputs",
                pins=(
                    "DA0P",
                    "DA0N",
                    "DA1P",
                    "DA1N",
                    "DA2P",
                    "DA2N",
                    "DA3P",
                    "DA3N",
                ),
                to="GND",
                source=f"{SOURCE} §9",
            ),
            contracts.LeaveOpenIfUnused(
                id="unused-db-outputs",
                pins=(
                    "DB0P",
                    "DB0N",
                    "DB1P",
                    "DB1N",
                    "DB2P",
                    "DB2N",
                    "DB3P",
                    "DB3N",
                ),
                source=f"{SOURCE} §9",
            ),
        )

        self.thermal = thermal.ThermalModel(
            r_ja=sv.celsius_per_watt(42.1, typ=42.1, max=42.1, source=f"{SOURCE} §6.4"),
            r_jb=sv.celsius_per_watt(12.8, typ=12.8, max=12.8, source=f"{SOURCE} §6.4"),
            r_jc_top=sv.celsius_per_watt(
                32.3, typ=32.3, max=32.3, source=f"{SOURCE} §6.4"
            ),
            r_jc_bottom=sv.celsius_per_watt(
                5.2, typ=5.2, max=5.2, source=f"{SOURCE} §6.4"
            ),
            psi_jt=sv.celsius_per_watt(0.5, typ=0.5, max=0.5, source=f"{SOURCE} §6.4"),
            psi_jb=sv.celsius_per_watt(
                12.6, typ=12.6, max=12.6, source=f"{SOURCE} §6.4"
            ),
        )
        self.power = thermal.ConstantPower(
            power=sv.watts(0, typ=0.150, max=0.150, source=f"{SOURCE} §6.5"),
            note="worst listed active mode: four lanes at 1 Gbps",
        )

        self.pins = cmp.PinContainer.from_dict(
            {
                1: "DA0P",
                2: "DA0N",
                3: "DA1P",
                4: "DA1N",
                5: "DACP",
                6: "DACN",
                7: "DA2P",
                8: "DA2N",
                9: "DA3P",
                10: "DA3N",
                11: "VCC",
                12: "VREG_OUT",
                13: "EQ_SCL",
                14: "ERC_SDA",
                15: "DB3N",
                16: "DB3P",
                17: "DB2N",
                18: "DB2P",
                19: "DBCN",
                20: "DBCP",
                21: "DB1N",
                22: "DB1P",
                23: "DB0N",
                24: "DB0P",
                25: "VDD",
                26: "PRE_CFG1",
                27: "VSADJ_CFG0",
                28: "RSTN",
                29: "GND",
            },
            self,
        )


PORTS = (
    "VCC",
    "GND",
    "DA0P",
    "DA0N",
    "DA1P",
    "DA1N",
    "DACP",
    "DACN",
    "DA2P",
    "DA2N",
    "DA3P",
    "DA3N",
    "DB0P",
    "DB0N",
    "DB1P",
    "DB1N",
    "DBCP",
    "DBCN",
    "DB2P",
    "DB2N",
    "DB3P",
    "DB3N",
    "RSTN",
    "EQ_SCL",
    "ERC_SDA",
    "PRE_CFG1",
    "VSADJ_CFG0",
)


def generate_design(add_i2c_pullups=True):
    """Build the datasheet application circuit around the retimer."""
    design = sch.Design("SN65DPHY440SS D-PHY retimer", "DPHY", list(PORTS))
    device = design.add_component(SN65DPHY440SS())

    for name in PORTS:
        design.connect([device.pins.by_name(name), design.port[name]], name)
    design.connect(device.pins.all_with_name("GND"), "GND")

    design.connect(
        [device.pins.by_name("VREG_OUT"), device.pins.by_name("VDD")],
        "DPHY_1V2",
    )
    design.add_decoupling_capacitor(cmp.Capacitor("100n", 10), "DPHY_1V2")
    design.add_decoupling_capacitor(cmp.Capacitor("100n", 10), "DPHY_1V2")
    design.add_decoupling_capacitor(cmp.Capacitor("100n", 10), "VCC")
    design.add_decoupling_capacitor(cmp.Capacitor("200n", 10), "RSTN")

    if add_i2c_pullups:
        design.add_series_res(
            device.pins.by_name("EQ_SCL"),
            "4.7k",
            device.pins.by_name("VCC"),
            "EQ_SCL",
        )
        design.add_series_res(
            device.pins.by_name("ERC_SDA"),
            "4.7k",
            device.pins.by_name("VCC"),
            "ERC_SDA",
        )

    expected = "VIH" if add_i2c_pullups else "VIM"
    reason = (
        "4.7 kΩ I2C pull-up intentionally selects the high strap level"
        if add_i2c_pullups
        else "no external bias; use the internal divider's middle level"
    )
    design.expect_strap(device, "rx-equalization", expected, reason)
    design.expect_strap(device, "edge-rate", expected, reason)
    design.expect_strap(
        device, "pre-emphasis", "VIM", "configuration pin is intentionally floating"
    )
    design.expect_strap(
        device, "output-swing", "VIM", "configuration pin is intentionally floating"
    )

    for name in ("PRE_CFG1", "VSADJ_CFG0"):
        testpoint = design.add_component(CircleSmdTestpoint(1.5))
        design.connect([testpoint.pins[1], device.pins.by_name(name)], name)
    return design

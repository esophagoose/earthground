"""Typed component sourcing metadata and design-level lifecycle reporting."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import earthground.standard_values as sv


class Lifecycle(Enum):
    ACTIVE = "Active"
    NRND = "Not Recommended for New Designs"
    EOL = "End of Life"
    OBSOLETE = "Obsolete"
    PREVIEW = "Preview"
    UNKNOWN = "Unknown"


@dataclass(frozen=True)
class SourcingCheck:
    refdes: str
    mpn: str
    lifecycle: Lifecycle
    status: sv.CheckStatus

    def __str__(self) -> str:
        identity = self.mpn or "unspecified MPN"
        return (
            f"SOURCING {self.status.value} at {self.refdes}: "
            f"{identity} lifecycle is {self.lifecycle.value}"
        )


@dataclass(frozen=True)
class SourcingReport:
    checks: tuple[SourcingCheck, ...]

    @property
    def passes(self) -> tuple[SourcingCheck, ...]:
        return tuple(
            check for check in self.checks if check.status is sv.CheckStatus.PASS
        )

    @property
    def failures(self) -> tuple[SourcingCheck, ...]:
        return tuple(
            check for check in self.checks if check.status is sv.CheckStatus.FAIL
        )

    @property
    def is_valid(self) -> bool:
        return not self.failures


def check_design(design) -> SourcingReport:
    from earthground.analysis import DesignAnalysis

    checks = []
    for resolved in DesignAnalysis(design).components:
        component = resolved.component
        if component.virtual or component.dnp:
            continue
        lifecycle = component.lifecycle
        status = (
            sv.CheckStatus.PASS
            if lifecycle is Lifecycle.ACTIVE
            else sv.CheckStatus.FAIL
        )
        checks.append(
            SourcingCheck(
                refdes=resolved.refdes,
                mpn=component.mpn,
                lifecycle=lifecycle,
                status=status,
            )
        )
    return SourcingReport(tuple(checks))

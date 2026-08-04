"""Typed component sourcing metadata and design-level lifecycle reporting."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Protocol

import earthground.standard_values as sv


class Lifecycle(Enum):
    ACTIVE = "Active"
    NRND = "Not Recommended for New Designs"
    EOL = "End of Life"
    OBSOLETE = "Obsolete"
    PREVIEW = "Preview"
    UNKNOWN = "Unknown"


class EvidenceMode(Enum):
    """How procurement or documentation evidence is supplied for a component."""

    DIRECT = "Direct"
    RESOLVER = "Resolver"
    NOT_APPLICABLE = "Not Applicable"


@dataclass(frozen=True, kw_only=True)
class SourcingEvidence:
    mpn: str
    lifecycle: Lifecycle = Lifecycle.UNKNOWN
    datasheet: str = ""
    datasheet_revision: str = ""
    datasheet_sha256: str = ""
    source: Optional[str] = None


class SourcingResolver(Protocol):
    def resolve(self, component) -> Optional[SourcingEvidence]: ...


@dataclass(frozen=True)
class SourcingCheck:
    refdes: str
    mpn: str
    lifecycle: Lifecycle
    status: sv.CheckStatus
    applicable: bool = True
    source: Optional[str] = None

    def __str__(self) -> str:
        if not self.applicable:
            return f"SOURCING Pass at {self.refdes}: not applicable"
        identity = self.mpn or "unspecified MPN"
        source = f" [source: {self.source}]" if self.source else ""
        return (
            f"SOURCING {self.status.value} at {self.refdes}: "
            f"{identity} lifecycle is {self.lifecycle.value}{source}"
        )


@dataclass(frozen=True)
class SourcingReport:
    checks: tuple[SourcingCheck, ...]

    @property
    def items(self):
        return self.checks

    @property
    def passes(self) -> tuple[SourcingCheck, ...]:
        return tuple(
            check
            for check in self.checks
            if check.applicable and check.status is sv.CheckStatus.PASS
        )

    @property
    def failures(self) -> tuple[SourcingCheck, ...]:
        return tuple(
            check for check in self.checks if check.status is sv.CheckStatus.FAIL
        )

    @property
    def unknowns(self) -> tuple[SourcingCheck, ...]:
        return tuple(
            check for check in self.checks if check.status is sv.CheckStatus.UNKNOWN
        )

    @property
    def not_applicable(self) -> tuple[SourcingCheck, ...]:
        return tuple(check for check in self.checks if not check.applicable)

    @property
    def blocking(self) -> tuple[SourcingCheck, ...]:
        return self.failures + self.unknowns

    @property
    def is_valid(self) -> bool:
        return not self.blocking


def _direct_evidence(component) -> SourcingEvidence:
    return SourcingEvidence(
        mpn=component.mpn,
        lifecycle=component.lifecycle,
        datasheet=component.datasheet,
        datasheet_revision=component.datasheet_revision,
        datasheet_sha256=component.datasheet_sha256,
        source="component metadata",
    )


def _resolver_evidence(design, component) -> Optional[SourcingEvidence]:
    resolvers = [
        resolver
        for page in design.iter_designs()
        for resolver in page._sourcing_resolvers
    ]
    for resolver in resolvers:
        evidence = (
            resolver.resolve(component)
            if hasattr(resolver, "resolve")
            else resolver(component)
        )
        if evidence is not None:
            if not isinstance(evidence, SourcingEvidence):
                raise TypeError(
                    "Sourcing resolver must return SourcingEvidence or None"
                )
            return evidence
    return None


def resolve_component(design, component) -> Optional[SourcingEvidence]:
    mode = component.procurement_mode
    if mode is EvidenceMode.NOT_APPLICABLE:
        return None
    if mode is EvidenceMode.DIRECT or component.mpn:
        return _direct_evidence(component)
    return _resolver_evidence(design, component)


def resolve_documentation(design, component) -> Optional[SourcingEvidence]:
    mode = component.documentation_mode
    if mode is EvidenceMode.NOT_APPLICABLE:
        return None
    if mode is EvidenceMode.DIRECT or component.datasheet:
        return _direct_evidence(component)
    return _resolver_evidence(design, component)


def _status(evidence: Optional[SourcingEvidence]) -> sv.CheckStatus:
    if evidence is None or not evidence.mpn or evidence.lifecycle is Lifecycle.UNKNOWN:
        return sv.CheckStatus.UNKNOWN
    if evidence.lifecycle is Lifecycle.ACTIVE:
        return sv.CheckStatus.PASS
    return sv.CheckStatus.FAIL


def check_design(design) -> SourcingReport:
    from earthground.analysis import DesignAnalysis

    checks = []
    for resolved in DesignAnalysis(design).components:
        component = resolved.component
        if component.virtual or component.dnp:
            continue
        applicable = component.procurement_mode is not EvidenceMode.NOT_APPLICABLE
        evidence = resolve_component(design, component)
        lifecycle = Lifecycle.UNKNOWN if evidence is None else evidence.lifecycle
        status = sv.CheckStatus.PASS if not applicable else _status(evidence)
        checks.append(
            SourcingCheck(
                refdes=resolved.refdes,
                mpn="" if evidence is None else evidence.mpn,
                lifecycle=lifecycle,
                status=status,
                applicable=applicable,
                source=None if evidence is None else evidence.source,
            )
        )
    return SourcingReport(tuple(checks))

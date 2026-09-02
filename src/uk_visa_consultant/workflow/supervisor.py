"""CaseSupervisor — the deterministic state machine (docs/AGENT-WORKFLOW.md).

Runs a case through the built states: `intake` (documents already parsed) →
`gathering` (gap analysis) → `review` (assembly + gates) → `delivered` (PASS) /
`gathering` (FAIL) / `parked` (HOLD). Transitions are code, never model output.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from uk_visa_consultant.gaps.gap import analyze
from uk_visa_consultant.models import Document, GapReport, Package, RequirementSet, VerificationResult
from uk_visa_consultant.workflow.assembly import assemble
from uk_visa_consultant.workflow.gates import verify


class WorkflowResult(BaseModel):
    final_state: str  # gathering | review | parked | delivered | closed
    gap_report: GapReport | None = None
    package: Package | None = None
    checks: list[VerificationResult] = Field(default_factory=list)
    documents: list[Document] = Field(default_factory=list)
    trace: list[str] = Field(default_factory=list)


class CaseSupervisor:
    def run(self, documents: list[Document], requirement_set: RequirementSet,
            client: dict[str, Any]) -> WorkflowResult:
        trace = ["intake → gathering (route identified)"]
        gap = analyze(documents, requirement_set, client)

        if gap.status != "READY":
            trace.append("gathering (gap INCOMPLETE — stay in gathering)")
            return WorkflowResult(final_state="gathering", gap_report=gap,
                                  documents=documents, trace=trace)

        trace.append("gathering → review (gap READY)")
        package = assemble(documents, requirement_set, gap, client)
        final, checks = verify(package, gap, documents, client)
        package.checks = checks

        if final == "PASS":
            trace.append("review → delivered (gates PASS)")
            return WorkflowResult(final_state="delivered", gap_report=gap, package=package,
                                  checks=checks, documents=documents, trace=trace)
        if final == "HOLD":
            trace.append("review → parked (gate HOLD)")
            return WorkflowResult(final_state="parked", gap_report=gap, package=package,
                                  checks=checks, documents=documents, trace=trace)
        trace.append("review → gathering (gate FAIL)")
        return WorkflowResult(final_state="gathering", gap_report=gap, package=package,
                              checks=checks, documents=documents, trace=trace)

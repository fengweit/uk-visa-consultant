"""CaseSupervisor — the deterministic state machine (docs/AGENT-WORKFLOW.md).

Runs a case through the states that are built: `intake` (documents already
parsed by IntakeAgent upstream) → `gathering` (gap analysis) → `review` (READY).
`parked`/`delivered` arrive with HITL and assembly. Transitions are code, never
model output.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from uk_visa_consultant.gaps.gap import analyze
from uk_visa_consultant.models import Document, GapReport, RequirementSet


class WorkflowResult(BaseModel):
    final_state: str  # gathering | review | parked | delivered | closed
    gap_report: GapReport | None = None
    documents: list[Document] = Field(default_factory=list)
    trace: list[str] = Field(default_factory=list)


class CaseSupervisor:
    def run(self, documents: list[Document], requirement_set: RequirementSet,
            client: dict[str, Any]) -> WorkflowResult:
        trace = ["intake → gathering (route identified)"]
        gap = analyze(documents, requirement_set, client)
        if gap.status == "READY":
            trace.append("gathering → review (gap READY)")
            return WorkflowResult(final_state="review", gap_report=gap,
                                  documents=documents, trace=trace)
        trace.append("gathering (gap INCOMPLETE — stay in gathering)")
        return WorkflowResult(final_state="gathering", gap_report=gap,
                              documents=documents, trace=trace)

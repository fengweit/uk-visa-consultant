"""Eval harness — golden-set runner with a promotion bar (docs/specs/eval-harness.md).

A module is "promoted" only when its pass rate clears the bar. This is the
ordering constraint from docs/STABILITY.md: checks before humans.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Report:
    module: str
    total: int = 0
    passed: int = 0
    failures: list[tuple[str, str, str]] = field(default_factory=list)  # (id, expected, actual)
    bar: float = 0.95

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 0.0

    @property
    def promoted(self) -> bool:
        return self.total > 0 and self.pass_rate >= self.bar

    def __str__(self) -> str:
        verdict = "PROMOTED" if self.promoted else "BLOCKED"
        return (f"{self.module}: {self.passed}/{self.total} passed "
                f"({self.pass_rate:.0%}), bar {self.bar:.0%} -> {verdict}")


def run(module: str, cases: list[tuple[str, object, object]], bar: float = 0.95) -> Report:
    """cases: list of (fixture_id, expected, actual); equality is the default check."""
    report = Report(module=module, bar=bar)
    for fid, expected, actual in cases:
        report.total += 1
        if actual == expected:
            report.passed += 1
        else:
            report.failures.append((fid, str(expected), str(actual)))
    return report

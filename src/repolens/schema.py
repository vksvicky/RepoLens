"""Canonical finding report schema."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class Severity(StrEnum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


Priority = Literal["P1", "P2", "P3"]
FixTiming = Literal["immediately", "before launch", "after launch", "if time permits"]


class Issue(BaseModel):
    severity: Severity
    priority: Priority
    category: str
    file: str
    line: int = Field(ge=1)
    title: str
    explanation: str
    impact: str = ""
    recommendedFix: str
    codeExample: str = ""
    fixTiming: FixTiming = "before launch"
    cwe: str | None = None
    owasp: str | None = None

    @model_validator(mode="after")
    def require_impact_and_example_for_high(self) -> Issue:
        if self.severity in {Severity.CRITICAL, Severity.HIGH}:
            if not self.impact.strip():
                raise ValueError("Critical/High findings require non-empty impact")
            if not self.codeExample.strip():
                raise ValueError("Critical/High findings require non-empty codeExample")
        return self


class Summary(BaseModel):
    critical: int = Field(ge=0, default=0)
    high: int = Field(ge=0, default=0)
    medium: int = Field(ge=0, default=0)
    low: int = Field(ge=0, default=0)


class ArchitectureScores(BaseModel):
    architecture: int = Field(ge=1, le=10)
    security: int = Field(ge=1, le=10)
    maintainability: int = Field(ge=1, le=10)
    performance: int = Field(ge=1, le=10)
    scalability: int = Field(ge=1, le=10)
    productionReadiness: int = Field(ge=1, le=10)


class ScannerRun(BaseModel):
    tool: str
    status: Literal["ran", "skipped", "failed"]
    detail: str = ""
    findingCount: int = Field(ge=0, default=0)


class FindingReport(BaseModel):
    schemaVersion: str = "1.0"
    confidence: int = Field(ge=0, le=100)
    summary: Summary
    issues: list[Issue] = Field(default_factory=list)
    durabilityGaps: list[str] = Field(default_factory=list)
    scores: ArchitectureScores | None = None
    scannerRuns: list[ScannerRun] = Field(default_factory=list)

    @field_validator("confidence")
    @classmethod
    def confidence_range(cls, value: int) -> int:
        if not 0 <= value <= 100:
            raise ValueError("confidence must be 0–100")
        return value

    def recount_summary(self) -> Summary:
        counts = Summary()
        for issue in self.issues:
            if issue.severity == Severity.CRITICAL:
                counts.critical += 1
            elif issue.severity == Severity.HIGH:
                counts.high += 1
            elif issue.severity == Severity.MEDIUM:
                counts.medium += 1
            else:
                counts.low += 1
        return counts

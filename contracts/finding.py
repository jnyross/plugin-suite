"""Audit finding record shared by gates, judges, and extractors."""

from dataclasses import dataclass

SEVERITIES = ("error", "warning", "proposal", "info")


@dataclass
class Finding:
    code: str
    severity: str
    path: str
    evidence: str
    source: str = "gate"
    op_hint: str | None = None

    def __post_init__(self):
        if self.severity not in SEVERITIES:
            raise ValueError(f"severity must be one of {SEVERITIES}, got {self.severity!r}")

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "severity": self.severity,
            "path": self.path,
            "evidence": self.evidence,
            "source": self.source,
            "op_hint": self.op_hint,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Finding":
        return cls(
            code=data["code"],
            severity=data["severity"],
            path=data["path"],
            evidence=data["evidence"],
            source=data.get("source", "gate"),
            op_hint=data.get("op_hint"),
        )

"""Skill spec contract for proposed mutations."""

import re
from dataclasses import dataclass, field

MUTATION_POLICIES = ("read_only", "scoped", "broad")
_NAME_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


@dataclass
class Spec:
    name: str
    purpose: str
    triggers: list[str]
    non_triggers: list[str]
    inputs: str
    mutation_policy: str
    verification: list[str]
    boundaries: list[str]
    open_questions: list[str] = field(default_factory=list)

    def validate(self) -> None:
        if not self.name:
            raise ValueError("spec.name must be non-empty")
        if not _NAME_RE.fullmatch(self.name):
            raise ValueError(f"spec.name must be lowercase-hyphen-case, got {self.name!r}")
        if self.mutation_policy not in MUTATION_POLICIES:
            raise ValueError(
                f"spec.mutation_policy must be one of {MUTATION_POLICIES}, got {self.mutation_policy!r}"
            )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "purpose": self.purpose,
            "triggers": list(self.triggers),
            "non_triggers": list(self.non_triggers),
            "inputs": self.inputs,
            "mutation_policy": self.mutation_policy,
            "verification": list(self.verification),
            "boundaries": list(self.boundaries),
            "open_questions": list(self.open_questions),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Spec":
        return cls(
            name=data["name"],
            purpose=data["purpose"],
            triggers=list(data["triggers"]),
            non_triggers=list(data["non_triggers"]),
            inputs=data["inputs"],
            mutation_policy=data["mutation_policy"],
            verification=list(data["verification"]),
            boundaries=list(data["boundaries"]),
            open_questions=list(data["open_questions"]),
        )

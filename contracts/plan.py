"""Mutation plan record with an explicit status machine."""

from dataclasses import dataclass, field

PLAN_STATUSES = ("draft", "approved", "applied", "rolled_back")
TRANSITIONS = {
    "draft": {"approved"},
    "approved": {"applied", "rolled_back"},
    "applied": set(),
    "rolled_back": set(),
}


@dataclass
class OpCall:
    op: str
    args: dict
    rationale: str


@dataclass
class Plan:
    id: str
    target: str
    ops: list[OpCall]
    predicted_delta: dict
    rollback: dict
    status: str = "draft"
    decision_ref: str | None = None

    def transition(self, new_status: str) -> None:
        allowed = TRANSITIONS.get(self.status, set())
        if new_status not in allowed:
            raise ValueError(
                f"illegal plan transition {self.status!r} -> {new_status!r}; allowed: {sorted(allowed)}"
            )
        self.status = new_status

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "target": self.target,
            "ops": [{"op": o.op, "args": o.args, "rationale": o.rationale} for o in self.ops],
            "predicted_delta": self.predicted_delta,
            "rollback": self.rollback,
            "status": self.status,
            "decision_ref": self.decision_ref,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Plan":
        return cls(
            id=data["id"],
            target=data["target"],
            ops=[OpCall(op=o["op"], args=o["args"], rationale=o["rationale"]) for o in data["ops"]],
            predicted_delta=data["predicted_delta"],
            rollback=data["rollback"],
            status=data.get("status", "draft"),
            decision_ref=data.get("decision_ref"),
        )

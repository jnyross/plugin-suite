"""Profile kinds, thresholds, and gate assignments."""

from dataclasses import dataclass, field

KINDS = ("single-skill", "collection", "router-plugin")
DEFAULT_THRESHOLDS = {"large_file": 300, "split_required": 500}


@dataclass
class Profile:
    kind: str
    entry: str | None = None
    thresholds: dict = field(default_factory=lambda: dict(DEFAULT_THRESHOLDS))
    gates: tuple[str, ...] = ()

    def __post_init__(self):
        if self.kind not in KINDS:
            raise ValueError(f"profile kind must be one of {KINDS}, got {self.kind!r}")
        if self.kind == "router-plugin":
            if not self.entry:
                raise ValueError("router-plugin profile requires an entry skill folder name")
        elif self.kind == "collection" and self.entry is not None:
            raise ValueError(f"entry must be None for kind {self.kind!r}, got {self.entry!r}")

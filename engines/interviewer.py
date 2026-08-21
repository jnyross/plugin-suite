"""Interview-driven Spec authoring: grilling state machine over Spec fields."""

import json
import re
from pathlib import Path

from contracts.spec import MUTATION_POLICIES, Spec

FIELD_ORDER = [
    ("name", "What is the skill/plugin name (lowercase-hyphen-case)?"),
    ("purpose", "One sentence: what does it do and for whom?"),
    ("triggers", "List concrete example requests that should invoke it (one per line, empty line to finish):"),
    ("non_triggers", "List requests that should NOT invoke it (empty line to finish):"),
    ("inputs", "What does the user provide when invoking it?"),
    ("mutation_policy", "Mutation policy? [read_only|scoped|broad]"),
    ("verification", "List observable checks proving it worked (empty line to finish):"),
    ("boundaries", "What will it explicitly NOT do? (empty line to finish):"),
]
MULTI_FIELDS = frozenset({"triggers", "non_triggers", "verification", "boundaries"})
REQUIRED_LISTS = frozenset({"triggers", "verification"})
MAX_ATTEMPTS = 3
STATE_RELPATH = Path(".suite") / "interview.json"
_NAME_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


class _Exhausted(Exception):
    """Scripted answer source ran dry; run() returns the partial spec."""


def _empty_spec() -> Spec:
    return Spec(
        name="", purpose="", triggers=[], non_triggers=[], inputs="",
        mutation_policy="", verification=[], boundaries=[],
    )


class Interview:
    """Walks FIELD_ORDER, grilling each field, into a Spec."""

    def __init__(self, spec: Spec | None = None, answers: list[str] | None = None, ask=None):
        self.spec = spec if spec is not None else _empty_spec()
        self.answers = list(answers) if answers is not None else None
        self.ask = ask

    def run(self) -> Spec:
        try:
            for field, question in FIELD_ORDER:
                if getattr(self.spec, field):
                    continue
                if field == "name":
                    self._fill_name(question)
                elif field == "mutation_policy":
                    self._fill_policy(question)
                elif field in MULTI_FIELDS:
                    self._fill_list(field, question)
                else:
                    self._set(field, self._line(question).strip())
        except _Exhausted:
            pass
        try:
            self.spec.validate()
        except ValueError as exc:
            self._defer("spec", str(exc))
        return self.spec

    def _line(self, prompt: str) -> str:
        if self.answers is not None:
            if not self.answers:
                raise _Exhausted()
            return self.answers.pop(0)
        ask = self.ask if self.ask is not None else input
        return ask(prompt)

    def _set(self, field: str, value) -> None:
        setattr(self.spec, field, value)
        prefix = f"unresolved {field}:"
        self.spec.open_questions = [q for q in self.spec.open_questions if not q.startswith(prefix)]

    def _defer(self, field: str, reason: str) -> None:
        entry = f"unresolved {field}: {reason}"
        if entry not in self.spec.open_questions:
            self.spec.open_questions.append(entry)

    def _fill_name(self, question: str) -> None:
        value = ""
        for _ in range(MAX_ATTEMPTS):
            value = self._line(question).strip()
            if _NAME_RE.fullmatch(value):
                self._set("name", value)
                return
        self._set("name", value)
        self._defer("name", f"expected lowercase-hyphen-case after {MAX_ATTEMPTS} attempts, last {value!r}")

    def _fill_policy(self, question: str) -> None:
        value = ""
        for _ in range(MAX_ATTEMPTS):
            value = self._line(question).strip()
            if value in MUTATION_POLICIES:
                self._set("mutation_policy", value)
                return
        self._set("mutation_policy", "read_only")
        self._defer(
            "mutation_policy",
            f"no valid policy after {MAX_ATTEMPTS} attempts; assuming read_only",
        )

    def _fill_list(self, field: str, question: str) -> None:
        entries: list[str] = []
        for _ in range(MAX_ATTEMPTS):
            entries.clear()
            while True:
                line = self._line(question if not entries else "> ").strip()
                if line == "":
                    break
                entries.append(line)
            if entries or field not in REQUIRED_LISTS:
                self._set(field, entries)
                return
        self._set(field, entries)
        self._defer(field, f"needs at least one entry; none provided after {MAX_ATTEMPTS} attempts")


def save(state_dir: Path, interview: Interview) -> Path:
    path = Path(state_dir) / STATE_RELPATH
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "spec": interview.spec.to_dict(),
        "answers_remaining": list(interview.answers or []),
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def load(state_dir: Path) -> Interview:
    path = Path(state_dir) / STATE_RELPATH
    payload = json.loads(path.read_text(encoding="utf-8"))
    return Interview(spec=Spec.from_dict(payload["spec"]), answers=payload.get("answers_remaining"))

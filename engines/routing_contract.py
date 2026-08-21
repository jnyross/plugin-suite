"""Deterministic executable contract for router evaluation corpora."""

import re
from dataclasses import dataclass
from pathlib import Path

READ_ONLY = {"read-only", "readonly", "do not change", "don't change", "no edits", "without editing"}
QUESTION_WORDS = {"how", "why", "what", "when", "where", "which", "who", "whose", "whom"}
ADVISORY = re.compile(r"(?:should|shall|do|does|did|is|are|am|may|might)\s+(?:i|we)\b")
DETERMINERS = {"this", "that", "these", "those", "the", "a", "an"}

ROUTE_BULLET = re.compile(r"^\s*-\s*Select\s+\*\*([A-Za-z][A-Za-z ]*)\*\*\s+for\s+([^.]+)\.(.*)$")
PLAYBOOK_STEM = re.compile(r"\[([a-z0-9-]+)\.md\]")
TOKEN = re.compile(r"[a-z]+(?:-[a-z]+)?")
WORD = re.compile(r"[a-z]+(?:-[a-z]+)?")
SENTENCE_SPLIT = re.compile(r"[.!?\n;]")
POLITE_DIRECT = re.compile(r"\b(?:can|could|would|will)\s+you\b")


@dataclass(frozen=True)
class Route:
    """One routing path: its trigger vocabulary and playbook stem."""

    vocab: frozenset[str]
    stem: str


@dataclass(frozen=True)
class Contract:
    """Routes[0] is the read-only path; later routes are change-family paths."""

    routes: tuple[Route, ...]

    def classify(self, text: str) -> dict[str, str]:
        read_only = self.routes[0]
        non_read = frozenset().union(*(route.vocab for route in self.routes[1:]))
        lowered = text.lower()
        words = set(WORD.findall(lowered))
        if any(marker in lowered for marker in READ_ONLY):
            return {"route": read_only.stem, "mutation": "none", "reason": "explicit read-only constraint"}
        polite_direct = bool(POLITE_DIRECT.search(lowered))
        content_question = advisory_question = imperative_change = False
        change_candidates = set()
        for sentence in SENTENCE_SPLIT.split(lowered):
            tokens = WORD.findall(sentence)
            if not tokens:
                continue
            if tokens[0] in QUESTION_WORDS:
                content_question = True
            if ADVISORY.match(sentence):
                advisory_question = True
            if tokens[0] in non_read:
                imperative_change = True
            for idx, token in enumerate(tokens):
                if token in non_read and not (idx and tokens[idx - 1] in DETERMINERS):
                    change_candidates.add(token)
        if not polite_direct and (content_question or advisory_question) and not imperative_change:
            return {"route": read_only.stem, "mutation": "none", "reason": "explanatory or advisory question"}
        investigation = bool(words & read_only.vocab)
        for route in self.routes[1:]:
            if change_candidates & route.vocab:
                reason = "request authorizes investigation and change" if investigation else "explicit change intent"
                return {"route": route.stem, "mutation": "scoped", "reason": reason}
        if investigation:
            return {"route": read_only.stem, "mutation": "none", "reason": "read-only inquiry intent"}
        return {"route": "fallback", "mutation": "none", "reason": "no proven playbook match"}


def derive_contract(skill_md: Path) -> Contract:
    """Parse every route bullet in a SKILL.md into an executable Contract."""
    routes: list[Route] = []
    seen: dict[str, str] = {}
    for line in skill_md.read_text(encoding="utf-8").splitlines():
        match = ROUTE_BULLET.match(line)
        if not match:
            continue
        vocab = set()
        for raw in match.group(2).split(","):
            token = raw.strip().removeprefix("or ")
            if not TOKEN.fullmatch(token):
                raise SystemExit(f"unparsable routing vocabulary in {skill_md}")
            if token in seen:
                raise SystemExit(f"unparsable routing vocabulary in {skill_md} (duplicate vocabulary: {token})")
            seen[token] = match.group(1).strip()
            vocab.add(token)
        stem = PLAYBOOK_STEM.search(match.group(3))
        if not stem:
            raise SystemExit(f"unparsable routing vocabulary in {skill_md}")
        routes.append(Route(frozenset(vocab), stem.group(1)))
    if not routes:
        raise SystemExit(f"unparsable routing vocabulary in {skill_md}")
    return Contract(tuple(routes))

"""Role 1 - the Theorist.

Turns a Layer-9 conflict plus Kevin's candidates into a precise theory: terms, mechanism,
preconditions, predictions and an explicit demarcation from the trivial reading. The LLM
phrases; this engine fixes the *shape* (closed fields, clamped counts) and, on a revision
round, folds the Falsifier's weakest assumption into the preconditions deterministically so
each iteration is a real, reproducible change rather than a re-roll.
"""

from __future__ import annotations

from .llm_client import LLMClient
from .models import ResearchTask, Theory

_MAX_PREDICTIONS = 4


class Theorist:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    def formulate(self, task: ResearchTask, *, address: str = "") -> Theory:
        """Formulate a theory. ``address`` is a concern from a prior round (the Falsifier's
        weakest assumption or a reviewer reason) that the new theory must explicitly pin
        down - this is how the controlled circle makes progress without randomness."""
        data = self._llm.theorize(task.conflict, list(task.candidates))
        statement = str(data.get("statement", "")).strip() or _fallback_statement(task)

        preconditions = _as_tuple(data.get("preconditions"))
        if address:
            # Deterministically tighten: the open concern becomes a stated precondition,
            # so the theory now *commits* on what last round left loose.
            pinned = f"explicitly controls for: {address}"
            if pinned not in preconditions:
                preconditions = (*preconditions, pinned)

        return Theory(
            statement=statement,
            terms=_as_tuple(data.get("terms")),
            mechanism=str(data.get("mechanism", "")).strip(),
            preconditions=preconditions,
            predictions=_as_tuple(data.get("predictions"))[:_MAX_PREDICTIONS],
            demarcation=str(data.get("demarcation", "")).strip(),
        )


def _as_tuple(value) -> tuple[str, ...]:
    if not value:
        return ()
    if isinstance(value, str):
        return (value.strip(),)
    return tuple(str(v).strip() for v in value if str(v).strip())


def _fallback_statement(task: ResearchTask) -> str:
    lead = (task.candidates[0] if task.candidates else task.conflict).strip().rstrip(".")
    return f"Provisional theory addressing the conflict: {lead}."

"""Role 2 - the Literature Scout.

Maps the field around the theory: existing accounts, competing explanations, known
counterexamples and usable datasets/benchmarks, and turns them into weighed evidence for
and against. Offline it is a *deterministic stub* (replay-stable, no network); a real
search backend can be injected without touching the orchestrator.

The strengths it assigns are conservative and rule-based: internally generated leads are
weak SOURCES, never strong evidence. The Scout cannot, by construction, hand the team a
decisive citation it did not actually verify.
"""

from __future__ import annotations

from typing import Protocol

from .llm_client import _salient_terms
from .models import EvidenceItem, LiteratureFindings, ResearchTask, Theory

# Internally generated leads are deliberately weak: a stub citation is a hint to chase, not
# corroboration. A real, verified source backend may assign higher strengths.
_STUB_FOR_STRENGTH = 0.25
_STUB_AGAINST_STRENGTH = 0.35   # we weight the *against* side a touch higher, on purpose


class SearchBackend(Protocol):
    """Optional real-search seam. Returns ``(related, competing, counterexamples,
    datasets)`` lists of strings. When absent, the deterministic stub is used."""

    def search(self, query: str) -> dict: ...


class LiteratureScout:
    def __init__(self, backend: SearchBackend | None = None) -> None:
        self._backend = backend

    def survey(self, theory: Theory, task: ResearchTask) -> LiteratureFindings:
        if self._backend is not None:
            data = self._backend.search(theory.statement)  # pragma: no cover - real backend
        else:
            data = self._stub(theory, task)

        related = tuple(data.get("related", ()))
        competing = tuple(data.get("competing", ()))
        counter = tuple(data.get("counterexamples", ()))
        datasets = tuple(data.get("datasets", ()))

        evidence_for = [
            EvidenceItem(text=r, ref=f"lit:{i}", strength=_STUB_FOR_STRENGTH)
            for i, r in enumerate(related)
        ]
        evidence_against = [
            EvidenceItem(text=c, ref=f"counter:{i}", strength=_STUB_AGAINST_STRENGTH)
            for i, c in enumerate(counter)
        ]
        return LiteratureFindings(
            related_work=related,
            competing_explanations=competing,
            known_counterexamples=counter,
            datasets=datasets,
            evidence_for=evidence_for,
            evidence_against=evidence_against,
        )

    def _stub(self, theory: Theory, task: ResearchTask) -> dict:
        """A deterministic, content-free literature map keyed off the theory's terms."""
        terms = theory.terms or _salient_terms(theory.statement) or ("the phenomenon",)
        t0 = terms[0]
        t1 = terms[1] if len(terms) > 1 else t0
        return {
            "related": (
                f"An existing line of work treats {t0} as the primary driver.",
                f"A second tradition models {t0} and {t1} as jointly determined.",
            ),
            "competing": (
                f"Rival explanation A: the link is confounded by an unmeasured cause of {t0}.",
                f"Rival explanation B: the effect is an artefact of how {t1} is measured.",
            ),
            "counterexamples": (
                f"A reported case where {t0} varied but the predicted effect did not appear.",
            ),
            "datasets": (
                f"A public benchmark with annotated {t0} suitable for a first replication.",
            ),
        }

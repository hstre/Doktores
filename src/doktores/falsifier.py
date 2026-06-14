"""Role 3 - the Falsifier.

Tries to *destroy* the theory before anyone invests in it. It asks the four hard questions
and answers them by rule, not by taste:

  * **Is it falsifiable?** Are there predictions, and do they forbid an observable outcome?
  * **Is it merely a renaming?** Does it add a mechanism and new terms, or just re-label the
    conflict it came from?
  * **Is there a simpler explanation?** Is the mechanism doing any work the data needs?
  * **What is the weakest assumption?** The one that, if it fails, takes the theory with it.

The booleans are deterministic signals; the LLM only *phrases* the refutation conditions and
the weakest assumption. A theory that is unfalsifiable or a mere renaming is :pyattr:`fatal`
- the Adversarial Reviewer turns that into a REJECT.
"""

from __future__ import annotations

from .llm_client import LLMClient, _salient_terms
from .models import EvidenceItem, FalsificationReport, ResearchTask, Theory

# Surface markers of a prediction that forbids something observable. Content-free and
# deterministic: presence of any of these in a prediction makes it testable.
_FALSIFIABLE_MARKERS = (
    "more", "less", "reduce", "reduc", "increase", "decrease", "higher", "lower",
    "outperform", "disappear", "monoton", "margin", "than", "no change", "no effect",
    "removing", "remove", "perturb", "fixed", "should", "predict",
)
_MIN_MECHANISM_LEN = 12


class Falsifier:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    def attack(self, theory: Theory, task: ResearchTask) -> FalsificationReport:
        is_falsifiable = _is_falsifiable(theory)
        merely_renaming = _is_renaming(theory, task)

        # A simpler explanation looms when the mechanism is doing no work or the theory
        # cannot be tested - in either case Ockham prefers the rival.
        simpler = ""
        if not theory.mechanism.strip() or not is_falsifiable:
            simpler = self._llm.phrase(
                "review_reason",
                "a model without the proposed mechanism would fit the same observations",
            )

        n = max(len(theory.predictions), 2)
        refutations = tuple(self._llm.phrase_list("refutation", theory.statement, n))
        seed = theory.preconditions[0] if theory.preconditions else theory.statement
        weakest = self._llm.phrase("weakest_assumption", seed)

        evidence_against: list[EvidenceItem] = []
        if simpler:
            evidence_against.append(
                EvidenceItem(text=simpler, ref="falsifier:ockham", strength=0.4)
            )
        if merely_renaming:
            evidence_against.append(
                EvidenceItem(
                    text="The theory re-labels the conflict without adding a mechanism.",
                    ref="falsifier:renaming",
                    strength=0.6,
                )
            )

        return FalsificationReport(
            refutation_conditions=refutations,
            is_falsifiable=is_falsifiable,
            simpler_explanation=simpler,
            merely_renaming=merely_renaming,
            weakest_assumption=weakest,
            evidence_against=evidence_against,
        )


def _is_falsifiable(theory: Theory) -> bool:
    if not theory.predictions:
        return False
    return any(
        any(m in pred.lower() for m in _FALSIFIABLE_MARKERS) for pred in theory.predictions
    )


def _is_renaming(theory: Theory, task: ResearchTask) -> bool:
    """True when the theory adds neither a real mechanism nor any term beyond the words
    already in the conflict it came from - i.e. it only renames the problem."""
    conflict_words = set(_salient_terms(task.conflict))
    theory_terms = set(theory.terms) or set(_salient_terms(theory.statement))
    new_terms = theory_terms - conflict_words
    thin_mechanism = len(theory.mechanism.strip()) < _MIN_MECHANISM_LEN
    return thin_mechanism and not new_terms

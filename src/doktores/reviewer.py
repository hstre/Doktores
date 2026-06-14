"""Role 7 - the Adversarial Reviewer.

Judges the whole package the way a hard reviewer would, and is allowed to say no. The
verdict is computed by a fixed scorecard - never by the language layer - so the same work
always earns the same call:

  * A theory the Falsifier killed (unfalsifiable, or a mere renaming) is an immediate
    **REJECT**: it skips the epistemic channel entirely (the publication is still archived).
  * Otherwise the verdict comes from a weighted scorecard over falsifiability, method
    soundness, the balance of evidence, and whether real experiments exist - with a penalty
    when a simpler explanation is on the table.

``confidence`` is the scorecard value: a bounded *internal* number, explicitly **not** a
probability that the theory is true. The LLM only phrases the human-readable summary line.
"""

from __future__ import annotations

from .llm_client import LLMClient
from .models import (
    EvidenceItem,
    FalsificationReport,
    MethodReview,
    ReviewerVerdict,
    Theory,
    Verdict,
)

# Scorecard weights (sum to 1.0). Pure logic.
_W_FALSIFIABLE = 0.25
_W_SOUNDNESS = 0.35
_W_EVIDENCE = 0.25
_W_EXPERIMENTS = 0.15
_SIMPLER_PENALTY = 0.15

_ACCEPT_AT = 0.66
_REVISE_AT = 0.42


class AdversarialReviewer:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    def judge(
        self,
        theory: Theory,
        falsification: FalsificationReport,
        method_review: MethodReview,
        evidence_for: list[EvidenceItem],
        evidence_against: list[EvidenceItem],
        experiments: list,
    ) -> ReviewerVerdict:
        if falsification.fatal:
            why = (
                "unfalsifiable as stated" if not falsification.is_falsifiable
                else "a mere renaming of the conflict, adding no mechanism"
            )
            reason = self._llm.phrase("review_reason", f"rejected because the theory is {why}")
            return ReviewerVerdict(
                verdict=Verdict.REJECT,
                reasons=(f"Reject: {why}.", reason),
                confidence=round(0.15 * method_review.soundness, 4),
            )

        balance = _evidence_balance(evidence_for, evidence_against)
        score = (
            _W_FALSIFIABLE * 1.0
            + _W_SOUNDNESS * method_review.soundness
            + _W_EVIDENCE * balance
            + _W_EXPERIMENTS * (1.0 if experiments else 0.0)
        )
        if falsification.simpler_explanation:
            score -= _SIMPLER_PENALTY
        score = max(0.0, min(1.0, score))

        if score >= _ACCEPT_AT:
            verdict = Verdict.ACCEPT
        elif score >= _REVISE_AT:
            verdict = Verdict.REVISE
        else:
            verdict = Verdict.REJECT

        reasons = _reasons(verdict, method_review, balance, falsification, experiments)
        summary = self._llm.phrase(
            "review_reason", f"{verdict.value} at scorecard {score:.2f}; {reasons[0]}"
        )
        return ReviewerVerdict(
            verdict=verdict, reasons=(*reasons, summary), confidence=round(score, 4)
        )


def _evidence_balance(
    evidence_for: list[EvidenceItem], evidence_against: list[EvidenceItem]
) -> float:
    """Share of total weighed evidence that supports the theory, in [0, 1]. Neutral (0.5)
    when there is no evidence either way - absence is not support."""
    for_sum = sum(e.strength for e in evidence_for)
    against_sum = sum(e.strength for e in evidence_against)
    total = for_sum + against_sum
    return 0.5 if total == 0 else round(for_sum / total, 4)


def _reasons(
    verdict: Verdict,
    method_review: MethodReview,
    balance: float,
    falsification: FalsificationReport,
    experiments: list,
) -> tuple[str, ...]:
    out = [
        f"{verdict.value.title()}: falsifiable, method soundness {method_review.soundness:.2f}, "
        f"evidence balance {balance:.2f}, {len(experiments)} pilot(s).",
    ]
    if falsification.simpler_explanation:
        out.append("A simpler explanation is on the table and was penalised.")
    if method_review.soundness < 0.8:
        out.append("Method gaps remain: " + "; ".join(method_review.limitations[:2]))
    if verdict is Verdict.REVISE:
        out.append("Address the weakest assumption and re-submit: "
                   + falsification.weakest_assumption)
    return tuple(out)

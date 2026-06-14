"""Doktores - the orchestrator (the controlled circle).

This is the whole research organisation in one routing object. It owns no judgement of its
own; it *routes* between the seven roles in the order the design prescribes, loops where the
design says to loop, and assembles a replay-stable ``research_output`` package. The order is
**not** linear:

    1. Theorist        - formulate a precise theory from the conflict + Kevin's candidates
    2. Falsifier       - try to destroy it; if it is fatal and rounds remain, jump back to (1)
    3. Literature Scout- map competing explanations, counterexamples, datasets
    4. Designer        - minimal pilots, baselines, metrics, stop criteria
    5. Method Reviewer - score the design's soundness, list the gaps
    6. Paper Builder   - only now write it up
    7. Adversarial Rev.- accept | revise | reject  (revise jumps back to (1) for another round)

The terminal state is the Adversarial Reviewer saying ACCEPT or REJECT, or the round budget
running out (whatever the last round produced stands). Every decision - routing, scoring,
the verdict, the confidence, the recommended updates - is deterministic. The LLM only ever
phrased language inside the roles.

The boundary, in one line: **Doktores produces a SOURCE package; whether any of it becomes a
belief is decided by Joni alone.** That is why ``recommended_claim_updates`` only ever
*proposes* (``add_claim`` / ``open_conflict``) and a REJECT emits none at all.
"""

from __future__ import annotations

from .experimenter import ExperimentalDesigner
from .falsifier import Falsifier
from .literature import LiteratureScout, SearchBackend
from .llm_client import LLMClient, get_default_client
from .methodologist import MethodReviewer
from .models import (
    ClaimUpdate,
    ResearchOutput,
    ResearchTask,
    Verdict,
)
from .paper_builder import PaperBuilder
from .reviewer import AdversarialReviewer
from .theorist import Theorist

# Pilots are *designed* in v1, not executed - so results are honestly reported as unrun
# rather than invented. Wiring a real trial runner later only changes this string + the
# evidence it produces; no role changes.
_RESULTS_UNRUN = "not yet run"

# The provenance caveat stamped into every package's limitations. It is the boundary made
# explicit inside the artefact itself.
_SOURCE_CAVEAT = (
    "Internally produced and method-checked, not externally replicated: this package is a "
    "SOURCE for Joni's governance, not a confirmed belief."
)


class Doktores:
    def __init__(
        self,
        llm: LLMClient | None = None,
        *,
        search_backend: SearchBackend | None = None,
    ) -> None:
        self._llm = llm or get_default_client()
        self._theorist = Theorist(self._llm)
        self._falsifier = Falsifier(self._llm)
        self._scout = LiteratureScout(search_backend)
        self._designer = ExperimentalDesigner(self._llm)
        self._methodologist = MethodReviewer(self._llm)
        self._paper = PaperBuilder(self._llm)
        self._reviewer = AdversarialReviewer(self._llm)

    def run(self, task: ResearchTask, *, max_rounds: int = 3) -> ResearchOutput:
        """One full pass through the controlled circle. Deterministic given the same LLM.

        ``max_rounds`` bounds the Theorist/Falsifier/Reviewer loop: a REVISE (or an early
        fatal falsification) sends the work back to the Theorist with the open concern pinned
        as a new precondition, up to this many times. The last round's package is returned.
        """
        address = ""
        last: ResearchOutput | None = None

        for round_no in range(max(1, max_rounds)):
            final_round = round_no == max(1, max_rounds) - 1
            theory = self._theorist.formulate(task, address=address)
            falsification = self._falsifier.attack(theory, task)

            # Controlled jump-back: a fatal theory with rounds to spare goes back to the
            # Theorist to fix its weakest assumption, instead of wasting a full pipeline.
            if falsification.fatal and not final_round:
                address = falsification.weakest_assumption or "make the predictions falsifiable"
                continue

            literature = self._scout.survey(theory, task)
            experiments = self._designer.design(theory)
            method_review = self._methodologist.review(experiments)

            evidence_for = list(literature.evidence_for)
            evidence_against = [*literature.evidence_against, *falsification.evidence_against]

            review = self._reviewer.judge(
                theory, falsification, method_review, evidence_for, evidence_against, experiments
            )
            publication = self._paper.build(
                task, theory, literature, falsification, experiments, method_review, _RESULTS_UNRUN
            )

            last = ResearchOutput(
                source_hypothesis_ids=task.source_hypothesis_ids,
                theory=theory,
                evidence_for=evidence_for,
                evidence_against=evidence_against,
                experiments=experiments,
                results=_RESULTS_UNRUN,
                limitations=(*method_review.limitations, _SOURCE_CAVEAT),
                reviewer_verdict=review.verdict,
                confidence=review.confidence,
                recommended_claim_updates=_claim_updates(
                    task, theory, review.verdict, falsification
                ),
                publication=publication,
            )

            # Terminal verdicts end the circle; a REVISE spends another round pinning the
            # weakest assumption (or the reviewer's first concern) as a new precondition.
            if review.verdict in (Verdict.ACCEPT, Verdict.REJECT):
                return last
            address = falsification.weakest_assumption or (
                review.reasons[-1] if review.reasons else ""
            )

        assert last is not None  # the loop runs at least once
        return last


def _claim_updates(task, theory, verdict, falsification) -> list[ClaimUpdate]:
    """The epistemic channel - deterministic, and empty on REJECT.

    A REJECT skips the epistemic channel entirely (mirroring Joni's intake, which would skip
    it anyway): a theory the team itself rejected must not even *propose* a belief. Otherwise
    the theory enters as a candidate SOURCE claim, and - when it was seeded by existing
    Layer-9 claims - a conflict is held open against them so the tension stays visible. None
    of this confirms anything; Joni decides.
    """
    if verdict is Verdict.REJECT:
        return []
    updates = [ClaimUpdate(op="add_claim", text=theory.statement, topic=task.topic)]
    if task.source_hypothesis_ids:
        tension = (
            falsification.refutation_conditions[0]
            if falsification.refutation_conditions
            else theory.statement
        )
        updates.append(
            ClaimUpdate(
                op="open_conflict",
                text=f"New theory stands in tension with the seeding hypotheses: {tension}",
                topic=task.topic,
                against=task.source_hypothesis_ids,
            )
        )
    return updates


def research(task: ResearchTask, *, llm: LLMClient | None = None, max_rounds: int = 3) -> dict:
    """Convenience: run one task and return the schema-valid package dict."""
    return Doktores(llm).run(task, max_rounds=max_rounds).to_dict()

"""Each role does its job deterministically, with verdicts/scores in rules not language."""

from __future__ import annotations

from doktores.experimenter import ExperimentalDesigner
from doktores.falsifier import Falsifier
from doktores.literature import LiteratureScout
from doktores.llm_client import MockLLM
from doktores.methodologist import MethodReviewer
from doktores.models import ResearchTask, Theory
from doktores.reviewer import AdversarialReviewer
from doktores.theorist import Theorist

TASK = ResearchTask(
    conflict="routing prefers locality but memory prefers recency under drift",
    topic="routing",
    candidates=("recency is a proxy for relevance, not its cause",),
    source_hypothesis_ids=("C-12",),
)
LLM = MockLLM()


def test_theorist_produces_structured_falsifiable_theory():
    theory = Theorist(LLM).formulate(TASK)
    assert theory.statement
    assert theory.predictions          # something to test against
    assert theory.mechanism            # a mechanism, not a renaming


def test_theorist_address_is_pinned_as_precondition():
    theory = Theorist(LLM).formulate(TASK, address="confounding by an upstream cause")
    assert any("confounding by an upstream cause" in p for p in theory.preconditions)


def test_falsifier_flags_degenerate_theory_as_fatal():
    # No mechanism, no predictions, terms that only echo the conflict -> a mere renaming.
    degenerate = Theory(statement="routing locality memory recency", terms=("routing", "memory"))
    report = Falsifier(LLM).attack(degenerate, TASK)
    assert not report.is_falsifiable
    assert report.merely_renaming
    assert report.fatal


def test_falsifier_passes_a_real_theory():
    theory = Theorist(LLM).formulate(TASK)
    report = Falsifier(LLM).attack(theory, TASK)
    assert report.is_falsifiable
    assert not report.fatal
    assert report.weakest_assumption       # always names the load-bearing assumption


def test_method_reviewer_scores_a_full_design_higher_than_an_empty_one():
    theory = Theorist(LLM).formulate(TASK)
    experiments = ExperimentalDesigner(LLM).design(theory)
    full = MethodReviewer(LLM).review(experiments)
    empty = MethodReviewer(LLM).review([])
    assert 0.0 <= empty.soundness < full.soundness <= 1.0
    assert empty.concerns                  # an empty design draws every concern


def test_reviewer_rejects_fatal_and_can_accept_strong():
    theory = Theorist(LLM).formulate(TASK)
    experiments = ExperimentalDesigner(LLM).design(theory)
    method = MethodReviewer(LLM).review(experiments)
    lit = LiteratureScout().survey(theory, TASK)
    fals = Falsifier(LLM).attack(theory, TASK)

    strong = AdversarialReviewer(LLM).judge(
        theory, fals, method, lit.evidence_for, lit.evidence_against, experiments
    )
    assert strong.verdict.value in {"accept", "revise"}
    assert 0.0 <= strong.confidence <= 1.0

    degenerate = Theory(statement="routing memory", terms=("routing",))
    fatal = Falsifier(LLM).attack(degenerate, TASK)
    rejected = AdversarialReviewer(LLM).judge(degenerate, fatal, method, [], [], experiments)
    assert rejected.verdict.value == "reject"

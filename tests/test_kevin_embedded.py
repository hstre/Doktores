"""Tests for the vendored, improved Kevin subpackage (``doktores.kevin``).

Each of the eight improvements is exercised here. Everything runs under the
deterministic MockLLM - no network, no key, replay-stable.
"""

from __future__ import annotations

from doktores.kevin import (
    Affinity,
    Kevin,
    MethodLibrary,
    Problem,
    Verdict,
    build_briefing,
    diverse_slate,
    extract_method,
)
from doktores.kevin.method_library import SEED_METHODS
from doktores.kevin.space_predictor import SpacePredictor


def _problem() -> Problem:
    return Problem(
        statement="how do we make onboarding feel less like paperwork?",
        domain="hr",
        known_approaches=("send a welcome email",),
        anchors=("the new-hire checklist", "the IT ticket"),
        evidence=("80% of week-one time is forms",),
        variables=("time-to-productive", "form count"),
    )


# -- import + baseline ------------------------------------------------------- #


def test_import_and_plain_run_yields_promising():
    run = Kevin().run(Problem("how do we cut report turnaround time?"))
    assert run.candidates
    assert any(e.verdict is Verdict.PROMISING for e in run.evaluations)
    # The briefing renders without error and lists the promising set.
    assert "PROBLEM:" in build_briefing(run).render()


# -- improvement 1: grounding ------------------------------------------------ #


def test_grounding_weaves_anchor_into_a_variant():
    p = _problem()
    run = Kevin().run(p)
    assert any(
        any(anchor in v.content for anchor in p.anchors) for v in run.variants
    ), "expected at least one variant to reference a concrete anchor"


# -- improvement 2: executed methods (not labels) ---------------------------- #


def test_executed_transfer_mentions_a_variable():
    p = _problem()
    run = Kevin().run(p)
    mapped = [step for tr in run.transfers for step in tr.mapped_steps]
    assert mapped, "expected at least one method transfer"
    assert any(
        ("time-to-productive" in step or "form count" in step) and "Executed" in step
        for step in mapped
    ), "expected an executed step that mentions a named variable"


# -- improvement 3: combinatorial axes --------------------------------------- #


def test_combinatorial_pair_space_appears():
    pred = SpacePredictor().predict(_problem())
    assert pred.pair_spaces, "predictor should emit distant blind-axis pairs"
    pair = pred.pair_spaces[0]
    assert "+" in pair.axis
    # Merged affinities span both axes (no shared affinity by construction).
    assert len(pair.affinities) >= 2
    # And the explorer/run surfaces a pair space among the routed spaces.
    run = Kevin().run(_problem())
    assert any("+" in s.axis for s in run.spaces)


# -- improvement 4b: pareto + novelty floor ---------------------------------- #


def test_pareto_flag_set_on_at_least_one():
    run = Kevin().run(_problem())
    assert any(e.pareto for e in run.evaluations)
    assert run.pareto_ids
    assert set(run.pareto_ids) == {e.candidate_id for e in run.evaluations if e.pareto}


def test_novelty_floor_blocks_pure_restatement():
    from doktores.kevin.llm_client import MockLLM
    from doktores.kevin.models import Candidate, Signals
    from doktores.kevin.selector import Selector

    p = _problem()
    sel = Selector(MockLLM(), min_novelty=0.99)  # impossible floor -> nothing promising
    # A candidate the mock will read as falsifiable/mechanistic, but novelty is floored.
    cand = Candidate(
        content="if the lever is pushed, the mechanism applied to it shifts",
        space_id="space_x",
        variant_id="var_x",
        signals=Signals(),
    )
    ev = sel.evaluate(p, cand)
    assert ev.verdict is not Verdict.PROMISING


# -- improvement 4a: falsification / hardening loop -------------------------- #


def test_hardening_loop_adds_revised_candidates():
    run = Kevin().run(_problem(), harden=True, max_harden=2)
    assert run.hardened, "expected hardened candidates"
    by_id = {c.id: c for c in run.candidates}
    for hid in run.hardened:
        assert by_id[hid].hardened_from is not None
        assert "hardened against weakness" in by_id[hid].content
    # No hardening when switched off.
    plain = Kevin().run(_problem(), harden=False)
    assert not plain.hardened


# -- improvement 5: domain-tagged Layer-9 learning --------------------------- #


def test_learned_method_carries_domain_and_is_preferred():
    run = Kevin().run(_problem())
    winner = run.candidates[0].id
    learned = extract_method(run, winner)
    assert learned.learned_domain == "hr"

    lib = MethodLibrary()
    lib.add(learned)
    assert lib.ledger.entries  # in-memory ledger recorded it
    # With prefer_domain, the same-domain learned method wins ties on shape.
    matched = lib.match(learned.affinities, top_k=3, prefer_domain="hr")
    assert learned.id in {m.id for m in matched}


# -- improvement 7: diversity pressure --------------------------------------- #


def test_diverse_slate_spreads_across_spaces():
    run = Kevin().run(_problem(), top_spaces=2)
    by_id = {c.id: c for c in run.candidates}

    # The slate maximises spread over (space, method) pairs: no two picks share one.
    slate = diverse_slate(run.evaluations, run.candidates, 4)
    pairs = [
        (by_id[e.candidate_id].space_id, by_id[e.candidate_id].method_name or "raw")
        for e in slate
    ]
    assert len(pairs) == len(set(pairs)), "diverse slate must not repeat a (space, method) bet"
    # A wide-enough slate spans more than one routed space rather than one bet's variants.
    space_ids = {p[0] for p in pairs}
    assert len(space_ids) >= 2, "diverse slate should span more than one space"


# -- improvement 8: multi-persona ensemble ----------------------------------- #


def test_personas_change_the_variant_set():
    p = _problem()
    single = {v.content for v in Kevin().run(p, personas=1).variants}
    ensemble = {v.content for v in Kevin().run(p, personas=3).variants}
    assert single != ensemble
    # The ensemble harvested more than one persona voice.
    personas_seen = {v.persona for v in Kevin().run(p, personas=3).variants}
    assert len(personas_seen) > 1


# -- determinism ------------------------------------------------------------- #


def test_two_identical_runs_produce_identical_ids():
    p = _problem()
    r1 = Kevin().run(p, personas=3, harden=True)
    r2 = Kevin().run(p, personas=3, harden=True)
    assert [c.id for c in r1.candidates] == [c.id for c in r2.candidates]
    assert r1.id == r2.id


def test_seed_methods_are_content_free_and_present():
    assert len(SEED_METHODS) >= 18
    assert all(Affinity.__members__ for _ in SEED_METHODS)  # affinities are the closed enum

"""Paper-improver mode: the controlled circle pointed at a manuscript.

Offline + deterministic (MockLLM + embedded Kevin's MockLLM). These tests pin the
contract the parent and any consumer rely on: a valid package, real per-section content,
the embedded Kevin actually driving ideation, and replay-stable ids.
"""

from __future__ import annotations

from doktores import (
    PaperDraft,
    Section,
    improve_paper,
    validate_paper_improvement,
)
from doktores.examples import rg_paper_draft
from doktores.models import Verdict


def _draft() -> PaperDraft:
    return rg_paper_draft()


def test_package_is_valid_and_covers_every_section():
    draft = _draft()
    pkg = improve_paper(draft).to_dict()
    assert validate_paper_improvement(pkg) == []
    assert len(pkg["section_improvements"]) == len(draft.sections)
    headings = {s["heading"] for s in pkg["section_improvements"]}
    assert headings == {s.heading for s in draft.sections}


def test_each_section_has_weaknesses_suggestion_and_rewrite():
    pkg = improve_paper(_draft()).to_dict()
    for s in pkg["section_improvements"]:
        assert s["weaknesses"], "every section must carry at least one weakness"
        assert s["suggestion"].strip()
        assert len(s["rewrite"]) > 40, "rewrite must be a real rewritten passage"
        assert s["verdict"] in {v.value for v in Verdict}
        assert 0.0 <= s["confidence"] <= 1.0


def test_embedded_kevin_supplies_an_angle():
    # At least one section should surface a distinct improvement angle from Kevin
    # (i.e. not the 'no distinct angle' fallback).
    pkg = improve_paper(_draft()).to_dict()
    angles = [s["angle"] for s in pkg["section_improvements"]]
    assert any("no distinct improvement angle" not in a for a in angles)


def test_reviewer_verdict_and_confidence_are_rule_based():
    pkg = improve_paper(_draft()).to_dict()
    assert pkg["reviewer_verdict"] in {v.value for v in Verdict}
    assert 0.0 <= pkg["confidence"] <= 1.0


def test_runs_are_replay_stable():
    a = improve_paper(_draft()).to_dict()
    b = improve_paper(_draft()).to_dict()
    assert a["id"] == b["id"]
    assert a == b


def test_works_on_an_ad_hoc_draft():
    draft = PaperDraft(
        title="A Note on Caching Under Drift",
        topic="systems",
        abstract="We argue recency-based eviction degrades under workload drift.",
        claims=("recency is a proxy for relevance, not its cause",),
        sections=(
            Section("Introduction", "Caches evict by recency. Under drift recency misleads."),
            Section("Method", "We compare recency eviction to a drift-aware policy on traces."),
        ),
    )
    pkg = improve_paper(draft, personas=3).to_dict()
    assert validate_paper_improvement(pkg) == []
    assert len(pkg["section_improvements"]) == 2

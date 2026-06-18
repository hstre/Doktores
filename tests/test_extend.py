"""Paper-extension mode: ask the questions the paper does not, and sketch answers.

Offline + deterministic (MockLLM + embedded Kevin's MockLLM). Pins the contract: a valid
package, several questions that span *different* axes (diversity), each worked into a
sketched direction, and replay-stable ids.
"""

from __future__ import annotations

from doktores import PaperDraft, Section, extend_paper, validate_paper_extension
from doktores.examples import rg_paper_draft


def test_extension_is_valid_and_has_questions():
    pkg = extend_paper(rg_paper_draft(), max_questions=4).to_dict()
    assert validate_paper_extension(pkg) == []
    assert 1 <= len(pkg["questions"]) <= 4


def test_each_question_is_worked_into_a_direction():
    pkg = extend_paper(rg_paper_draft()).to_dict()
    for q in pkg["questions"]:
        assert q["question"].strip()
        assert q["approach"].strip()
        assert q["test"].strip()
        assert q["builds_toward"].strip()
        assert 0.0 <= q["novelty"] <= 1.0


def test_questions_span_distinct_axes():
    pkg = extend_paper(rg_paper_draft(), max_questions=4).to_dict()
    axes = [q["axis"] for q in pkg["questions"]]
    assert len(axes) == len(set(axes)), "each question must come from a distinct axis"
    if len(axes) >= 2:
        assert len(set(axes)) >= 2


def test_extension_is_replay_stable():
    a = extend_paper(rg_paper_draft()).to_dict()
    b = extend_paper(rg_paper_draft()).to_dict()
    assert a == b


def test_extends_an_ad_hoc_draft():
    draft = PaperDraft(
        title="A Note on Caching Under Drift", topic="systems",
        abstract="Recency-based eviction degrades under workload drift.",
        claims=("recency is a proxy for relevance, not its cause",),
        sections=(Section("Introduction", "Caches evict by recency; under drift it misleads."),),
    )
    pkg = extend_paper(draft, max_questions=3).to_dict()
    assert validate_paper_extension(pkg) == []

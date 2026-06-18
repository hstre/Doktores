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


def test_extension_surfaces_multiple_questions():
    # The pick loop spreads across primary dimensions then fills, so a multi-section
    # paper should surface more than one question (not collapse to a single one).
    pkg = extend_paper(rg_paper_draft(), max_questions=4).to_dict()
    assert len(pkg["questions"]) >= 2


def test_questions_apply_named_methods_incl_unusual():
    # Kevin's thesis: a blind spot + an UNUSUAL method drives each question.
    from doktores.extend import UNUSUAL_METHODS
    pkg = extend_paper(rg_paper_draft(), max_questions=4).to_dict()
    methods = [q["method"] for q in pkg["questions"]]
    assert all(isinstance(q["method"], str) for q in pkg["questions"])
    assert any(methods), "at least one question must carry a named method"
    assert any(m in UNUSUAL_METHODS for m in methods), methods


def test_every_question_gets_a_triage_verdict():
    pkg = extend_paper(rg_paper_draft(), max_questions=4).to_dict()
    assert set(pkg["triage"]) == {"present", "borderline", "discard"}
    assert sum(pkg["triage"].values()) == len(pkg["questions"])
    for q in pkg["questions"]:
        assert q["verdict"] in ("present", "borderline", "discard")


def test_triage_discards_far_fetched_untestable_questions():
    from doktores import PaperExtender
    from doktores.extend import OpenQuestion
    ext = PaperExtender()  # offline MockLLM
    quatsch = OpenQuestion(
        axis="analogy", method="structural_analogy_transport",
        question="Just as a Roman aqueduct mirrors the soul, is the framework basically vibes?",
        why_open="", approach="", test="", builds_toward="", novelty=0.5,
    )
    assert ext._triage(rg_paper_draft(), quatsch) == "discard"


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

"""The package schema is the contract with Joni - guard it directly."""

from __future__ import annotations

from doktores import ResearchTask, stable_id
from doktores.models import (
    ClaimUpdate,
    EvidenceItem,
    Experiment,
    Publication,
    PublicationKind,
    ResearchOutput,
    Theory,
    Verdict,
    validate_research_output,
)


def test_stable_id_is_replay_stable():
    assert stable_id("RO", "a", "b") == stable_id("RO", "a", "b")
    assert stable_id("RO", "a", "b") != stable_id("RO", "b", "a")
    assert stable_id("RO", "a").startswith("RO_")


def test_task_id_deterministic():
    t1 = ResearchTask(conflict="x vs y", topic="routing", source_hypothesis_ids=("C-1",))
    t2 = ResearchTask(conflict="x vs y", topic="routing", source_hypothesis_ids=("C-1",))
    assert t1.id == t2.id


def _minimal_output(verdict=Verdict.ACCEPT) -> ResearchOutput:
    theory = Theory(statement="Under drift, recency detaches from locality.", predictions=("more",))
    return ResearchOutput(
        source_hypothesis_ids=("C-12",),
        theory=theory,
        evidence_for=[EvidenceItem("a lead", "lit:0", 0.25)],
        evidence_against=[EvidenceItem("a counterexample", "counter:0", 0.35)],
        experiments=[Experiment("a pilot", ("baseline",), ("metric",), "stop at N")],
        results="not yet run",
        limitations=("small sample",),
        reviewer_verdict=verdict,
        confidence=0.5,
        recommended_claim_updates=[ClaimUpdate("add_claim", "the theory", "routing")],
        publication=Publication(PublicationKind.PAPER, "A title", "# A title\n"),
    )


def test_valid_package_passes_schema():
    assert validate_research_output(_minimal_output().to_dict()) == []


def test_schema_rejects_bad_op_and_out_of_range_confidence():
    pkg = _minimal_output().to_dict()
    pkg["recommended_claim_updates"][0]["op"] = "confirm_claim"   # not a permitted op
    assert any("op in" in e for e in validate_research_output(pkg))

    pkg2 = _minimal_output().to_dict()
    pkg2["confidence"] = 1.7
    assert any("confidence" in e for e in validate_research_output(pkg2))


def test_schema_flags_missing_keys():
    errors = validate_research_output({"id": "x"})
    assert any("missing key" in e for e in errors)


def test_to_dict_has_no_confirmation_field():
    # Provenance is SOURCE-only: there is no operation or field through which the producer
    # could mark a belief confirmed.
    pkg = _minimal_output().to_dict()
    blob = str(pkg).lower()
    assert "confirm" not in blob
    for upd in pkg["recommended_claim_updates"]:
        assert upd["op"] in {"add_claim", "open_conflict"}

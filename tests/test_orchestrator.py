"""The controlled circle, end to end - the v1 acceptance tests."""

from __future__ import annotations

from doktores import Doktores, ResearchTask, validate_research_output
from doktores.llm_client import _salient_terms

CONFLICT = (
    "Routing prefers locality (keep related work close) but memory prefers recency "
    "(recently touched items are most relevant); under drift they recommend opposite placements."
)
TASK = ResearchTask(
    conflict=CONFLICT,
    topic="routing",
    source_hypothesis_ids=("C-12", "C-37"),
    candidates=("recency is a proxy for relevance, not its cause",),
)


def test_end_to_end_produces_a_schema_valid_package():
    pkg = Doktores().run(TASK).to_dict()
    assert validate_research_output(pkg) == []
    assert pkg["theory"]
    assert pkg["predictions"]
    assert pkg["experiments"]
    assert pkg["reviewer_verdict"] in {"accept", "revise", "reject"}
    assert 0.0 <= pkg["confidence"] <= 1.0
    assert pkg["source_hypothesis_ids"] == ["C-12", "C-37"]


def test_run_is_replay_stable():
    a = Doktores().run(TASK).to_dict()
    b = Doktores().run(TASK).to_dict()
    assert a == b
    assert a["id"] == b["id"]


def test_outputs_are_sources_never_confirmed():
    pkg = Doktores().run(TASK).to_dict()
    # The only epistemic operations a package may carry are candidate proposals - there is
    # structurally no "confirm" operation the producer could emit.
    for upd in pkg["recommended_claim_updates"]:
        assert upd["op"] in {"add_claim", "open_conflict"}
    # The limitations even spell the boundary out explicitly.
    assert any("not a confirmed belief" in lim.lower() for lim in pkg["limitations"])
    # A non-reject package that was seeded by Layer-9 claims keeps the tension visible.
    if pkg["reviewer_verdict"] != "reject":
        assert any(u["op"] == "add_claim" for u in pkg["recommended_claim_updates"])
        assert any(u["op"] == "open_conflict" for u in pkg["recommended_claim_updates"])


# A degenerate language layer: it always "theorises" a mere renaming of the conflict (no
# mechanism, no predictions). The deterministic Falsifier + Adversarial Reviewer must catch
# this and the circle must terminate in a REJECT - language cannot launder a non-theory.
class _RenamingLLM:
    def theorize(self, conflict: str, candidates: list[str]) -> dict:
        return {
            "statement": conflict,
            "mechanism": "",
            "terms": list(_salient_terms(conflict)),
            "preconditions": [],
            "predictions": [],
            "demarcation": "",
        }

    def phrase(self, kind: str, context: str) -> str:
        return f"{kind}: {context[:40]}"

    def phrase_list(self, kind: str, context: str, n: int) -> list[str]:
        return [f"{kind} {i}" for i in range(n)]


def test_reject_path_skips_the_epistemic_channel():
    out = Doktores(_RenamingLLM()).run(TASK, max_rounds=3)
    pkg = out.to_dict()
    assert validate_research_output(pkg) == []
    assert pkg["reviewer_verdict"] == "reject"
    # Epistemic channel is skipped on reject...
    assert pkg["recommended_claim_updates"] == []
    # ...but the publication is still produced for the audit trail.
    assert pkg["publication"]["title"]
    assert pkg["publication"]["kind"] in {"report", "paper", "protocol", "replication", "summary"}


def test_revise_loop_is_bounded():
    # Even pathological inputs terminate within the round budget and return a valid package.
    out = Doktores().run(ResearchTask(conflict="a", topic="t"), max_rounds=1)
    assert validate_research_output(out.to_dict()) == []

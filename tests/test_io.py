"""The two seams: reading occasions, and dropping packages for Joni (append-only, deduped)."""

from __future__ import annotations

import json

from doktores import Doktores, ResearchTask, io_joni, io_kevin


def test_read_tasks_from_handoff(tmp_path):
    handoff = tmp_path / "handoff.json"
    handoff.write_text(json.dumps([
        {"conflict": "x vs y", "topic": "routing", "source_hypothesis_ids": ["C-1"],
         "candidates": ["a guess"]},
        {"conflict": "", "topic": "skip-me"},          # empty conflict -> skipped
        "not a dict",                                   # malformed entry -> skipped
    ]), encoding="utf-8")

    tasks = io_joni.read_tasks_from_handoff(handoff)
    assert len(tasks) == 1
    assert tasks[0].conflict == "x vs y"
    assert tasks[0].source_hypothesis_ids == ("C-1",)
    assert tasks[0].candidates == ("a guess",)


def test_read_tasks_missing_file_is_empty(tmp_path):
    assert io_joni.read_tasks_from_handoff(tmp_path / "nope.json") == []


def test_write_research_inbox_appends_and_dedupes(tmp_path):
    inbox = io_joni.joni_research_inbox(tmp_path)
    assert inbox == tmp_path / "state" / "research_inbox.json"

    pkg = Doktores().run(ResearchTask(conflict="x vs y under drift", topic="routing")).to_dict()

    first = io_joni.write_research_inbox([pkg], inbox)
    assert first["written"] == 1
    # Re-dropping the same package id writes nothing new (idempotent / replay-safe).
    second = io_joni.write_research_inbox([pkg], inbox)
    assert second["written"] == 0 and second["total"] == 1

    on_disk = json.loads(inbox.read_text(encoding="utf-8"))
    assert isinstance(on_disk, list) and len(on_disk) == 1
    assert on_disk[0]["id"] == pkg["id"]


def test_write_research_inbox_skips_malformed(tmp_path):
    inbox = tmp_path / "inbox.json"
    summary = io_joni.write_research_inbox([{"id": "bad", "theory": "incomplete"}], inbox)
    assert summary["written"] == 0 and summary["skipped"] == 1


def test_kevin_seam_returns_a_tuple():
    # Kevin is an optional dependency: importable -> candidate strings; absent -> empty tuple.
    out = io_kevin.candidates_for("how to reconcile locality and recency", domain="routing")
    assert isinstance(out, tuple)
    assert all(isinstance(c, str) for c in out)

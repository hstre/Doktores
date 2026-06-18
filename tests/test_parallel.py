"""Parallel execution must be a pure optimisation: same results, any concurrency.

The LLM calls inside a Kevin run are parallelised (I/O-bound), but routing/scoring are
unchanged and ``pmap`` preserves input order, so a run is byte-identical whether the
pool runs one worker or many. These tests pin that invariant (offline MockLLM).
"""

from __future__ import annotations

from doktores.kevin import Kevin, Problem
from doktores.kevin._parallel import pmap


def test_pmap_preserves_input_order():
    assert pmap(lambda x: x * x, [1, 2, 3, 4, 5]) == [1, 4, 9, 16, 25]
    assert pmap(lambda x: x, []) == []
    assert pmap(lambda x: x + 1, [10]) == [11]


def _ids(run):
    return [c.id for c in run.candidates]


def test_serial_and_parallel_runs_are_identical(monkeypatch):
    p = Problem(
        statement="reduce the paperwork in employee onboarding",
        domain="hr", anchors=("checklist", "welcome email"), variables=("steps", "time"),
    )
    monkeypatch.setenv("DOKTORES_LLM_CONCURRENCY", "1")
    serial = Kevin().run(p, personas=3)
    monkeypatch.setenv("DOKTORES_LLM_CONCURRENCY", "8")
    parallel = Kevin().run(p, personas=3)

    assert serial.id == parallel.id
    assert _ids(serial) == _ids(parallel)
    assert [e.candidate_id for e in serial.evaluations] == \
           [e.candidate_id for e in parallel.evaluations]
    assert serial.hardened == parallel.hardened

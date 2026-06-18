"""The multi-MODEL persona ensemble: each persona drawn from a different LLM.

Offline: we inject fake clients (no network) and assert the dispatch contract - personas
spread across the underlying models, while non-persona work stays on the primary client.
"""

from __future__ import annotations

from doktores.kevin import MultiModelLLM, Problem
from doktores.kevin.models import SolutionSpace, WildMove


class _FakeClient:
    def __init__(self, tag: str) -> None:
        self.tag = tag
        self.variant_personas: list[str] = []
        self.other_calls = 0

    def write_variant(self, problem, space, move, *, persona: str = "") -> str:
        self.variant_personas.append(persona)
        return f"[{self.tag}] {move.value} :: {persona}"

    def propose_spaces(self, problem) -> list[dict]:
        self.other_calls += 1
        return []

    def phrase_transfer(self, target_text: str, step: str) -> str:
        self.other_calls += 1
        return step

    def execute_step(self, ps, target_text, step, variables) -> str:
        self.other_calls += 1
        return step

    def critique(self, problem, candidate_text: str) -> dict:
        self.other_calls += 1
        return {}

    def read_signals(self, problem, candidate_text: str) -> dict:
        self.other_calls += 1
        return {}


_SPACE = SolutionSpace(label="X", description="d", axis="mechanism")
_PROB = Problem(statement="p")


def test_personas_spread_across_models():
    a, b, c = _FakeClient("A"), _FakeClient("B"), _FakeClient("C")
    m = MultiModelLLM([a, b, c])
    assert m.model_count == 3
    for p in ("persona-0", "persona-1", "persona-2", "persona-3", "persona-4"):
        m.write_variant(_PROB, _SPACE, WildMove.ANALOGY, persona=p)
    used = sum(1 for cl in (a, b, c) if cl.variant_personas)
    assert used >= 2, "personas must reach more than one model"


def test_persona_mapping_is_deterministic():
    a, b = _FakeClient("A"), _FakeClient("B")
    m = MultiModelLLM([a, b])
    first = m.write_variant(_PROB, _SPACE, WildMove.WHAT_IF, persona="alpha")
    second = m.write_variant(_PROB, _SPACE, WildMove.WHAT_IF, persona="alpha")
    assert first == second, "same persona must always hit the same model"


def test_non_persona_work_stays_on_primary():
    a, b = _FakeClient("A"), _FakeClient("B")
    m = MultiModelLLM([a, b])
    m.propose_spaces(_PROB)
    m.read_signals(_PROB, "cand")
    m.critique(_PROB, "cand")
    assert a.other_calls == 3 and b.other_calls == 0


def test_empty_clients_rejected():
    try:
        MultiModelLLM([])
    except ValueError:
        return
    raise AssertionError("MultiModelLLM([]) must raise ValueError")

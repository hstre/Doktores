"""Stage 2 - the wild brother (der wilde Bruder).

A free, aggressive, associative instance. Unusual analogies, absurd combinations,
style breaks, distant domains, risky hypotheses, "what if?". It is **allowed to
spin** - its task is not truth, it is *variation*. Selection comes later; here we
maximise spread.

The wild brother is the one place we deliberately invite nonsense. Two guard-rails
keep it auditable rather than merely random:
  * Its repertoire is the closed ``WildMove`` enum - chaos you can enumerate.
  * Each move gets a fixed ``wildness`` weight, so downstream stages can see how
    far out a variant is and the human can dial risk.

The text of each variant is the LLM's job (language). Which moves fire, in which
spaces, under which personas, and how wild each is rated - that is this engine's
job (logic).

Improvement 8 (multi-persona ensemble): run the wild brother under several
deterministic personas and HARVEST DIVERGENCE - keep the variants that differ most
across personas. The persona label is fed to the LLM so each persona's hash seed
(and thus its output) differs, while the run stays replay-stable.
"""

from __future__ import annotations

from ._parallel import pmap
from .llm_client import LLMClient
from .models import Problem, SolutionSpace, Variant, WildMove

# How far out each move is, by construction. Replay-stable, no PRNG.
WILDNESS: dict[WildMove, float] = {
    WildMove.ANALOGY: 0.4,
    WildMove.STYLE_BREAK: 0.5,
    WildMove.WHAT_IF: 0.6,
    WildMove.DISTANT_DOMAIN: 0.75,
    WildMove.ABSURD_COMBINATION: 0.85,
    WildMove.RISKY_HYPOTHESIS: 0.9,
}

# An affinity-light region gets gentler moves; a rich region can take the wild end.
_DEFAULT_MOVES = (
    WildMove.ANALOGY,
    WildMove.WHAT_IF,
    WildMove.DISTANT_DOMAIN,
    WildMove.RISKY_HYPOTHESIS,
)

# Deterministic persona roster. Index 0 ("") is the plain single-persona voice, so a
# personas=1 run is identical to the un-ensembled wild brother.
PERSONAS: tuple[str, ...] = ("", "skeptic", "visionary", "engineer", "contrarian")


class WildBrother:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    def vary(
        self,
        problem: Problem,
        space: SolutionSpace,
        *,
        moves: tuple[WildMove, ...] = _DEFAULT_MOVES,
        persona: str = "",
    ) -> list[Variant]:
        """Generate one variant per requested move inside one space (one persona)."""
        variants: list[Variant] = []
        for move in moves:
            content = self._llm.write_variant(problem, space, move, persona=persona)
            variants.append(
                Variant(
                    space_id=space.id,
                    move=move,
                    content=content,
                    wildness=WILDNESS[move],
                    persona=persona,
                )
            )
        return variants

    def storm(
        self,
        problem: Problem,
        spaces: list[SolutionSpace],
        *,
        moves: tuple[WildMove, ...] = _DEFAULT_MOVES,
        personas: int = 1,
    ) -> list[Variant]:
        """Run the wild brother across every routed space. Order is deterministic.

        With ``personas == 1`` this is the plain wild brother. With ``personas > 1``
        it runs each (space, move) under several persona voices and HARVESTS
        DIVERGENCE: for each (space, move) slot it keeps the variants whose content
        differs most across personas (dropping personas that merely echo another).
        """
        chosen = PERSONAS[: max(1, min(personas, len(PERSONAS)))]
        # Flat, deterministic task list across (space, move, persona); the LLM calls
        # run concurrently (I/O-bound) but results stay in input order, so the run is
        # replay-stable.
        tasks = [(space, move, p) for space in spaces for move in moves for p in chosen]
        contents = pmap(
            lambda t: self._llm.write_variant(problem, t[0], t[1], persona=t[2]), tasks
        )
        built: dict[tuple[str, WildMove, str], Variant] = {
            (space.id, move, p): Variant(
                space_id=space.id, move=move, content=content,
                wildness=WILDNESS[move], persona=p,
            )
            for (space, move, p), content in zip(tasks, contents, strict=True)
        }
        out: list[Variant] = []
        for space in spaces:
            for move in moves:
                slot = [built[(space.id, move, p)] for p in chosen]
                if len(chosen) == 1:
                    out.append(slot[0])
                else:
                    out.extend(self._harvest_divergence(slot))
        return out

    @staticmethod
    def _harvest_divergence(slot: list[Variant]) -> list[Variant]:
        """Keep persona variants that diverge; drop content-duplicates deterministically.

        Deterministic, replay-stable: variants are visited in persona order and a
        variant is kept only if its content has not already been seen, so the surviving
        set is exactly the *distinct* outputs the personas produced for this slot.
        """
        seen: set[str] = set()
        kept: list[Variant] = []
        for v in slot:
            if v.content not in seen:
                seen.add(v.content)
                kept.append(v)
        return kept

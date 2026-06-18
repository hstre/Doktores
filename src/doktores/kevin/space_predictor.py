"""Predicting *where* the solution spaces are - before the wild brother runs.

Kevin's thesis starts with finding plausible-but-unworked regions. This adds a
deterministic predictor: a fixed *universe of structural axes* (the dimensions any
problem can be attacked along), a coverage analysis of which axes the known
approaches already work, and therefore a prediction of which axes are **blind
spots** - open solution spaces nobody has explored.

The coverage/blind-spot computation is the in-house set arithmetic
(``_builtin_coverage``): set union / intersection / symmetric difference over these
axis sets. The prediction seeds the explorer with spaces on the open axes, so Kevin
actively probes where the room actually is.

Improvement 3 (combinatorial axes): after the single blind-spot axes, the predictor
also emits PAIR seed-spaces for the top-N distant (no shared affinity) blind axes, so
the explorer/wild-brother probe axis *combinations*, not only single axes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import Affinity, Problem, SolutionSpace


@dataclass(frozen=True)
class Axis:
    name: str
    description: str
    keywords: frozenset[str]
    affinities: tuple[Affinity, ...]


# The universe: the structural ways any problem can be attacked. Larger than what the
# LLM usually proposes, so there are genuine blind spots to predict.
STRUCTURAL_AXES: tuple[Axis, ...] = (
    Axis("mechanism", "how the underlying process actually works",
         frozenset({"mechanism", "process", "cause", "how", "works"}),
         (Affinity.CAUSAL, Affinity.DECOMPOSITION)),
    Axis("constraint", "which constraint, if removed, dissolves the problem",
         frozenset({"constraint", "limit", "rule", "budget", "headcount", "cost"}),
         (Affinity.INVERSION, Affinity.INVARIANT)),
    Axis("boundary", "behaviour at the extremes / limit cases",
         frozenset({"boundary", "edge", "extreme", "scale", "peak", "worst"}),
         (Affinity.BOUNDARY, Affinity.RISK)),
    Axis("actor", "whose interests and behaviour shape the situation",
         frozenset({"actor", "people", "stakeholder", "interest", "who", "team", "user", "hire"}),
         (Affinity.PROVENANCE, Affinity.ADVERSARIAL)),
    Axis("analogy", "a distant field with the same structural shape",
         frozenset({"analogy", "like", "metaphor", "similar", "elsewhere"}),
         (Affinity.ANALOGY, Affinity.DECOMPOSITION)),
    Axis("level", "the right level of generality to attack it on",
         frozenset({"level", "abstract", "general", "specific", "detail"}),
         (Affinity.ABSTRACTION, Affinity.DECOMPOSITION)),
    Axis("synthesis", "what emerges when the parts interact, not the parts alone",
         frozenset({"synthesis", "combine", "interaction", "emergent", "whole", "system"}),
         (Affinity.COMPOSITION, Affinity.CAUSAL)),
    Axis("temporal", "how it unfolds over time / sequencing & timing",
         frozenset({"time", "temporal", "sequence", "when", "schedule", "timing", "onboarding"}),
         (Affinity.CAUSAL, Affinity.RISK)),
    Axis("incentive", "what rewards or penalties drive the behaviour",
         frozenset({"incentive", "reward", "penalty", "motivation", "gamify", "nudge"}),
         (Affinity.PROVENANCE, Affinity.RISK)),
    Axis("information", "what is known/unknown and how signal flows",
         frozenset({"information", "data", "signal", "feedback", "knowledge", "email"}),
         (Affinity.PROVENANCE, Affinity.DECOMPOSITION)),
    Axis("material", "the physical medium / tooling substrate",
         frozenset({"material", "medium", "physical", "tool", "substrate", "paperwork", "form"}),
         (Affinity.BOUNDARY, Affinity.INVARIANT)),
    Axis("inversion", "the opposite / failure framing",
         frozenset({"inversion", "opposite", "fail", "avoid", "prevent", "remove"}),
         (Affinity.INVERSION, Affinity.ADVERSARIAL)),
)


def _tokens(text: str) -> set[str]:
    return {w.strip(".,;:!?'\"()").lower() for w in text.split() if len(w) > 2}


def _touches(texts: tuple[str, ...], axis: Axis) -> bool:
    blob = _tokens(" ".join(texts))
    return bool(blob & axis.keywords)


def _plausibility(problem: Problem, axis: Axis) -> float:
    """How sensible is this axis for this problem? Token overlap with the statement."""
    overlap = len(_tokens(problem.statement) & axis.keywords)
    return round(min(0.9, 0.5 + 0.2 * overlap), 4)


@dataclass
class Prediction:
    """Where the solution spaces are, per the coverage analysis."""

    engine: str
    universe_size: int
    covered: tuple[str, ...]
    blindspots: tuple[str, ...]
    new_region_fraction: float        # fraction of the structural space left unexplored
    redundancy: float                 # how much the known approaches overlap (crowding)
    seed_spaces: list[SolutionSpace] = field(default_factory=list)
    pair_spaces: list[SolutionSpace] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "engine": self.engine,
            "universe_size": self.universe_size,
            "covered": list(self.covered),
            "blindspots": list(self.blindspots),
            "new_region_fraction": self.new_region_fraction,
            "redundancy": self.redundancy,
            "pair_spaces": [s.axis for s in self.pair_spaces],
        }


class SpacePredictor:
    """Predicts blind-spot axes (open solution spaces) via coverage analysis."""

    def __init__(self, axes: tuple[Axis, ...] = STRUCTURAL_AXES) -> None:
        self._axes = axes

    def predict(self, problem: Problem, *, pair_top_n: int = 3) -> Prediction:
        universe_ids = set(range(len(self._axes)))
        covered_ids = {
            i for i, axis in enumerate(self._axes)
            if _touches(problem.known_approaches, axis)
        }
        blind_ids = sorted(universe_ids - covered_ids)

        report = _builtin_coverage(covered_ids, universe_ids)

        seeds = [self._seed(problem, self._axes[i]) for i in blind_ids]
        pairs = self._pair_seeds(problem, blind_ids, pair_top_n=pair_top_n)
        return Prediction(
            engine=report["engine"],
            universe_size=len(self._axes),
            covered=tuple(self._axes[i].name for i in sorted(covered_ids)),
            blindspots=tuple(self._axes[i].name for i in blind_ids),
            new_region_fraction=report["new_region_fraction"],
            redundancy=report["redundancy"],
            seed_spaces=seeds,
            pair_spaces=pairs,
        )

    def _seed(self, problem: Problem, axis: Axis) -> SolutionSpace:
        # A predicted-open region: plausible, and (by construction) under-worked, so a
        # low exploration score -> high opportunity -> the wild brother is sent here.
        return SolutionSpace(
            label=f"{axis.name.title()} space",
            description=f"Attack {problem.statement!r} along {axis.description}.",
            axis=axis.name,
            affinities=axis.affinities,
            plausibility=_plausibility(problem, axis),
            exploration=0.2,
        )

    def _pair_seeds(
        self, problem: Problem, blind_ids: list[int], *, pair_top_n: int
    ) -> list[SolutionSpace]:
        """Combinatorial blind spots: pairs of *distant* (no shared affinity) blind axes.

        The single blind axes are already ranked by opportunity via plausibility; here
        we take the top-N blind axes and form pairs that share *no* affinity tag, so the
        pair genuinely spans the structural space. The combined region is rewarded for
        being doubly-unworked (a very low exploration), and its affinities are the merged
        set, so method transfer can draw on both shapes.
        """
        ranked = sorted(
            blind_ids,
            key=lambda i: (-_plausibility(problem, self._axes[i]), self._axes[i].name),
        )[:pair_top_n]
        pairs: list[SolutionSpace] = []
        for a in range(len(ranked)):
            for b in range(a + 1, len(ranked)):
                ax_a, ax_b = self._axes[ranked[a]], self._axes[ranked[b]]
                if set(ax_a.affinities) & set(ax_b.affinities):
                    continue  # not distant - skip
                merged = tuple(dict.fromkeys((*ax_a.affinities, *ax_b.affinities)))
                # Opportunity reward: both unworked -> exploration floor even lower.
                plaus = round(
                    min(0.95, 0.5 * (_plausibility(problem, ax_a) + _plausibility(problem, ax_b))
                        + 0.1),
                    4,
                )
                pairs.append(
                    SolutionSpace(
                        label=f"{ax_a.name.title()}x{ax_b.name.title()} space",
                        description=(
                            f"Attack {problem.statement!r} along BOTH "
                            f"{ax_a.description} AND {ax_b.description}."
                        ),
                        axis=f"{ax_a.name}+{ax_b.name}",
                        affinities=merged,
                        plausibility=plaus,
                        exploration=0.1,
                    )
                )
        return pairs


def _builtin_coverage(covered_ids: set[int], universe_ids: set[int]) -> dict:
    """The set arithmetic for blind-spot coverage, computed in-house."""
    sym_diff = covered_ids ^ universe_ids
    union = covered_ids | universe_ids
    smaller = min(len(covered_ids), len(universe_ids))
    inter = covered_ids & universe_ids
    return {
        "engine": "kevin-builtin",
        "blindspot_count": len(sym_diff),
        "new_region_fraction": round(len(sym_diff) / len(union), 6) if union else 0.0,
        "redundancy": round(len(inter) / smaller, 6) if smaller else 0.0,
        "universe_size": len(universe_ids),
        "covered_size": len(covered_ids),
    }

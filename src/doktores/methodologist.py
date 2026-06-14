"""Role 5 - the Method Reviewer / Statistician.

Audits the experimental plan the way a hostile methods reviewer would: sample size,
confounding, measurement error, significance versus effect size, multiple testing,
robustness, and whether an alternative analysis was even considered. It returns a
``soundness`` score in [0, 1] computed **entirely by rule** from what the design actually
contains - the LLM only phrases the prose concerns. A plan with no baselines, no stop
criterion and a single untested metric scores low no matter how it is written up.
"""

from __future__ import annotations

from .llm_client import LLMClient
from .models import Experiment, MethodReview

# What a defensible minimal pilot must contain. Each present feature earns weight; the score
# is their weighted sum, clamped to [0, 1]. Pure logic - no language here.
_WEIGHTS = {
    "has_baselines": 0.25,       # something to beat -> guards against "looks good in isolation"
    "has_metrics": 0.20,         # a declared primary metric -> guards against metric-fishing
    "has_stop_criteria": 0.25,   # a pre-set stop -> guards against optional-stopping
    "has_robustness": 0.15,      # an alternative analysis path -> guards against one lucky pipeline
    "multiple_designs": 0.15,    # >1 pilot -> guards against a single fragile result
}


class MethodReviewer:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    def review(self, experiments: list[Experiment]) -> MethodReview:
        features = _features(experiments)
        soundness = round(sum(w for k, w in _WEIGHTS.items() if features[k]), 4)

        # Concerns are raised for every guard that is *missing* - that is where a real
        # statistician spends their ink.
        gaps = [k for k in _WEIGHTS if not features[k]]
        n = max(len(gaps), 1)
        concerns = tuple(self._llm.phrase_list("concern", " ".join(gaps) or "general rigor", n))

        limitations = tuple(_LIMITATION[g] for g in gaps if g in _LIMITATION)
        return MethodReview(concerns=concerns, limitations=limitations, soundness=soundness)


def _features(experiments: list[Experiment]) -> dict[str, bool]:
    has_baselines = any(x.baselines for x in experiments)
    has_metrics = any(x.metrics for x in experiments)
    has_stop = any(x.stop_criteria.strip() for x in experiments)
    has_robustness = any(
        "robust" in (m.lower()) or "alternative" in m.lower()
        for x in experiments for m in x.metrics
    )
    return {
        "has_baselines": has_baselines,
        "has_metrics": has_metrics,
        "has_stop_criteria": has_stop,
        "has_robustness": has_robustness,
        "multiple_designs": len(experiments) > 1,
    }


_LIMITATION = {
    "has_baselines": "no baseline to compare against; an isolated result is uninterpretable",
    "has_metrics": "no declared primary metric; significance cannot be assessed honestly",
    "has_stop_criteria": "no pre-set stop criterion; optional stopping inflates false positives",
    "has_robustness": "robustness to an alternative analysis was not established",
    "multiple_designs": "only one pilot; the finding is not yet shown to be reproducible",
}

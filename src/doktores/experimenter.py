"""Role 4 - the Experimental Designer.

Turns each falsifiable prediction into a *minimal* pilot: a design, baselines to beat,
metrics to read, and an explicit stop criterion so the study cannot run forever or move its
own goalposts. Reproducibility is a first-class field, not an afterthought. The LLM phrases
the design sentence; the controls/metrics/stop-criterion scaffold is fixed and deterministic
so the Method Reviewer downstream always has the same structure to audit.
"""

from __future__ import annotations

from .llm_client import LLMClient
from .models import Experiment, Theory

_MAX_EXPERIMENTS = 3


class ExperimentalDesigner:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    def design(self, theory: Theory) -> list[Experiment]:
        predictions = theory.predictions or (theory.statement,)
        experiments: list[Experiment] = []
        for prediction in predictions[:_MAX_EXPERIMENTS]:
            design = self._llm.phrase("experiment_design", prediction)
            experiments.append(
                Experiment(
                    design=design,
                    baselines=(
                        "a no-mechanism null model",
                        "the strongest competing explanation from the literature scout",
                    ),
                    metrics=(
                        "primary: the predicted effect size with a confidence interval",
                        "secondary: robustness under a pre-registered alternative analysis",
                    ),
                    stop_criteria=(
                        "stop at the pre-registered sample size, or earlier if the predicted "
                        "effect's interval excludes the null in both directions"
                    ),
                )
            )
        return experiments

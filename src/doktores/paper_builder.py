"""Role 6 - the Paper Builder.

Only *after* the theory has been falsified-tested, designed-for and method-reviewed does the
team write anything up. The builder assembles a structured draft - Problem, Related Work,
Theory, Method, Results, Limitations, Open Questions - in markdown. The LLM phrases each
section's prose; the section structure and the choice of publication *kind* are deterministic
and reflect the artefact, not a wish: a falsified theory becomes a candid ``report``, an
unrun design becomes a ``protocol``, a sound tested theory becomes a ``paper``.
"""

from __future__ import annotations

from .llm_client import LLMClient
from .models import (
    FalsificationReport,
    LiteratureFindings,
    MethodReview,
    Publication,
    PublicationKind,
    ResearchTask,
    Theory,
)

_PAPER_SOUNDNESS = 0.8


class PaperBuilder:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    def build(
        self,
        task: ResearchTask,
        theory: Theory,
        literature: LiteratureFindings,
        falsification: FalsificationReport,
        experiments: list,
        method_review: MethodReview,
        results: str,
    ) -> Publication:
        kind = _kind(falsification, method_review, experiments, results)
        title = _title(theory)

        def prose(section: str, ctx: str) -> str:
            return self._llm.phrase(f"paper:{section}", ctx)

        parts = [
            f"## Problem\n\n{prose('problem', task.conflict)}\n",
            "## Related Work\n\n"
            + prose("related_work", "; ".join(literature.competing_explanations) or task.topic)
            + "\n\n"
            + _bullets(literature.related_work),
            f"## Theory\n\n{prose('theory', theory.statement)}\n\n"
            f"*Mechanism:* {theory.mechanism or 'unspecified'}\n\n"
            f"*Predictions:*\n\n{_bullets(theory.predictions)}\n\n"
            f"*Demarcation:* {theory.demarcation or 'n/a'}\n",
            "## Method\n\n"
            + prose("method", experiments[0].design if experiments else theory.statement)
            + "\n\n"
            + _bullets([x.design for x in experiments]),
            f"## Results\n\n{prose('results', results)}\n\n> {results}\n",
            "## Limitations\n\n"
            + prose("limitations", "; ".join(method_review.limitations) or "the usual caveats")
            + "\n\n"
            + _bullets(
                (*method_review.limitations, falsification.weakest_assumption)
                if falsification.weakest_assumption
                else method_review.limitations
            ),
            "## Open Questions\n\n"
            + prose(
                "open_questions",
                "; ".join(falsification.refutation_conditions) or theory.statement,
            )
            + "\n",
        ]
        markdown = f"# {title}\n\n" + "\n".join(parts)
        return Publication(kind=kind, title=title, markdown=markdown)


def _kind(
    falsification: FalsificationReport, method_review: MethodReview, experiments: list, results: str
) -> PublicationKind:
    if falsification.fatal:
        return PublicationKind.REPORT
    if results.strip().lower().startswith("not yet run") and experiments:
        return PublicationKind.PROTOCOL
    if method_review.soundness >= _PAPER_SOUNDNESS and experiments:
        return PublicationKind.PAPER
    return PublicationKind.REPORT


def _title(theory: Theory) -> str:
    head = theory.statement.strip().rstrip(".")
    if len(head) > 80:
        head = head[:77].rsplit(" ", 1)[0] + "…"
    return head or "Untitled research output"


def _bullets(items) -> str:
    items = [str(i).strip() for i in items if str(i).strip()]
    return "\n".join(f"- {i}" for i in items) if items else "_(none)_"

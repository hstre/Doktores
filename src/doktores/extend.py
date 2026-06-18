"""Paper-extension mode: ask the questions the paper does *not*, and sketch answers.

A different goal from the improver. Instead of hunting faults and rewriting prose (which
fights the claim-faithfulness guard), this points the embedded Kevin's blind-spot router
at the paper to surface the **unasked** questions - the structural dimensions the paper
leaves unworked - and then, per question, sketches an approach to answer it and a way to
test that answer. It builds ON the paper rather than correcting it.

This plays to Kevin's actual strength (routing to under-worked regions) and has no
faithfulness conflict: every question/approach is a labelled *proposal*, never a claim
that the paper is wrong. Kevin finds the directions; scoring stays in rules; the LLM only
phrases. Diversity is enforced by axis, so the questions span different dimensions rather
than collapsing onto one.
"""

from __future__ import annotations

from dataclasses import dataclass

from .kevin import Kevin, Problem
from .kevin._parallel import pmap
from .llm_client import LLMClient, get_default_client
from .models import stable_id
from .paper import PaperDraft, _terms


@dataclass
class OpenQuestion:
    """One question the paper does not ask, worked into a sketched research direction."""

    axis: str                 # the blind-spot dimension it comes from
    question: str
    why_open: str             # why the paper leaves it open
    approach: str             # a sketch of how to answer it
    test: str                 # how to validate / falsify that answer
    builds_toward: str        # what answering it would unlock
    novelty: float            # Kevin's calibrated opportunity score for the seed

    def to_dict(self) -> dict:
        return {
            "axis": self.axis,
            "question": self.question,
            "why_open": self.why_open,
            "approach": self.approach,
            "test": self.test,
            "builds_toward": self.builds_toward,
            "novelty": round(self.novelty, 4),
        }


@dataclass
class PaperExtension:
    """The package the extender hands back: a small research agenda built on the paper."""

    paper_id: str
    title: str
    topic: str
    questions: list[OpenQuestion]
    summary: str

    @property
    def id(self) -> str:
        return stable_id("PX", self.paper_id, *(q.question for q in self.questions))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "paper_id": self.paper_id,
            "title": self.title,
            "topic": self.topic,
            "questions": [q.to_dict() for q in self.questions],
            "summary": self.summary,
        }


PAPER_EXTENSION_KEYS = ("id", "paper_id", "title", "topic", "questions", "summary")
_Q_KEYS = ("axis", "question", "why_open", "approach", "test", "builds_toward", "novelty")


def validate_paper_extension(pkg: dict) -> list[str]:
    """Return a list of human-readable problems with a package dict (empty == valid)."""
    problems: list[str] = []
    for key in PAPER_EXTENSION_KEYS:
        if key not in pkg:
            problems.append(f"missing top-level key: {key}")
    qs = pkg.get("questions")
    if not isinstance(qs, list) or not qs:
        problems.append("questions must be a non-empty list")
    else:
        for i, q in enumerate(qs):
            for key in _Q_KEYS:
                if key not in q:
                    problems.append(f"question[{i}] missing key: {key}")
            nov = q.get("novelty")
            if not isinstance(nov, int | float) or not (0.0 <= float(nov) <= 1.0):
                problems.append(f"question[{i}] novelty must be in [0,1]: {nov}")
    return problems


class PaperExtender:
    """Find the questions a paper does not ask, and sketch how to answer each.

    Deterministic given the same LLM. The embedded Kevin routes to the paper's blind-spot
    axes (declaring the paper's own claims/headings as 'known' so they score as crowded);
    we keep one direction per *distinct* axis so the agenda spans dimensions.
    """

    def __init__(
        self,
        llm: LLMClient | None = None,
        *,
        kevin: Kevin | None = None,
        max_questions: int = 4,
        personas: int = 2,
    ) -> None:
        self._llm = llm or get_default_client()
        self._kevin = kevin or Kevin()
        self._max = max(1, max_questions)
        self._personas = personas

    def extend(self, draft: PaperDraft) -> PaperExtension:
        body = draft.abstract + " " + " ".join(s.text for s in draft.sections)
        terms = _terms(body)[:8]
        problem = Problem(
            statement=f"what important question does the paper '{draft.title}' leave unanswered?",
            domain=draft.topic,
            constraints=("the question must build ON the paper, not contradict its claims",),
            known_approaches=tuple(draft.claims) + tuple(s.heading for s in draft.sections),
            evidence=(draft.abstract,) if draft.abstract else (),
            anchors=terms,
            variables=terms,
        )
        # Explore enough spaces to span several axes; no hardening (we want breadth).
        run = self._kevin.run(
            problem, top_spaces=self._max, methods_per_target=1,
            personas=self._personas, harden=False,
        )
        axis_of = {s.id: s.axis for s in run.spaces}
        cand_by_id = {c.id: c for c in run.candidates}
        promising = run.promising()

        def components(axis: str) -> list[str]:
            return [c for c in axis.split("+") if c]

        # One direction per distinct axis *component* (not just exact string) so the
        # agenda spans genuinely different dimensions; and 'analogy' is deprioritised - it
        # over-appears in the routing and tends to produce metaphor questions, so it only
        # fills a slot if nothing else is left.
        picks: list[tuple[str, float]] = []   # (axis, score)
        used: set[str] = set()
        for allow_analogy in (False, True):
            for ev in promising:
                if len(picks) >= self._max:
                    break
                cand = cand_by_id.get(ev.candidate_id)
                if cand is None:
                    continue
                axis = axis_of.get(cand.space_id, "open")
                comps = components(axis)
                if not allow_analogy and "analogy" in comps:
                    continue
                if any(c in used for c in comps):     # component-level de-dup
                    continue
                used.update(comps)
                picks.append((axis, ev.score))
            if len(picks) >= self._max:
                break

        questions = pmap(lambda p: self._work(draft, p[0], p[1]), picks)
        summary = self._llm.phrase(
            "extension_summary",
            f"{draft.title} ({draft.topic}); {len(questions)} unasked questions across "
            f"{', '.join(q.axis for q in questions)}",
        )
        return PaperExtension(
            paper_id=draft.id, title=draft.title, topic=draft.topic,
            questions=questions, summary=summary,
        )

    def _work(self, draft: PaperDraft, axis: str, score: float) -> OpenQuestion:
        ctx = (
            f"PAPER: {draft.title}\nFIELD: {draft.topic}\nABSTRACT: {draft.abstract}\n"
            f"DIMENSION the paper does not work: {axis}"
        )
        question = self._llm.phrase(
            "open_question",
            ctx + "\nPose ONE precise, substantive research question along that dimension "
            "that the paper does not address. Be concrete and testable; no metaphors or "
            "analogies, no anthropomorphic framing.",
        )
        qctx = f"PAPER: {draft.title}\nFIELD: {draft.topic}\nQUESTION: {question}"
        return OpenQuestion(
            axis=axis,
            question=question,
            why_open=self._llm.phrase("why_unasked", ctx + f"\nQUESTION: {question}"),
            approach=self._llm.phrase(
                "answer_approach",
                qctx + "\nSketch a concrete method to answer it (data/procedure), 1-2 sentences.",
            ),
            test=self._llm.phrase(
                "answer_test",
                qctx + "\nGive a concrete validation: the specific experiment or measurement, "
                "the metric, and the observed result that would FALSIFY the proposed answer. "
                "1-2 sentences. Do NOT merely restate that the paper omits this.",
            ),
            builds_toward=self._llm.phrase("builds_toward", qctx),
            novelty=round(score, 4),
        )


def extend_paper(
    draft: PaperDraft,
    *,
    llm: LLMClient | None = None,
    max_questions: int = 4,
    personas: int = 2,
) -> PaperExtension:
    """Convenience: surface a paper's unasked questions and sketch answers."""
    return PaperExtender(llm, max_questions=max_questions, personas=personas).extend(draft)

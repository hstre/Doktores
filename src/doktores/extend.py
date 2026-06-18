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
    """One question the paper does not ask: an unusual METHOD applied to a blind spot."""

    axis: str                 # the blind-spot dimension Kevin routed to
    method: str               # the unusual content-free method applied to that blind spot
    question: str
    why_open: str             # why the paper leaves it open
    approach: str             # a sketch of how to answer it
    test: str                 # how to validate / falsify that answer
    builds_toward: str        # what answering it would unlock
    novelty: float            # Kevin's calibrated opportunity score for the seed

    def to_dict(self) -> dict:
        return {
            "axis": self.axis,
            "method": self.method,
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
_Q_KEYS = ("axis", "method", "question", "why_open", "approach", "test", "builds_toward",
           "novelty")

# The bold, content-free Denkbewegungen worth applying to a blind spot - the ones that
# reframe rather than merely re-check. We prefer these over the diligent-reviewer methods
# (five_whys, base_rate_first, ...) so the questions lean unusual, not safe.
UNUSUAL_METHODS = frozenset({
    "invert_then_flip", "limit_case_analysis", "constraint_relaxation",
    "structural_analogy_transport", "conservation_tracking", "dimensional_consistency",
    "first_principles_reduction", "emergence_search", "abstraction_ladder", "premortem",
})


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
        transfer_by_id = {t.id: t for t in run.transfers}
        promising = run.promising()

        def primary(axis: str) -> str:
            comps = [c for c in axis.split("+") if c]
            return comps[0] if comps else "open"

        def method_of(cand) -> str:
            return getattr(cand, "method_name", "") or ""

        def steps_of(cand) -> tuple[str, ...]:
            t = transfer_by_id.get(getattr(cand, "transfer_id", None))
            return tuple(t.mapped_steps) if t else ()

        # Kevin's two-stage thesis: find the blind spot, then apply an UNUSUAL method to it.
        # So we prefer method-disciplined candidates whose method is one of the bold ones,
        # and spread across both the blind-spot dimension AND the method (no repeats), so
        # each question is a different (blind spot x unusual method) pairing. Later stages
        # relax: any disciplined candidate, then anything, to fill up to max_questions.
        picks: list = []                 # (cand, axis, method, steps, score)
        picked_ids: set[str] = set()
        used_prim: set[str] = set()
        used_method: set[str] = set()
        stages = ("unusual-distinct", "unusual", "disciplined", "fill")
        for stage in stages:
            for ev in promising:
                if len(picks) >= self._max:
                    break
                if ev.candidate_id in picked_ids:
                    continue
                cand = cand_by_id.get(ev.candidate_id)
                if cand is None:
                    continue
                method = method_of(cand)
                axis = axis_of.get(cand.space_id, "open")
                prim = primary(axis)
                disciplined = bool(getattr(cand, "transfer_id", None))
                unusual = method in UNUSUAL_METHODS
                if stage == "unusual-distinct" and not (
                    unusual and prim not in used_prim and method not in used_method
                ):
                    continue
                if stage == "unusual" and not (unusual and method not in used_method):
                    continue
                if stage == "disciplined" and not disciplined:
                    continue
                picked_ids.add(ev.candidate_id)
                used_prim.add(prim)
                if method:
                    used_method.add(method)
                picks.append((cand, axis, method, steps_of(cand), ev.score))
            if len(picks) >= self._max:
                break

        questions = pmap(lambda p: self._work(draft, *p), picks)
        summary = self._llm.phrase(
            "extension_summary",
            f"{draft.title} ({draft.topic}); {len(questions)} unasked questions across "
            f"{', '.join(q.axis for q in questions)}",
        )
        return PaperExtension(
            paper_id=draft.id, title=draft.title, topic=draft.topic,
            questions=questions, summary=summary,
        )

    def _work(
        self, draft: PaperDraft, cand, axis: str, method: str,
        steps: tuple[str, ...], score: float,
    ) -> OpenQuestion:
        # Kevin's move, made real: take the blind spot (axis) and APPLY the unusual method
        # to it, grounded in the paper's actual content. The method's executed steps are the
        # creative engine; the LLM only phrases the question that results.
        content = " ".join(f"[{s.heading}] {s.text}" for s in draft.sections)[:2600]
        method_label = method.replace("_", " ") if method else "an unusual reframing method"
        executed = " ; ".join(steps[:3])
        ctx = (
            f"PAPER: {draft.title}\nFIELD: {draft.topic}\nABSTRACT: {draft.abstract}\n"
            f"CONTENT: {content}"
        )
        question = self._llm.phrase(
            "open_question",
            ctx
            + f"\nBLIND SPOT (a dimension the paper does not work): {axis}"
            + f"\nUNUSUAL METHOD to apply to that blind spot: {method_label}"
            + (f"\nMETHOD STEPS executed against the paper: {executed}" if executed else "")
            + "\nApply this method to that blind spot of THIS paper and phrase the ONE bold, "
            "non-obvious research question it produces - one the paper does not ask. Lean into "
            "the reframing the method suggests (invert the premise, push to the limit, drop the "
            "binding constraint, transport the structure from another field) rather than a "
            "routine robustness/generalisation check. Reference the paper's own constructs. An "
            "illuminating cross-domain analogy is welcome if it sharpens the question; no "
            "decorative metaphor, no anthropomorphic framing. Make it concrete and testable.",
        )
        qctx = f"PAPER: {draft.title}\nFIELD: {draft.topic}\nQUESTION: {question}"
        return OpenQuestion(
            axis=axis,
            method=method,
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

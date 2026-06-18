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

Acceptance criterion (what this mode is FOR): the yield of *author-surprising-but-true*
findings - questions that hit a real gap the author, or a strong model reading the paper
cold, would not readily name. NOT the count of ``present`` questions. The scaffold only
earns its keep where a *forced* Denkbewegung (e.g. premortem: "assume this already failed -
why?") surfaces something the naked model would not. The methods that pay off force a move
you would not otherwise make (premortem, dimensional_consistency, invert_then_flip); the
decorative ones (structural_analogy_transport, conservation_tracking, abstraction_ladder)
are correctly the ones the triage mostly discards.
"""

from __future__ import annotations

from dataclasses import dataclass

from .kevin import Kevin, Problem
from .kevin._parallel import pmap
from .kevin.space_predictor import SpacePredictor
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
    verdict: str = "borderline"   # the Doktores triage: present | borderline | discard

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
            "verdict": self.verdict,
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
        counts = {"present": 0, "borderline": 0, "discard": 0}
        for q in self.questions:
            counts[q.verdict] = counts.get(q.verdict, 0) + 1
        return {
            "id": self.id,
            "paper_id": self.paper_id,
            "title": self.title,
            "topic": self.topic,
            "questions": [q.to_dict() for q in self.questions],
            "triage": counts,  # how the Doktores split nonsense from what to examine
            "summary": self.summary,
        }


PAPER_EXTENSION_KEYS = ("id", "paper_id", "title", "topic", "questions", "triage", "summary")
_Q_KEYS = ("axis", "method", "question", "why_open", "approach", "test", "builds_toward",
           "novelty", "verdict")
_VERDICTS = ("present", "borderline", "discard")

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
            if q.get("verdict") not in _VERDICTS:
                problems.append(f"question[{i}] verdict not in {_VERDICTS}: {q.get('verdict')}")
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
        # Stage 1 (Kevin): find the blind spots - the structural dimensions the paper does
        # not work. Deterministic; deprioritise 'analogy' so it cannot crowd out real ones.
        prediction = SpacePredictor().predict(problem)
        blind = [a for a in prediction.blindspots if a != "analogy"] or list(prediction.blindspots)
        if not blind:
            blind = ["mechanism"]
        opp = {sp.axis: sp.opportunity for sp in prediction.seed_spaces}

        # Stage 2 (Kevin): apply a DIVERSE set of unusual methods from the library - one
        # distinct Denkbewegung per question, instead of the single move that affinity
        # matching collapses to under a real LLM. THIS is "try more methods".
        bold = [m for m in self._kevin.library.all() if m.name in UNUSUAL_METHODS]
        if not bold:
            bold = self._kevin.library.all()

        pairs = [(blind[i % len(blind)], bold[i % len(bold)]) for i in range(self._max)]
        questions = pmap(lambda p: self._work(draft, p[0], p[1], opp.get(p[0], 0.6)), pairs)

        # The Doktores triage (the critical stage): separate total nonsense from what is
        # worth putting before examiners. Kevin generates wild; the Doctoren judge. The LLM
        # only reads each question into signals - the verdict is a rule.
        verdicts = pmap(lambda q: self._triage(draft, q), questions)
        for q, v in zip(questions, verdicts, strict=True):
            q.verdict = v

        summary = self._llm.phrase(
            "extension_summary",
            f"{draft.title} ({draft.topic}); {len(questions)} unasked questions across "
            f"{', '.join(q.axis for q in questions)}",
        )
        return PaperExtension(
            paper_id=draft.id, title=draft.title, topic=draft.topic,
            questions=questions, summary=summary,
        )

    def _triage(self, draft: PaperDraft, q: OpenQuestion) -> str:
        """Rule mapping over an LLM holistic read: present | borderline | discard.

        The hard call - is a bold analogy *illuminating* or a decorative *gimmick*? - is
        exactly what a strong LLM judges better than a keyword rule, so we let it set the
        ``gimmick`` flag holistically; the rule only maps. Discard the incoherent, the
        gimmicky, or the ungrounded; present what is grounded, testable and non-trivial.
        """
        s = self._llm.triage_question(q.question, f"{draft.title}. {draft.abstract}")
        if not s.get("coherent") or s.get("gimmick") or not s.get("grounded"):
            return "discard"
        if s.get("testable") and s.get("nontrivial"):
            return "present"
        return "borderline"

    def _work(self, draft: PaperDraft, axis: str, method, novelty: float) -> OpenQuestion:
        # Kevin's thesis, made literal: take the blind spot and CARRY OUT an unusual method
        # on it, grounded in the paper's own content. The method's steps are the engine; the
        # LLM only phrases the question the move yields.
        content = " ".join(f"[{s.heading}] {s.text}" for s in draft.sections)[:2600]
        steps = " ; ".join(method.steps)
        ctx = (
            f"PAPER: {draft.title}\nFIELD: {draft.topic}\nABSTRACT: {draft.abstract}\n"
            f"CONTENT: {content}"
        )
        question = self._llm.phrase(
            "open_question",
            ctx
            + f"\nBLIND SPOT (a dimension the paper does not work): {axis}"
            + f"\nUNUSUAL METHOD to apply: {method.name.replace('_', ' ')} - {method.summary}"
            + f"\nMETHOD STEPS: {steps}"
            + "\nCarry out this thinking move literally on that blind spot of THIS paper and "
            "phrase the ONE bold, non-obvious research question it yields - one the paper does "
            "not ask. (If the move says invert, invert the paper's premise; if push to the "
            "limit, take a named variable to its extreme; if transport a structure, name the "
            "source system and the mapping.) Reference the paper's own constructs. A cross-domain "
            "analogy is allowed only if it is structural and sharpens the question - no "
            "decorative metaphor, no anthropomorphic framing. Make it concrete and testable.",
        )
        qctx = f"PAPER: {draft.title}\nFIELD: {draft.topic}\nQUESTION: {question}"
        return OpenQuestion(
            axis=axis,
            method=method.name,
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
            novelty=round(min(1.0, max(0.0, novelty)), 4),
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

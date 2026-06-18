"""Paper-improver mode - the controlled circle pointed at a manuscript.

Doktores' research mode turns a Layer-9 conflict into a ``research_output`` package. This
*parallel* mode keeps the same architecture - a deterministic controlled circle, an
LLM that only phrases, an embedded Kevin as the idea source - but points it at a paper:

    Reader  ->  Kevin (improvement angles)  ->  Critic  ->  Reviser  ->  Reviewer

and produces a ``PaperImprovement`` package: per section, the weaknesses found, one
concrete improvement angle (routed by the embedded Kevin into the paper's blind spots), a
suggestion, and a *rewritten passage* the author can take or leave.

The boundary that defines Doktores still holds: **it advises, it never decides.** The
package is a SOURCE of suggestions; which edits land is the author's call. Every score and
verdict is computed by rules here; the LLM only words prose.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .kevin import Kevin, Problem
from .llm_client import LLMClient, get_default_client
from .models import Verdict, stable_id

# Reviewer thresholds (mirror Kevin's gate discipline): how strongly the circle
# recommends acting on a section.
_APPLY_AT = 0.62      # ACCEPT: a strong, well-anchored improvement - apply the rewrite
_CONSIDER_AT = 0.40   # REVISE: a moderate suggestion - consider it
# below -> REJECT: the section is already sound or the angle is hollow; leave it.


def _terms(text: str) -> tuple[str, ...]:
    """Deterministic, content-free keyword pull - anchors for ideation only."""
    seen: list[str] = []
    for raw in text.lower().replace("/", " ").replace("-", " ").split():
        w = "".join(ch for ch in raw if ch.isalnum())
        if len(w) > 4 and w not in _STOP and w not in seen:
            seen.append(w)
    return tuple(seen)


def _first_clause(text: str) -> str:
    t = " ".join(text.split())
    for sep in (". ", "; ", " - "):
        if sep in t:
            return t.split(sep, 1)[0].strip()
    return t[:200].strip()


_STOP = {
    "which", "their", "there", "these", "those", "would", "could", "should", "about",
    "where", "while", "being", "under", "after", "before", "between", "because", "paper",
    "section", "value", "values", "study", "studies", "using", "based",
}


# --------------------------------------------------------------------------- #
# Inputs: the manuscript
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Section:
    """One section of a paper: a heading and its prose."""

    heading: str
    text: str

    @property
    def id(self) -> str:
        return stable_id("sec", self.heading)


@dataclass(frozen=True)
class PaperDraft:
    """A manuscript to improve. ``claims`` are the load-bearing claims the rewrite must
    not contradict (the epistemic guard-rail: improve the writing, not the facts)."""

    title: str
    topic: str
    sections: tuple[Section, ...]
    abstract: str = ""
    claims: tuple[str, ...] = ()

    @property
    def id(self) -> str:
        return stable_id("paper", self.title, *(s.heading for s in self.sections))


# --------------------------------------------------------------------------- #
# Outputs: the improvement package
# --------------------------------------------------------------------------- #


@dataclass
class SectionImprovement:
    """One section, worked through the circle."""

    heading: str
    angle: str                       # the improvement direction (from the embedded Kevin)
    weaknesses: tuple[str, ...]      # what the Critic found wrong with the section
    suggestion: str                  # the concrete improvement
    rewrite: str                     # a rewritten passage - take it or leave it
    verdict: Verdict                 # apply (accept) / consider (revise) / leave (reject)
    confidence: float

    def to_dict(self) -> dict:
        return {
            "heading": self.heading,
            "angle": self.angle,
            "weaknesses": list(self.weaknesses),
            "suggestion": self.suggestion,
            "rewrite": self.rewrite,
            "verdict": self.verdict.value,
            "confidence": round(self.confidence, 4),
        }


@dataclass
class PaperImprovement:
    """The package the paper-improver hands back. A SOURCE of suggested edits, not a
    decision: which edits land is the author's call."""

    paper_id: str
    title: str
    topic: str
    section_improvements: list[SectionImprovement]
    global_weaknesses: tuple[str, ...]
    summary: str
    reviewer_verdict: Verdict
    confidence: float

    @property
    def id(self) -> str:
        return stable_id("PI", self.paper_id, *(s.heading for s in self.section_improvements))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "paper_id": self.paper_id,
            "title": self.title,
            "topic": self.topic,
            "section_improvements": [s.to_dict() for s in self.section_improvements],
            "global_weaknesses": list(self.global_weaknesses),
            "summary": self.summary,
            "reviewer_verdict": self.reviewer_verdict.value,
            "confidence": round(self.confidence, 4),
        }


PAPER_IMPROVEMENT_KEYS = (
    "id", "paper_id", "title", "topic", "section_improvements",
    "global_weaknesses", "summary", "reviewer_verdict", "confidence",
)
_SECTION_KEYS = ("heading", "angle", "weaknesses", "suggestion", "rewrite", "verdict", "confidence")
_VALID_VERDICTS = {v.value for v in Verdict}


def validate_paper_improvement(pkg: dict) -> list[str]:
    """Return a list of human-readable problems with a package dict (empty == valid)."""
    problems: list[str] = []
    for key in PAPER_IMPROVEMENT_KEYS:
        if key not in pkg:
            problems.append(f"missing top-level key: {key}")
    if pkg.get("reviewer_verdict") not in _VALID_VERDICTS:
        problems.append(f"reviewer_verdict not in {_VALID_VERDICTS}: {pkg.get('reviewer_verdict')}")
    conf = pkg.get("confidence")
    if not isinstance(conf, int | float) or not (0.0 <= float(conf) <= 1.0):
        problems.append(f"confidence must be in [0,1]: {conf}")
    secs = pkg.get("section_improvements")
    if not isinstance(secs, list) or not secs:
        problems.append("section_improvements must be a non-empty list")
    else:
        for i, s in enumerate(secs):
            for key in _SECTION_KEYS:
                if key not in s:
                    problems.append(f"section[{i}] missing key: {key}")
            if s.get("verdict") not in _VALID_VERDICTS:
                problems.append(f"section[{i}] verdict invalid: {s.get('verdict')}")
    return problems


# --------------------------------------------------------------------------- #
# The circle
# --------------------------------------------------------------------------- #


@dataclass
class _SectionWork:
    """Internal scratch carried between the roles for one section."""

    section: Section
    terms: tuple[str, ...] = ()
    angle: str = ""
    angle_score: float = 0.0
    weaknesses: tuple[str, ...] = field(default_factory=tuple)


class PaperImprover:
    """The controlled circle for manuscripts. Deterministic given the same LLM.

    The embedded, improved Kevin supplies the *ideation*: for each section it routes into
    the paper's structural blind spots (the axes the section does not yet work) and returns
    a ranked, justified set of improvement angles. The roles here turn the top angle into a
    concrete, defensible suggested edit; all scoring/verdicts are rules.
    """

    def __init__(
        self,
        llm: LLMClient | None = None,
        *,
        kevin: Kevin | None = None,
        personas: int = 2,
    ) -> None:
        self._llm = llm or get_default_client()
        # The embedded Kevin shares no LLM with us by design: its MockLLM is the offline
        # default, so the whole improver runs deterministically with no network.
        self._kevin = kevin or Kevin()
        self._personas = max(1, personas)

    # -- public ------------------------------------------------------------- #
    def improve(self, draft: PaperDraft) -> PaperImprovement:
        works = [self._read(s) for s in draft.sections]
        for w in works:
            self._ideate(draft, w)
            self._critique(w)

        improvements = [self._revise_and_review(draft, w) for w in works]

        # Global review: aggregate. The paper's verdict is the rule-based roll-up of its
        # sections (worst-weighted toward action), never an LLM call.
        global_weaknesses = tuple(
            self._llm.phrase_list("paper_global_weakness", f"{draft.title}. {draft.abstract}", 3)
        )
        summary = self._llm.phrase(
            "paper_summary",
            f"{draft.title} ({draft.topic}); "
            f"{sum(1 for i in improvements if i.verdict is Verdict.ACCEPT)} strong, "
            f"{sum(1 for i in improvements if i.verdict is Verdict.REVISE)} moderate suggestions",
        )
        conf = round(
            sum(i.confidence for i in improvements) / len(improvements), 4
        ) if improvements else 0.0
        verdict = self._roll_up(improvements)

        return PaperImprovement(
            paper_id=draft.id,
            title=draft.title,
            topic=draft.topic,
            section_improvements=improvements,
            global_weaknesses=global_weaknesses,
            summary=summary,
            reviewer_verdict=verdict,
            confidence=conf,
        )

    # -- roles -------------------------------------------------------------- #
    def _read(self, section: Section) -> _SectionWork:
        """Reader: pull the section's salient terms (the anchors ideation must respect)."""
        return _SectionWork(section=section, terms=_terms(section.text)[:6])

    def _ideate(self, draft: PaperDraft, w: _SectionWork) -> None:
        """Embedded Kevin: route into the section's blind spots, return the best angle.

        The section's own gist is declared as a *known approach* so Kevin scores it as
        crowded and routes the wild brother elsewhere - exactly the blind-spot move. We do
        not echo Kevin's raw wild-variant prose (that is deliberately disreputable); we
        keep the *grounded* part: which structural axis it routed to, which content-free
        method it transferred, and the one executed step bound to a concrete variable.
        """
        problem = Problem(
            statement=f"strengthen the argument of the '{w.section.heading}' section",
            domain=draft.topic,
            constraints=(
                "stay faithful to the paper's load-bearing claims",
                "keep it a transparent, reproducible argument",
            ),
            known_approaches=(_first_clause(w.section.text),) + draft.claims,
            evidence=(draft.abstract,) if draft.abstract else (),
            anchors=w.terms,
            variables=w.terms,
        )
        run = self._kevin.run(problem, personas=self._personas, harden=True)
        promising = run.promising()
        if not promising:
            w.angle, w.angle_score = "", 0.0
            return
        # Prefer a method-disciplined candidate (it carries an executed step); fall back
        # to the top promising one.
        cand_by_id = {c.id: c for c in run.candidates}
        best = next(
            (e for e in promising if getattr(cand_by_id.get(e.candidate_id), "transfer_id", None)),
            promising[0],
        )
        cand = cand_by_id.get(best.candidate_id)
        w.angle = self._grounded_angle(run, cand)
        w.angle_score = best.score

    @staticmethod
    def _grounded_angle(run, cand) -> str:
        """Express the routed angle from its structure, not the wild prose."""
        if cand is None:
            return ""
        space = next((s for s in run.spaces if s.id == cand.space_id), None)
        axis = space.axis if space else "an under-worked angle"
        method = getattr(cand, "method_name", "") or "first-principles"
        step = ""
        transfer = next(
            (t for t in run.transfers if t.id == getattr(cand, "transfer_id", None)), None
        )
        if transfer and transfer.mapped_steps:
            step = transfer.mapped_steps[0]
            # Strip the engine's "Executed against 'x':" prefix into plain guidance.
            if ":" in step:
                step = step.split(":", 1)[1].strip()
        return (
            f"Work the '{axis}' axis via {method.replace('_', ' ')}"
            + (f": {step}" if step else "")
        )

    def _critique(self, w: _SectionWork) -> None:
        """Critic (Falsifier-style): attack the section as it stands. Fed the prose only,
        so the weaknesses anchor on content terms, not the heading."""
        w.weaknesses = tuple(self._llm.phrase_list("paper_weakness", w.section.text, 2))

    def _revise_and_review(self, draft: PaperDraft, w: _SectionWork) -> SectionImprovement:
        """Reviser writes the suggestion + rewrite; Reviewer scores it by rules."""
        suggestion = self._llm.phrase(
            "paper_suggestion",
            f"{w.section.heading} || angle: {w.angle or 'tighten and ground the argument'}",
        )
        rewrite = self._llm.phrase(
            "paper_rewrite",
            f"{w.section.heading}: {w.section.text} || angle: {w.angle}",
        )

        # Reviewer (rules only): how strongly should the author act on this section?
        # Anchored on the embedded Kevin's own calibrated top score (so it varies with
        # the ideation quality), adjusted by how grounded and how critiqued the section is.
        anchor_strength = min(1.0, len(w.terms) / 6.0)
        weak_strength = min(1.0, len(w.weaknesses) / 2.0)
        score = round(
            0.55 * min(1.0, w.angle_score)
            + 0.30 * anchor_strength
            + 0.15 * weak_strength,
            4,
        )
        if score >= _APPLY_AT:
            verdict = Verdict.ACCEPT
        elif score >= _CONSIDER_AT:
            verdict = Verdict.REVISE
        else:
            verdict = Verdict.REJECT

        return SectionImprovement(
            heading=w.section.heading,
            angle=w.angle or "(no distinct improvement angle surfaced)",
            weaknesses=w.weaknesses,
            suggestion=suggestion,
            rewrite=rewrite,
            verdict=verdict,
            confidence=score,
        )

    @staticmethod
    def _roll_up(improvements: list[SectionImprovement]) -> Verdict:
        """Paper-level verdict: ACCEPT if most sections carry a strong suggestion, REVISE
        if some do, REJECT if essentially none did (the paper is already tight)."""
        if not improvements:
            return Verdict.REJECT
        strong = sum(1 for i in improvements if i.verdict is Verdict.ACCEPT)
        some = sum(1 for i in improvements if i.verdict is not Verdict.REJECT)
        if strong >= max(1, len(improvements) // 2):
            return Verdict.ACCEPT
        if some:
            return Verdict.REVISE
        return Verdict.REJECT


def improve_paper(
    draft: PaperDraft,
    *,
    llm: LLMClient | None = None,
    personas: int = 2,
) -> PaperImprovement:
    """Convenience: run the paper-improver circle once and return the package."""
    return PaperImprover(llm, personas=personas).improve(draft)

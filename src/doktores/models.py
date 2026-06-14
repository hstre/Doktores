"""The data model for Doktores - the research organisation between Joni and Kevin.

Following the ecosystem convention (DESi / AleXiona / Kevin / Joni): **LLM for
language, rules for logic.** Everything in this module is plain, deterministic data.
All routing, scoring and verdicts live in the role engines and the orchestrator and
operate on these structures only - the language layer never produces a number or a
verdict.

Three invariants borrowed from the ecosystem:

  * **Closed enumerations** - the reviewer's verdict set is fixed; no open-world
    category invention.
  * **Replay-stable identity** - ids are content hashes (:func:`stable_id`), never
    random, so a whole research run is reproducible and packages dedupe cleanly.
  * **Outputs are SOURCES, not beliefs** - the :class:`ResearchOutput` package is a
    *candidate* handed back to Joni. A paper does not become true because the
    in-house team wrote it; the recommended claim updates enter Joni as SOURCES and
    are never self-confirmed here.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import StrEnum


def stable_id(prefix: str, *parts: str) -> str:
    """A replay-stable id: ``prefix_<first 12 hex of sha256(parts)>``.

    No PRNG anywhere in Doktores - identical inputs always yield identical ids, so a
    research run is reproducible and a re-run produces a package with the same id (which
    is exactly what Joni's intake dedupes on).
    """
    digest = hashlib.sha256("\x00".join(parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:12]}"


# --------------------------------------------------------------------------- #
# Closed enumerations
# --------------------------------------------------------------------------- #


class Verdict(StrEnum):
    """The Adversarial Reviewer's closed verdict set - the package's gate.

    Mirrors the contract Joni's ``research_intake`` agrees on: a ``REJECT`` skips the
    epistemic channel entirely (the publication is still archived for the audit trail).
    """

    ACCEPT = "accept"   # falsifiable, method-checked, evidence on balance survives review
    REVISE = "revise"   # worth pursuing but not yet sound - hold, do another round
    REJECT = "reject"   # unfalsifiable / mere renaming / a simpler explanation wins - drop


class PublicationKind(StrEnum):
    """The closed kinds the publication channel may carry (mirrors Joni's schema)."""

    PAPER = "paper"
    REPORT = "report"
    PROTOCOL = "protocol"
    REPLICATION = "replication"
    SUMMARY = "summary"


# --------------------------------------------------------------------------- #
# The research anlass - what seeds a run (read-only from Joni / Kevin)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ResearchTask:
    """One research occasion: a productive Layer-9 conflict plus Kevin's candidates.

    ``source_hypothesis_ids`` are the Layer-9 claim/conflict ids that seeded the work -
    they travel with the package back to Joni so provenance is real. ``candidates`` are
    the hypotheses Kevin produced for this conflict (its creative raw material). This
    object is built by reading Joni Layer 9 and Kevin; Doktores never writes back through
    it.
    """

    conflict: str
    source_hypothesis_ids: tuple[str, ...] = ()
    topic: str = "research"
    candidates: tuple[str, ...] = ()
    context: str = ""

    @property
    def id(self) -> str:
        return stable_id("task", self.conflict, self.topic, *self.source_hypothesis_ids)


# --------------------------------------------------------------------------- #
# Role outputs (each of the seven roles emits one of these)
# --------------------------------------------------------------------------- #


@dataclass
class Theory:
    """Role 1 - the Theorist's precise formulation.

    The LLM phrases the prose; the *structure* (closed fields, clamped prediction count)
    is assembled deterministically.
    """

    statement: str
    terms: tuple[str, ...] = ()
    mechanism: str = ""
    preconditions: tuple[str, ...] = ()
    predictions: tuple[str, ...] = ()
    demarcation: str = ""

    @property
    def id(self) -> str:
        return stable_id("theory", self.statement)


@dataclass
class EvidenceItem:
    """A single weighed piece of evidence. ``strength`` in [0, 1] is assigned by rules."""

    text: str
    ref: str = ""
    strength: float = 0.0

    def to_dict(self) -> dict:
        return {"text": self.text, "ref": self.ref, "strength": round(self.strength, 4)}


@dataclass
class LiteratureFindings:
    """Role 2 - the Literature Scout's map of the surrounding field."""

    related_work: tuple[str, ...] = ()
    competing_explanations: tuple[str, ...] = ()
    known_counterexamples: tuple[str, ...] = ()
    datasets: tuple[str, ...] = ()
    evidence_for: list[EvidenceItem] = field(default_factory=list)
    evidence_against: list[EvidenceItem] = field(default_factory=list)


@dataclass
class FalsificationReport:
    """Role 3 - the Falsifier's attempt to destroy the theory.

    The booleans are *signals* (some read by the LLM, most derived by rules); the
    severity and what they imply for the verdict are computed downstream, never by the
    language layer.
    """

    refutation_conditions: tuple[str, ...] = ()
    is_falsifiable: bool = False
    simpler_explanation: str = ""
    merely_renaming: bool = False
    weakest_assumption: str = ""
    evidence_against: list[EvidenceItem] = field(default_factory=list)

    @property
    def fatal(self) -> bool:
        """A theory the Falsifier has structurally killed: unfalsifiable, or a mere
        renaming of the conflict it came from. The reviewer turns this into a REJECT."""
        return (not self.is_falsifiable) or self.merely_renaming


@dataclass
class Experiment:
    """One pilot design (Role 4). Plain data; the schema Joni archives expects exactly
    these keys."""

    design: str
    baselines: tuple[str, ...] = ()
    metrics: tuple[str, ...] = ()
    stop_criteria: str = ""

    def to_dict(self) -> dict:
        return {
            "design": self.design,
            "baselines": list(self.baselines),
            "metrics": list(self.metrics),
            "stop_criteria": self.stop_criteria,
        }


@dataclass
class MethodReview:
    """Role 5 - the Method Reviewer / Statistician's read.

    ``soundness`` in [0, 1] is computed deterministically from the design (baselines,
    metrics, stop criteria, sample reasoning); the LLM only phrases the ``concerns``.
    """

    concerns: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    soundness: float = 0.0


@dataclass
class ClaimUpdate:
    """One entry in the epistemic channel. ``op`` is closed: a new SOURCE claim, or a
    conflict held open against existing Layer-9 claims. Never a confirmation."""

    op: str            # "add_claim" | "open_conflict"
    text: str
    topic: str = "research"
    against: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        d: dict = {"op": self.op, "text": self.text, "topic": self.topic}
        if self.against:
            d["against"] = list(self.against)
        return d


@dataclass
class Publication:
    """The publication channel artefact (Role 6's draft). Archived by Joni with NO
    epistemic weight of its own."""

    kind: PublicationKind
    title: str
    markdown: str

    def to_dict(self) -> dict:
        return {"kind": self.kind.value, "title": self.title, "markdown": self.markdown}


@dataclass
class ReviewerVerdict:
    """Role 7 - the Adversarial Reviewer's call. ``verdict`` and ``confidence`` are both
    computed by rules from the scorecard; the LLM only phrases ``reasons``."""

    verdict: Verdict
    reasons: tuple[str, ...] = ()
    confidence: float = 0.0


# --------------------------------------------------------------------------- #
# The package handed back to Joni - exactly the research_output schema
# --------------------------------------------------------------------------- #


@dataclass
class ResearchOutput:
    """The structured ``research_output`` package - the only thing Doktores produces.

    It is a SOURCE, not a belief: whether any of it becomes a conviction is decided by
    Joni's governance alone. :meth:`to_dict` emits exactly the schema in
    ``joni.autonomy.research_intake.RESEARCH_OUTPUT_SCHEMA``.
    """

    source_hypothesis_ids: tuple[str, ...]
    theory: Theory
    evidence_for: list[EvidenceItem]
    evidence_against: list[EvidenceItem]
    experiments: list[Experiment]
    results: str
    limitations: tuple[str, ...]
    reviewer_verdict: Verdict
    confidence: float
    recommended_claim_updates: list[ClaimUpdate]
    publication: Publication

    @property
    def id(self) -> str:
        return stable_id("RO", self.theory.statement, *self.source_hypothesis_ids)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source_hypothesis_ids": list(self.source_hypothesis_ids),
            "theory": self.theory.statement,
            "predictions": list(self.theory.predictions),
            "evidence_for": [e.to_dict() for e in self.evidence_for],
            "evidence_against": [e.to_dict() for e in self.evidence_against],
            "experiments": [x.to_dict() for x in self.experiments],
            "results": self.results,
            "limitations": list(self.limitations),
            "reviewer_verdict": self.reviewer_verdict.value,
            "confidence": round(self.confidence, 4),
            "recommended_claim_updates": [u.to_dict() for u in self.recommended_claim_updates],
            "publication": self.publication.to_dict(),
        }


# The keys every package must carry. Kept here so the producer and Joni's consumer never
# drift; ``validate_research_output`` checks against it.
RESEARCH_OUTPUT_KEYS = (
    "id",
    "source_hypothesis_ids",
    "theory",
    "predictions",
    "evidence_for",
    "evidence_against",
    "experiments",
    "results",
    "limitations",
    "reviewer_verdict",
    "confidence",
    "recommended_claim_updates",
    "publication",
)

_VALID_VERDICTS = {v.value for v in Verdict}
_VALID_OPS = {"add_claim", "open_conflict"}
_VALID_PUB_KINDS = {k.value for k in PublicationKind}


def validate_research_output(pkg: dict) -> list[str]:
    """Return a list of human-readable problems with a package dict (empty == valid).

    This is the contract Joni relies on. It also enforces the governance boundary at the
    producer side: the package may only *recommend* (``add_claim`` / ``open_conflict``);
    there is deliberately no operation that could confirm a belief, and ``confidence`` is
    a bounded internal number, **not** a probability of truth.
    """
    errors: list[str] = []
    for key in RESEARCH_OUTPUT_KEYS:
        if key not in pkg:
            errors.append(f"missing key: {key}")
    if errors:
        return errors

    if not str(pkg["id"]):
        errors.append("id must be a non-empty stable string")
    if not isinstance(pkg["source_hypothesis_ids"], list):
        errors.append("source_hypothesis_ids must be a list")
    if not str(pkg["theory"]).strip():
        errors.append("theory must be a non-empty string")
    if not isinstance(pkg["predictions"], list):
        errors.append("predictions must be a list")

    for side in ("evidence_for", "evidence_against"):
        if not isinstance(pkg[side], list):
            errors.append(f"{side} must be a list")
            continue
        for e in pkg[side]:
            if not isinstance(e, dict) or "text" not in e or "strength" not in e:
                errors.append(f"{side} items need text + strength")
                break
            if not 0.0 <= float(e.get("strength", -1)) <= 1.0:
                errors.append(f"{side} strength must be in [0, 1]")
                break

    if not isinstance(pkg["experiments"], list):
        errors.append("experiments must be a list")
    if pkg["reviewer_verdict"] not in _VALID_VERDICTS:
        errors.append(f"reviewer_verdict must be one of {sorted(_VALID_VERDICTS)}")
    if not 0.0 <= float(pkg["confidence"]) <= 1.0:
        errors.append("confidence must be in [0, 1] (an internal number, not a probability)")

    updates = pkg["recommended_claim_updates"]
    if not isinstance(updates, list):
        errors.append("recommended_claim_updates must be a list")
    else:
        for u in updates:
            if not isinstance(u, dict) or u.get("op") not in _VALID_OPS:
                errors.append(f"each claim update needs op in {sorted(_VALID_OPS)}")
                break
            if not str(u.get("text", "")).strip():
                errors.append("each claim update needs non-empty text")
                break

    pub = pkg["publication"]
    if not isinstance(pub, dict) or pub.get("kind") not in _VALID_PUB_KINDS:
        errors.append(f"publication.kind must be one of {sorted(_VALID_PUB_KINDS)}")
    elif not str(pub.get("title", "")).strip():
        errors.append("publication.title must be non-empty")

    return errors

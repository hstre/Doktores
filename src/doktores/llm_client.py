"""The language boundary.

Everything the LLM is *allowed* to do passes through this interface, and nothing else
does. The contract enforces the ecosystem rule **LLM for language, rules for logic**:

  * The LLM *phrases* a theory, writes refutation conditions, drafts experiment prose and
    paper sections, and words the reviewer's reasons.
  * The LLM never decides falsifiability, never scores soundness, never picks a verdict,
    never sets the confidence. Those are all rules, in the role engines.

A :class:`MockLLM` is the default so the whole pipeline, the tests and CI run offline and
replay-stably with no API key (exactly like Kevin). A real OpenAI-compatible client
(DeepSeek / OpenRouter / GPT-4o, matching the rest of the ecosystem) drops in behind the
same Protocol without touching any engine. Set ``DOKTORES_USE_REAL_LLM=1`` to switch.
"""

from __future__ import annotations

import hashlib
import os
import time
from typing import Protocol, runtime_checkable

# Substrings that mark a *transient* failure worth retrying (mirrors Kevin's llm_client):
# notably the proxied-egress DNS quirk seen in managed environments. Genuine auth/4xx
# errors do not match and are never retried.
_TRANSIENT_MARKERS = (
    "resolve_no_records", "private/reserved", "temporarily", "timeout", "timed out",
    "connection", "overloaded", "rate limit", "too many requests",
    "502", "503", "504", "bad gateway", "service unavailable", "gateway timeout",
)
_TRANSIENT_EXCEPTIONS = {
    "APIConnectionError", "APITimeoutError", "RateLimitError",
    "InternalServerError", "APIStatusError",
}


def _is_transient(exc: Exception) -> bool:
    if type(exc).__name__ in _TRANSIENT_EXCEPTIONS:
        return True
    blob = str(exc).lower()
    return any(marker in blob for marker in _TRANSIENT_MARKERS)


def _seed(*parts: str) -> int:
    """Deterministic integer seed from text - replaces a PRNG so runs replay."""
    return int(hashlib.sha256("|".join(parts).encode()).hexdigest(), 16)


@runtime_checkable
class LLMClient(Protocol):
    """The only surface through which language enters Doktores."""

    def theorize(self, conflict: str, candidates: list[str]) -> dict:
        """Phrase a theory from a conflict + Kevin's candidates.

        Returns a dict with keys ``statement``/``mechanism``/``terms``/``preconditions``/
        ``predictions``/``demarcation``. This is language work - extraction and phrasing.
        The Theorist engine normalises the shape; it never asks the LLM for a score.
        """

    def phrase(self, kind: str, context: str) -> str:
        """Word one short artefact (a weakest assumption, an experiment design, a paper
        section, a reviewer reason). Pure language; no judgement, no numbers."""

    def phrase_list(self, kind: str, context: str, n: int) -> list[str]:
        """Word ``n`` short artefacts of one kind (refutation conditions, concerns, …)."""


# --------------------------------------------------------------------------- #
# The offline default
# --------------------------------------------------------------------------- #


class MockLLM:
    """Deterministic, offline stand-in for a real language model.

    It produces plausible, varied, *replay-stable* text by hash-selecting from templates.
    It is not intelligent - it exists so the routing/scoring/verdict logic can be
    exercised and tested without a network. Swap in a real client for real language; the
    engines do not change.
    """

    _MECHANISMS = (
        "a feedback loop amplifies small differences until they dominate the outcome",
        "a shared latent cause drives both observations, so the apparent link is indirect",
        "a threshold effect flips the behaviour once a hidden quantity is exceeded",
        "selection pressure on the inputs makes the surviving cases look correlated",
        "an unmodelled delay makes cause and effect appear in the wrong order",
    )
    _DEMARCATIONS = (
        "It does not claim {a} in general - only under the stated preconditions.",
        "It is distinct from the trivial reading: it forbids {a}, which the rival allows.",
        "Unlike a redescription, it commits to {a} that could be measured and missed.",
    )
    _PREDICTION_FRAMES = (
        "Removing {t} should reduce the effect by a measurable margin, not leave it intact.",
        "Holding {t} fixed should make the difference disappear rather than merely shrink.",
        "If {t} is the lever, perturbing it should move the outcome monotonically.",
        "Cases high in {t} should outperform matched controls on the primary metric.",
    )

    # -- LLMClient surface -------------------------------------------------- #
    def theorize(self, conflict: str, candidates: list[str]) -> dict:
        terms = _salient_terms(conflict + " " + " ".join(candidates))
        seed = _seed(conflict, *candidates)
        lead = (candidates[0] if candidates else conflict).strip().rstrip(".")
        mechanism = self._MECHANISMS[seed % len(self._MECHANISMS)]
        statement = (
            f"Under the stated conditions, {lead.lower()}; the proposed mechanism is that "
            f"{mechanism}."
        )
        anchor = terms[0] if terms else "the driver"
        demarc = self._DEMARCATIONS[seed % len(self._DEMARCATIONS)].format(
            a=f"any role for {anchor}"
        )
        # Two-to-three falsifiable predictions, each anchored on a salient term so they
        # carry the comparative markers the Falsifier's rule looks for.
        preds = []
        for i, t in enumerate((terms or ("the driver",))[:3]):
            frame = self._PREDICTION_FRAMES[(seed + i) % len(self._PREDICTION_FRAMES)]
            preds.append(frame.format(t=t))
        return {
            "statement": statement,
            "mechanism": mechanism,
            "terms": terms[:6],
            "preconditions": (
                f"the population is restricted to cases where {anchor} actually varies",
                "confounders identified by the Method Reviewer are controlled or measured",
            ),
            "predictions": preds,
            "demarcation": demarc,
        }

    def phrase(self, kind: str, context: str) -> str:
        ctx = context.strip()
        seed = _seed(kind, ctx)
        if kind == "weakest_assumption":
            opts = (
                f"that {_first_clause(ctx)} holds independently of measurement, which is untested",
                "that the mechanism is causal rather than a shared upstream cause",
                "that the effect size survives once obvious confounders are controlled",
            )
            return opts[seed % len(opts)]
        if kind == "experiment_design":
            return (
                f"A minimal pilot that operationalises '{_first_clause(ctx)}': pre-register the "
                "primary metric, randomise assignment where possible, and run the smallest sample "
                "that could detect the predicted effect."
            )
        if kind.startswith("paper:"):
            section = kind.split(":", 1)[1]
            return _PAPER_PROSE.get(section, "").format(ctx=_first_clause(ctx)) or (
                f"{section.title()}: {_first_clause(ctx)}."
            )
        if kind == "review_reason":
            return _first_clause(ctx)
        if kind == "paper_suggestion":
            head, _, angle = ctx.partition("|| angle:")
            term = (_salient_terms(head) or _salient_terms(angle) or ("the central claim",))[0]
            opts = (
                f"Make the role of {term} explicit up front, then let the rest of "
                f"'{_first_clause(head)}' follow from it.",
                f"Lead with the consequence for {term}; move the justification after it so the "
                "reader meets the payoff before the machinery.",
                f"State what would change if {term} were false - the section currently asserts "
                "where it could discriminate.",
            )
            return opts[seed % len(opts)]
        if kind == "paper_rewrite":
            # Context: "HEADING: ..\nORIGINAL: ..\nFIX THESE WEAKNESSES: ..\n<brief>".
            body = ctx.split("ORIGINAL:", 1)[1] if "ORIGINAL:" in ctx else ctx
            body = body.split("FIX THESE WEAKNESSES", 1)[0]
            term = (_salient_terms(body) or ("the central claim",))[0]
            return (
                f"{_first_clause(body)}. Here {term} is stated first with the single condition "
                "under which it would fail, the surrounding prose is tied back to that one "
                "thread, and no new claims are introduced."
            )
        if kind == "paper_summary":
            return (
                "Across the manuscript the strongest leverage is sharper framing and explicit "
                f"failure conditions: {_first_clause(ctx)}."
            )
        if kind in (
            "open_question", "why_unasked", "answer_approach", "answer_test",
            "builds_toward", "extension_summary",
        ):
            return _extension_phrase(kind, ctx, seed)
        return _first_clause(ctx)

    def phrase_list(self, kind: str, context: str, n: int) -> list[str]:
        ctx = context.strip()
        out: list[str] = []
        if kind == "refutation":
            frames = (
                "Observing no change in the outcome when {t} is removed would refute it.",
                "Finding the same effect in cases where {t} is absent would refute it.",
                "A simpler model without {t} predicting the data equally well would refute it.",
            )
            terms = _salient_terms(ctx) or ("the proposed driver",)
            for i in range(n):
                out.append(frames[i % len(frames)].format(t=terms[i % len(terms)]))
            return out
        if kind == "concern":
            bank = (
                "sample size may be too small to separate effect size from noise",
                "the comparison lacks a matched baseline, inviting confounding",
                "multiple metrics are tested without correcting the significance threshold",
                "measurement error in the predictor would attenuate the reported effect",
                "robustness to an alternative analysis path was not checked",
            )
            for i in range(n):
                out.append(bank[(_seed(ctx) + i) % len(bank)])
            return out
        if kind in ("paper_weakness", "paper_global_weakness"):
            terms = _salient_terms(ctx) or ("the central claim",)
            frames = (
                "{t} is asserted but never given an explicit condition under which it fails.",
                "the prose around {t} mixes the claim with its justification, blurring both.",
                "{t} is introduced without saying what it is being contrasted against.",
                "the section leans on {t} as a label where a concrete mechanism is needed.",
                "{t} is stated once and not tied back to the section's main thread.",
            )
            base = _seed(kind, ctx)
            for i in range(n):
                t = terms[i % len(terms)]
                out.append(frames[(base + i) % len(frames)].format(t=t.capitalize()))
            return out
        for i in range(n):
            out.append(f"{kind} {i + 1}: {_first_clause(ctx)}")
        return out


_PAPER_PROSE = {
    "problem": "We study an open conflict in the host system: {ctx}.",
    "related_work": "Prior accounts explain {ctx} differently; we contrast them below.",
    "theory": "We propose that {ctx}, stated precisely with explicit preconditions.",
    "method": "We test the theory with a pre-registered minimal pilot: {ctx}.",
    "results": "Results are reported as {ctx} (or marked 'not yet run' when the pilot is unrun).",
    "limitations": "The account is limited by {ctx} and by the assumptions the Falsifier flagged.",
    "open_questions": "It remains open whether {ctx} generalises beyond the studied regime.",
}


def _salient_terms(text: str) -> tuple[str, ...]:
    """Deterministic, content-free keyword pull: the longer, distinctive words, de-duped
    in order of appearance. Used only to anchor phrasing - never to score anything."""
    seen: list[str] = []
    for raw in text.lower().replace("/", " ").replace("-", " ").split():
        w = "".join(ch for ch in raw if ch.isalnum())
        if len(w) > 4 and w not in _STOP and w not in seen:
            seen.append(w)
    return tuple(seen)


def _first_clause(text: str) -> str:
    t = text.strip().replace("\n", " ")
    for sep in (". ", "; ", " - "):
        if sep in t:
            return t.split(sep, 1)[0].strip()
    return t[:200].strip() or "the claim under study"


_STOP = {
    "which", "their", "there", "these", "those", "would", "could", "should", "about",
    "where", "while", "being", "under", "after", "before", "between", "because", "claim",
    "conflict", "theory", "system", "value", "values",
}


def _extension_phrase(kind: str, ctx: str, seed: int) -> str:
    """Deterministic phrasing for the paper-extension kinds (offline MockLLM)."""
    term = (_salient_terms(ctx) or ("the central mechanism",))[0]
    axis = "an unexamined dimension"
    for marker in ("LENS", "DIMENSION"):
        if marker in ctx:
            tail = ctx.split(marker, 1)[1]
            axis = tail.split(":", 1)[-1].splitlines()[0].strip() or axis
            break
    if kind == "open_question":
        return (
            f"Under what conditions does {term} still hold once the {axis} dimension is "
            "varied - the regime the paper does not probe?"
        )
    if kind == "why_unasked":
        return (
            f"The paper fixes {term} and never varies it along {axis}, so the question falls "
            "outside its stated scope."
        )
    if kind == "answer_approach":
        return (
            f"Vary {term} systematically while holding the paper's setup fixed, and read off "
            "the effect from the cheapest discriminating case first."
        )
    if kind == "answer_test":
        return (
            f"The answer is falsified if {term} shows no measurable change across the varied "
            "regime, or if a simpler account predicts the same result."
        )
    if kind == "builds_toward":
        return (
            f"A validated answer would extend the paper from a single result toward a rule "
            f"over the {axis} dimension."
        )
    return f"The paper's main openings lie along dimensions it does not work: {_first_clause(ctx)}."


# --------------------------------------------------------------------------- #
# The real language layer (OpenAI-compatible: DeepSeek / OpenRouter / GPT-4o)
# --------------------------------------------------------------------------- #


class OpenAICompatibleLLM:
    """A real language layer via the OpenAI-compatible SDK.

    Matches the rest of the ecosystem (DESi / AleXiona / Kevin ``llm_client.py``):
    ``DEEPSEEK_API_KEY`` takes priority, then ``OPENROUTER_API_KEY``, then
    ``OPENAI_API_KEY``; the client selects the matching model and base URL. This class is
    the *only* place a network call happens - the engines never change. Budget-bewusst:
    short prompts, low temperatures, transient-only retry.
    """

    def __init__(self, model: str | None = None, base_url: str | None = None,
                 api_key: str | None = None) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - exercised only without the extra
            raise RuntimeError(
                "The real LLM client needs the 'openai' package. "
                "Install it with: pip install 'doktores[llm]'"
            ) from exc

        deepseek = api_key or os.getenv("DEEPSEEK_API_KEY") or os.getenv("DEEPSEEK_API_KEY2")
        openrouter = os.getenv("OPENROUTER_API_KEY")
        openai_key = os.getenv("OPENAI_API_KEY")
        if deepseek:
            self._model = model or "deepseek-chat"
            self._client = OpenAI(api_key=deepseek,
                                  base_url=base_url or "https://api.deepseek.com")
        elif openrouter:
            self._model = model or os.getenv("DOKTORES_MODEL", "deepseek/deepseek-chat")
            self._client = OpenAI(api_key=openrouter,
                                  base_url=base_url or "https://openrouter.ai/api/v1")
        elif openai_key:
            self._model = model or "gpt-4o"
            self._client = OpenAI(api_key=openai_key, base_url=base_url)
        else:  # pragma: no cover - config error path
            raise RuntimeError(
                "No LLM key found. Set DEEPSEEK_API_KEY / OPENROUTER_API_KEY / OPENAI_API_KEY "
                "(see .env.example), or unset DOKTORES_USE_REAL_LLM to use the MockLLM."
            )
        self._max_retries = int(os.getenv("DOKTORES_LLM_RETRIES", "4"))
        self._backoff_base = float(os.getenv("DOKTORES_LLM_BACKOFF", "0.5"))

    def _chat(self, system: str, user: str, *, temperature: float, json: bool = False) -> str:
        kwargs: dict = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
        }
        if json:
            kwargs["response_format"] = {"type": "json_object"}
        last: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                resp = self._client.chat.completions.create(**kwargs)
                return resp.choices[0].message.content or ""
            except Exception as exc:  # noqa: BLE001 - retry only transient, re-raise the rest
                if attempt >= self._max_retries or not _is_transient(exc):
                    raise
                last = exc
                time.sleep(self._backoff_base * (2 ** attempt))
        raise last  # unreachable, keeps the type checker honest

    @staticmethod
    def _parse_json(raw: str) -> dict:
        import json as _json

        try:
            return _json.loads(raw)
        except _json.JSONDecodeError:
            start, end = raw.find("{"), raw.rfind("}")
            if start != -1 and end > start:
                try:
                    return _json.loads(raw[start:end + 1])
                except _json.JSONDecodeError:
                    pass
            return {}

    def theorize(self, conflict: str, candidates: list[str]) -> dict:
        system = (
            "You are the THEORIST in a research team. Turn a conflict and candidate "
            "hypotheses into ONE precise theory. Be explicit and falsifiable. Reply as JSON "
            'with keys: statement, mechanism, terms (array), preconditions (array), '
            "predictions (array of falsifiable predictions), demarcation. You do NOT judge "
            "or score - you only formulate."
        )
        cand = "\n".join(f"- {c}" for c in candidates) or "- (none supplied)"
        user = f"Conflict:\n{conflict}\n\nCandidate hypotheses:\n{cand}"
        data = self._parse_json(self._chat(system, user, temperature=0.4, json=True))
        return data if isinstance(data, dict) else {}

    def phrase(self, kind: str, context: str) -> str:
        system = (
            "You word one short research artefact in one or two sentences. You only phrase; "
            "you never add a score, a probability or a verdict."
        )
        user = f"Kind: {kind}\nContext: {context}"
        return self._chat(system, user, temperature=0.4).strip()

    def phrase_list(self, kind: str, context: str, n: int) -> list[str]:
        system = (
            f"You word exactly {n} short research artefacts of kind '{kind}', one per line, "
            "no numbering. Language only - no scores, no verdicts."
        )
        user = f"Context: {context}"
        lines = [ln.strip(" -*\t") for ln in self._chat(system, user, temperature=0.5).splitlines()]
        return [ln for ln in lines if ln][:n]


def get_default_client() -> LLMClient:
    """Return the configured client.

    Without ``DOKTORES_USE_REAL_LLM=1``, returns the deterministic :class:`MockLLM` - so
    tests, CI and a fresh clone all work with zero setup. With it set, returns the real
    OpenAI-compatible client (needs the ``llm`` extra and a key). The engines are identical
    either way; only the language layer moves.
    """
    if os.getenv("DOKTORES_USE_REAL_LLM") == "1":  # pragma: no cover - needs a key + network
        return OpenAICompatibleLLM()
    return MockLLM()

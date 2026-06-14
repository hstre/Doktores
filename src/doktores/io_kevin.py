"""Integration seam: Kevin - the hypothesis source.

Doktores does not invent its own raw hypotheses; that is Kevin's job (creativity-routing).
For a given conflict, we ask Kevin for candidates and keep the ones its own epistemic
selector did not reject - exactly the handoff the design prescribes:

    from kevin import Kevin, Problem
    run = Kevin().run(Problem(statement, domain, constraints, known_approaches))
    # run.candidates / run.evaluations  (Verdict promising | tentative | rejected)

Kevin is an *optional* dependency. If it is not importable (a bare Doktores install, or a
test that supplies its own candidates), this returns an empty tuple and the Theorist simply
works from the conflict text alone. We never hard-fail on a missing sibling system.
"""

from __future__ import annotations

# Kevin's selector keeps these; "rejected" candidates are dropped before they reach us.
_KEEP_VERDICTS = {"promising", "tentative"}


def candidates_for(
    conflict: str,
    *,
    domain: str = "research",
    constraints: tuple[str, ...] = (),
    known_approaches: tuple[str, ...] = (),
    limit: int = 4,
) -> tuple[str, ...]:
    """Ask Kevin for non-rejected candidate hypotheses about ``conflict``.

    Deterministic with Kevin's default MockLLM; returns at most ``limit`` candidate texts in
    Kevin's own order. Empty tuple when Kevin is not installed.
    """
    try:
        from kevin import Kevin, Problem
    except Exception:  # noqa: BLE001 - missing/broken optional dep must never crash a run
        return ()

    run = Kevin().run(
        Problem(
            statement=conflict,
            domain=domain,
            constraints=tuple(constraints),
            known_approaches=tuple(known_approaches),
        )
    )
    kept_ids = {
        e.candidate_id
        for e in run.evaluations
        if getattr(e.verdict, "value", str(e.verdict)) in _KEEP_VERDICTS
    }
    texts: list[str] = []
    for cand in run.candidates:
        if cand.id in kept_ids and cand.content not in texts:
            texts.append(cand.content)
        if len(texts) >= limit:
            break
    return tuple(texts)

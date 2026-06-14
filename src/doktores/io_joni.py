"""Integration seam: Joni Layer 9 - the research *anlass* (read) and the return drop (write).

Two directions, institutionally separated and both governance-safe:

**Reading the occasion.** Doktores never writes into Layer 9 and prefers never to even *read*
it live. The primary path is a **decoupled handoff file**: a human (or Joni's own export step)
drops a small JSON list of open conflicts, and Doktores researches those. A best-effort live
reader is offered as a fallback for convenience, but it only *reads* ``cs.core.open_conflicts()``
and ``cs.active_claims()`` - it holds no write capability at all.

**Returning the result.** Doktores writes a JSON list of ``research_output`` packages into
Joni's ``state/research_inbox.json`` drop directory. Joni's ``research_intake`` reads them as
SOURCES (origin ``internal-research``), holds conflicts open, and never auto-confirms. We only
ever *append* (dedupe by id); we never touch Layer 9 itself.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from .models import ResearchTask, validate_research_output

# --------------------------------------------------------------------------- #
# Reading the occasion
# --------------------------------------------------------------------------- #


def read_tasks_from_handoff(path: str | Path) -> list[ResearchTask]:
    """Read research occasions from a decoupled handoff JSON file (the preferred path).

    The file is a JSON list of objects, each: ``{conflict, source_hypothesis_ids?, topic?,
    candidates?, context?}``. Unknown keys are ignored; a malformed file yields an empty list
    rather than raising - a bad drop must never crash the research loop.
    """
    p = Path(path)
    if not p.exists():
        return []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(raw, list):
        return []

    tasks: list[ResearchTask] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        conflict = str(item.get("conflict", "")).strip()
        if not conflict:
            continue
        tasks.append(
            ResearchTask(
                conflict=conflict,
                source_hypothesis_ids=tuple(
                    str(x) for x in item.get("source_hypothesis_ids", []) or []
                ),
                topic=str(item.get("topic", "research")) or "research",
                candidates=tuple(str(x) for x in item.get("candidates", []) or []),
                context=str(item.get("context", "")),
            )
        )
    return tasks


def read_tasks_from_layer9(root: str | Path | None = None) -> list[ResearchTask]:
    """Best-effort live read of Joni's open Layer-9 conflicts. **Read-only.**

    Imports Joni only if available; returns an empty list otherwise (a bare Doktores install,
    or any environment without Joni's core, simply uses the handoff path). It never imports a
    write capability and never mutates Joni's state.
    """
    if root is not None:
        os.environ.setdefault("JONI_AUTONOMY_ROOT", str(root))
    try:
        from joni.autonomy.config import paths
        from joni.autonomy.core_state import load_or_migrate
    except Exception:  # noqa: BLE001 - Joni not installed here; use the handoff file instead
        return []

    try:
        cs = load_or_migrate(paths())
        claims = {c.id: c for c in cs.active_claims()}
        tasks: list[ResearchTask] = []
        for conflict in cs.core.open_conflicts():
            texts = [claims[cid].text for cid in conflict.claim_ids if cid in claims]
            topic = next(
                (claims[cid].topic for cid in conflict.claim_ids if cid in claims), "research"
            )
            description = " ⟂ ".join(t for t in texts if t) or f"open {conflict.kind} conflict"
            tasks.append(
                ResearchTask(
                    conflict=description,
                    source_hypothesis_ids=(*conflict.claim_ids, conflict.id),
                    topic=topic or "research",
                )
            )
        return tasks
    except Exception:  # noqa: BLE001 - any live-read hiccup degrades to "no live tasks"
        return []


def read_tasks(
    handoff: str | Path | None = None, *, root: str | Path | None = None
) -> list[ResearchTask]:
    """Read occasions, preferring the decoupled handoff file, falling back to a live read."""
    if handoff is not None:
        tasks = read_tasks_from_handoff(handoff)
        if tasks:
            return tasks
    return read_tasks_from_layer9(root)


# --------------------------------------------------------------------------- #
# Returning the result
# --------------------------------------------------------------------------- #


def joni_research_inbox(root: str | Path) -> Path:
    """The path Joni reads research packages from: ``<root>/state/research_inbox.json``.

    Mirrors ``joni.autonomy.config.Paths.research_inbox`` so the two sides cannot drift, but
    computed locally so we need no Joni import to write the drop.
    """
    return Path(root) / "state" / "research_inbox.json"


def write_research_inbox(
    packages: list[dict], inbox: str | Path, *, validate: bool = True
) -> dict:
    """Append ``research_output`` packages to Joni's inbox (a JSON list), deduped by id.

    Idempotent: re-dropping a package with the same id replaces nothing and adds nothing, so
    re-running Doktores is safe. With ``validate=True`` (default) a package failing the shared
    schema is skipped rather than written, so a malformed package never reaches Joni. Returns a
    small summary: ``{written, skipped, total}``.
    """
    path = Path(inbox)
    path.parent.mkdir(parents=True, exist_ok=True)

    existing: list[dict] = []
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                existing = [p for p in loaded if isinstance(p, dict)]
        except (json.JSONDecodeError, OSError):
            existing = []

    by_id = {str(p.get("id")): p for p in existing if p.get("id")}
    written = skipped = 0
    for pkg in packages:
        if validate and validate_research_output(pkg):
            skipped += 1
            continue
        pid = str(pkg.get("id"))
        if not pid or pid in by_id:
            skipped += 1
            continue
        by_id[pid] = pkg
        written += 1

    merged = list(by_id.values())
    path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"written": written, "skipped": skipped, "total": len(merged)}

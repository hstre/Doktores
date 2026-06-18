"""Doktores CLI demonstrator.

    # research one conflict offline (deterministic MockLLM), print the package
    python -m doktores "routing prefers locality but memory prefers recency" --topic routing

    # pull candidate hypotheses from Kevin first, then research, drop the result for Joni
    python -m doktores "..." --topic routing --use-kevin --joni-root ../Joni

    # research a batch of occasions a handoff file describes, write packages to an inbox
    python -m doktores --from-handoff handoff.json --inbox out/research_inbox.json

Runs the full controlled circle offline and prints schema-valid ``research_output`` packages.
Writing to ``--joni-root`` / ``--inbox`` only ever *appends* (deduped) to Joni's drop file;
it never touches Layer 9.
"""

from __future__ import annotations

import argparse
import json

from . import io_joni, io_kevin
from .models import ResearchTask
from .orchestrator import Doktores


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="doktores",
        description="Doktores - turn Joni Layer-9 conflicts + Kevin candidates into worked "
        "research_output packages (a SOURCE for Joni, never a belief).",
    )
    p.add_argument("conflict", nargs="?", help="the conflict / open question to research")
    p.add_argument("--topic", default="research")
    p.add_argument("--id", action="append", default=[], dest="ids",
                   help="a seeding Layer-9 claim/conflict id (repeatable)")
    p.add_argument("--candidate", action="append", default=[], dest="candidates",
                   help="a candidate hypothesis to seed the Theorist (repeatable)")
    p.add_argument("--use-kevin", action="store_true",
                   help="ask Kevin for candidate hypotheses for the conflict")
    p.add_argument("--from-handoff", metavar="PATH",
                   help="read a JSON list of occasions instead of a single conflict")
    p.add_argument("--layer9-root", metavar="PATH",
                   help="fallback: best-effort read of open conflicts from a Joni repo (read-only)")
    p.add_argument("--rounds", type=int, default=3, help="max Theorist/Falsifier/Reviewer rounds")
    p.add_argument("--inbox", metavar="PATH", help="append the packages to this inbox JSON file")
    p.add_argument("--joni-root", metavar="PATH",
                   help="append to <root>/state/research_inbox.json (Joni's drop directory)")
    # Paper-improver mode (parallel to research mode): improve a manuscript instead.
    p.add_argument("--improve-paper", metavar="PATH",
                   help="paper-improver mode: read a paper JSON "
                        "{title,topic,abstract,claims,sections:[{heading,text}]} and improve it")
    p.add_argument("--demo-paper", action="store_true",
                   help="paper-improver mode on the bundled Reality Gap paper fixture")
    p.add_argument("--personas", type=int, default=2,
                   help="paper mode: number of wild-brother personas in the embedded Kevin")
    return p


def _tasks(args) -> list[ResearchTask]:
    if args.from_handoff:
        return io_joni.read_tasks(args.from_handoff, root=args.layer9_root)
    if args.conflict:
        candidates = tuple(args.candidates)
        if args.use_kevin:
            candidates = candidates + io_kevin.candidates_for(args.conflict, domain=args.topic)
        return [ResearchTask(
            conflict=args.conflict,
            source_hypothesis_ids=tuple(args.ids),
            topic=args.topic,
            candidates=candidates,
        )]
    if args.layer9_root:
        return io_joni.read_tasks_from_layer9(args.layer9_root)
    return []


def _load_paper(path: str):
    """Load a PaperDraft from a JSON file."""
    from .paper import PaperDraft, Section

    with open(path, encoding="utf-8") as fh:
        d = json.load(fh)
    return PaperDraft(
        title=d["title"],
        topic=d.get("topic", "general"),
        abstract=d.get("abstract", ""),
        claims=tuple(d.get("claims", ())),
        sections=tuple(Section(s["heading"], s["text"]) for s in d.get("sections", ())),
    )


def _run_paper_mode(args) -> int:
    from .paper import improve_paper

    if args.demo_paper:
        from .examples import rg_paper_draft
        draft = rg_paper_draft()
    else:
        draft = _load_paper(args.improve_paper)

    pkg = improve_paper(draft, personas=args.personas).to_dict()
    print(json.dumps(pkg, ensure_ascii=False, indent=2))
    print(
        f"  - {pkg['id']}: {pkg['reviewer_verdict']} (conf {pkg['confidence']}) "
        f"-> {len(pkg['section_improvements'])} section(s) reviewed",
        flush=True,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    # Paper-improver mode short-circuits the research circle.
    if args.demo_paper or args.improve_paper:
        return _run_paper_mode(args)

    tasks = _tasks(args)
    if not tasks:
        print("nothing to research: pass a conflict, --from-handoff, or --layer9-root",
              flush=True)
        return 2

    doktores = Doktores()
    packages = [doktores.run(t, max_rounds=args.rounds).to_dict() for t in tasks]

    inbox = args.inbox or (io_joni.joni_research_inbox(args.joni_root) if args.joni_root else None)
    if inbox:
        summary = io_joni.write_research_inbox(packages, inbox)
        print(f"wrote {summary['written']} new package(s) to {inbox} "
              f"(skipped {summary['skipped']}, {summary['total']} total)")
    else:
        print(json.dumps(packages, ensure_ascii=False, indent=2))

    for pkg in packages:
        print(f"  - {pkg['id']}: {pkg['reviewer_verdict']} (conf {pkg['confidence']}) "
              f"-> {len(pkg['recommended_claim_updates'])} update(s), "
              f"publication: {pkg['publication']['kind']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

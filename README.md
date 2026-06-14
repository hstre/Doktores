# Doktores

**An internally division-of-labour research organisation that sits between memory and
creativity.**

Doktores is the third system in a triad:

| System | Role | One line |
|---|---|---|
| **[Joni](https://github.com/hstre/Joni)** | **Memory & governance** | Holds the beliefs (Layer 9), decides what is confirmed, holds conflicts open. |
| **[Kevin](https://github.com/hstre/Kevin)** | **Creativity** | Produces candidate hypotheses by routing between unexplored spaces. |
| **Doktores** | **Research, scrutiny, acceptance** | Turns Joni's conflicts + Kevin's candidates into *worked research*. |

Doktores takes a productive **Layer-9 conflict** from Joni and the **candidate hypotheses**
Kevin generated for it, runs them through a seven-role research team, and hands the result
back as a structured **`research_output` package**.

> **The boundary that defines the system: Doktores advises, it never decides.**
> It produces the package; whether anything in it becomes a conviction is decided by Joni's
> governance *alone*. A paper does not become true because the in-house team wrote it.

## Why seven separate roles

No single model may simultaneously *invent*, *check*, *judge* and *confirm itself* — that is
how motivated reasoning launders a bad idea into a "result". Doktores splits those jobs into
seven roles, each its own module, with **deterministic orchestration and a language-only
LLM** (the ecosystem rule: *LLM for language, rules for logic*):

1. **Theorist** — formulates a precise theory from the conflict + candidates: terms,
   mechanism, preconditions, predictions, demarcation.
2. **Literature Scout** — maps existing accounts, competing explanations, known
   counterexamples, datasets (offline: a deterministic stub; optionally a real search).
3. **Falsifier** — tries to *destroy* the theory: is it falsifiable? a mere renaming? is
   there a simpler explanation? what is the weakest assumption?
4. **Experimental Designer** — a minimal pilot: baselines, metrics, stop criteria,
   reproducibility.
5. **Method Reviewer / Statistician** — sample size, confounding, measurement error,
   significance vs. effect size, multiple testing, robustness.
6. **Paper Builder** — *only now* writes it up: Problem, Related Work, Theory, Method,
   Results, Limitations, Open Questions.
7. **Adversarial Reviewer** — judges like a hard reviewer and may say no:
   `accept | revise | reject`.

Every verdict, score and routing decision is computed by rules in these engines. The LLM only
phrases language; it never emits a number or a verdict.

## The controlled circle (not a pipeline)

```
Joni Layer-9 conflict ─┐
                       ├─► Theorist ─► Falsifier ─┐ (fatal? jump back to Theorist)
Kevin candidates ──────┘                          ▼
        ▲                       Literature ─► Designer ─► Method Reviewer
        │                                                      │
        │                                              Paper Builder
        │                                                      │
        └──── research_output ◄──── Adversarial Reviewer ◄─────┘
              (SOURCE, held open)        accept │ revise │ reject
                                                └─ revise: another round
```

The terminal state is the Adversarial Reviewer's `accept`/`reject`, or the round budget
running out. A `revise` (or an early fatal falsification) jumps back to the Theorist with the
open concern pinned as a new precondition — so iteration is a real, reproducible change, not a
re-roll.

## Two return channels, institutionally separated

* **Epistemic** — `recommended_claim_updates` enter Joni as **SOURCES** (origin
  `internal-research`): candidate authority, conflict-checked, *never auto-confirmed*. A
  `reject` skips this channel entirely.
* **Publication** — the paper/report/protocol is archived under Joni's `docs/research/` with
  **no epistemic weight of its own**. A `reject` is still archived (marked rejected) for the
  audit trail.

## Install & run

```bash
make install          # pip install -e ".[dev]"
make test             # pytest  (offline, deterministic MockLLM)
make lint             # ruff
make demo             # one research run, printed
```

Runs fully **offline by default** (deterministic `MockLLM`) — no key needed for tests, CI or a
fresh clone. To use a real language layer, set `DOKTORES_USE_REAL_LLM=1` plus one of
`DEEPSEEK_API_KEY` / `OPENROUTER_API_KEY` / `OPENAI_API_KEY` (see `.env.example`). The engines
do not change; only the language layer moves. (This mirrors Kevin's `KEVIN_USE_REAL_LLM`.)

### As a library

```python
from doktores import Doktores, ResearchTask

task = ResearchTask(
    conflict="Routing prefers locality but memory prefers recency under drift.",
    topic="routing",
    source_hypothesis_ids=("C-12", "C-37"),     # the seeding Layer-9 claim/conflict ids
    candidates=("recency is a proxy for relevance, not its cause",),  # from Kevin
)
pkg = Doktores().run(task).to_dict()             # a schema-valid research_output package
```

### As a CLI

```bash
# research one conflict, pulling candidates from Kevin, and drop the result for Joni
python -m doktores "routing vs. recency under drift" --topic routing \
    --use-kevin --joni-root ../Joni

# research a batch from a handoff file, write packages to an inbox
python -m doktores --from-handoff examples/handoff.json --inbox out/research_inbox.json
```

## Integration seams

* **Kevin** (`io_kevin.candidates_for`) — calls `Kevin().run(Problem(...))` and keeps the
  candidates Kevin's own selector did not reject. Optional dependency; absent → Doktores
  works from the conflict text alone.
* **Joni, reading** (`io_joni.read_tasks`) — prefers a **decoupled handoff file** (a JSON list
  of open conflicts); a best-effort live read of `cs.core.open_conflicts()` is a fallback.
  **Doktores never writes to Layer 9.**
* **Joni, returning** (`io_joni.write_research_inbox`) — appends packages to Joni's
  `state/research_inbox.json` drop directory (deduped by id, idempotent). Joni's
  `src/joni/autonomy/research_intake.py` ingests them under the schema both sides agree on.

## The `research_output` package

`ResearchOutput.to_dict()` emits exactly the schema in
`joni.autonomy.research_intake.RESEARCH_OUTPUT_SCHEMA` (a guarded test enforces no drift):

```jsonc
{
  "id": "RO_…",                          // stable, for dedupe
  "source_hypothesis_ids": ["C-12"],     // the Layer-9 ids that seeded it
  "theory": "…",
  "predictions": ["…"],                  // falsifiable
  "evidence_for":    [{"text": "…", "ref": "…", "strength": 0.0}],
  "evidence_against":[{"text": "…", "ref": "…", "strength": 0.0}],
  "experiments": [{"design": "…", "baselines": [], "metrics": [], "stop_criteria": "…"}],
  "results": "not yet run",
  "limitations": ["…"],
  "reviewer_verdict": "accept | revise | reject",
  "confidence": 0.0,                     // internal number, NOT a probability of truth
  "recommended_claim_updates": [         // the epistemic channel (empty on reject)
    {"op": "add_claim", "text": "…", "topic": "…"},
    {"op": "open_conflict", "text": "…", "topic": "…", "against": ["C-12"]}
  ],
  "publication": {"kind": "paper|report|protocol|replication|summary",
                  "title": "…", "markdown": "…"}     // the publication channel
}
```

## A note on the optional self-loop

`.github/workflows/research-loop.yml` is analogous to Joni's `autonomy.yml` but **off by
default**: it has no schedule and runs only on a manual dispatch. It is a button, not a daemon
— matching *advises, never decides*. Enabling a cadence is a conscious human act.

## License

MIT — see [LICENSE](LICENSE).

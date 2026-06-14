# CLAUDE.md

This file guides Claude Code (claude.ai/code) when working in this repository.

## What Doktores is

The **research** system in a triad: **Joni** (memory & governance) holds beliefs in Layer 9
and decides what is confirmed; **Kevin** (creativity) produces candidate hypotheses; **Doktores**
turns Joni's Layer-9 conflicts + Kevin's candidates into *worked research* and hands the result
back as a structured `research_output` package.

**The boundary that defines the system: Doktores advises, it never decides.** It produces the
package; whether anything becomes a conviction is decided by Joni's governance alone. Outputs
are candidates / SOURCES, never beliefs — a paper is not true because the in-house team wrote
it. Keep this boundary: do not add a code path that confirms a belief or writes into Layer 9.

## The guiding rule

**LLM for language, rules for logic.** Orchestration, routing, scoring and verdicts are
deterministic; the LLM only phrases language. When changing reasoning behaviour, keep this
boundary — do not move a verdict, a score or the confidence into an LLM call. The LLM surface
is `llm_client.LLMClient` (just `theorize` / `phrase` / `phrase_list`); everything else is an
engine operating on plain dataclasses.

## Commands

```bash
make install   # pip install -e ".[dev]"
make test      # pytest (offline, deterministic MockLLM)
make lint      # ruff check .
make demo      # one research run, printed
```

Single test: `python -m pytest tests/test_orchestrator.py::test_reject_path_skips_the_epistemic_channel -q`

CI (`.github/workflows/ci.yml`) runs ruff + pytest on every branch. Match both before pushing.
`research-loop.yml` is the optional self-loop — **off by default** (manual dispatch only).

## Architecture (`src/doktores/`)

- `models.py` — all dataclasses + the `ResearchOutput` package and `validate_research_output`.
  `to_dict()` emits **exactly** `joni.autonomy.research_intake.RESEARCH_OUTPUT_SCHEMA`
  (a guarded test, `tests/test_joni_contract.py`, fails if the two drift).
- `llm_client.py` — `MockLLM` (deterministic, offline default) + `OpenAICompatibleLLM`. The
  switch is `DOKTORES_USE_REAL_LLM=1` (mirrors Kevin's `KEVIN_USE_REAL_LLM`); keys priority
  `DEEPSEEK_API_KEY` > `OPENROUTER_API_KEY` > `OPENAI_API_KEY`.
- The seven role engines, one module each:
  `theorist.py` · `literature.py` · `falsifier.py` · `experimenter.py` · `methodologist.py`
  · `paper_builder.py` · `reviewer.py`. Verdicts/scores live here, in rules.
- `orchestrator.py` — `Doktores`, the controlled circle (Theorist→Falsifier↺→…→Reviewer; a
  fatal falsification or a `revise` jumps back to the Theorist with the open concern pinned).
- `io_kevin.py` — calls Kevin for candidates (optional dep; absent → empty).
- `io_joni.py` — reads occasions (decoupled handoff file preferred; best-effort **read-only**
  live Layer-9 read as fallback) and appends packages to Joni's `state/research_inbox.json`.
- `cli.py` / `__main__.py` — `python -m doktores …`.

## Conventions

- Ruff: `select = ["E","F","I","UP","B","SIM"]`, line length 100. src-layout, `pyproject.toml`.
- **Replay-stable ids** (`stable_id`, content hashes — no PRNG): a re-run produces the same
  package id, which is exactly what Joni's intake dedupes on. Keep runs deterministic under the
  MockLLM.
- `confidence` is a bounded **internal** number in [0,1], **not** a probability of truth — do
  not present it as one.
- The epistemic channel may only `add_claim` / `open_conflict`; a `reject` emits none. There is
  deliberately no "confirm" operation a package can carry.
- German terms in the design vocabulary (e.g. *Anlass*, the role names) are intentional; the
  code/comments are English to match Kevin/Joni.

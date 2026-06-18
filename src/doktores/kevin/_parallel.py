"""Parallel map for the I/O-bound language-layer calls.

A pure *execution* optimisation, nothing more. The language calls (write_variant,
read_signals, execute_step, critique) are independent network I/O, so they run
concurrently in a thread pool instead of one-after-another. Routing, scoring and
selection are untouched.

Replay-stability is preserved: ``ThreadPoolExecutor.map`` yields results in *input*
order (not completion order), and Kevin's ids are content hashes regardless of timing,
so a run produces the same candidates and the same run id whether calls are serial or
parallel. With the offline MockLLM the calls are instant and the pool is a thin wrapper.

Concurrency is bounded by ``DOKTORES_LLM_CONCURRENCY`` (default 8).
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from typing import TypeVar

_T = TypeVar("_T")
_R = TypeVar("_R")


def _workers() -> int:
    try:
        return max(1, int(os.getenv("DOKTORES_LLM_CONCURRENCY", "8")))
    except ValueError:
        return 8


def pmap(fn: Callable[[_T], _R], items: Iterable[_T]) -> list[_R]:
    """Apply ``fn`` to each item in parallel; return results in input order."""
    work = list(items)
    workers = _workers()
    if workers <= 1 or len(work) <= 1:
        return [fn(x) for x in work]
    with ThreadPoolExecutor(max_workers=min(workers, len(work))) as ex:
        return list(ex.map(fn, work))

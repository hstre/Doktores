"""Drift guard against Joni's real intake contract.

These run only where Joni is importable (it is an optional dependency). They verify that the
package keys Doktores emits are exactly the ones ``joni.autonomy.research_intake`` documents,
and that a produced package would enter Joni as a SOURCE - never confirmed.
"""

from __future__ import annotations

import pytest

from doktores import Doktores, ResearchTask
from doktores.models import RESEARCH_OUTPUT_KEYS

intake = pytest.importorskip("joni.autonomy.research_intake")


def test_keys_match_joni_schema():
    joni_keys = set(intake.RESEARCH_OUTPUT_SCHEMA.keys())
    assert set(RESEARCH_OUTPUT_KEYS) == joni_keys


def test_produced_package_carries_every_joni_key():
    pkg = Doktores().run(ResearchTask(conflict="x vs y under drift", topic="routing")).to_dict()
    for key in intake.RESEARCH_OUTPUT_SCHEMA:
        assert key in pkg


def test_research_origin_is_not_a_confirmed_authority():
    # The origin Joni stamps on these claims is "internal-research" - a SOURCE, not HUMAN and
    # not confirmed. This is the governance boundary, asserted from Joni's own constant.
    assert intake.RESEARCH_ORIGIN == "internal-research"

"""Doktores - an internally division-of-labour research organisation.

Doktores sits between **Joni** (memory / governance) and **Kevin** (idea production). It turns
Joni's Layer-9 conflicts and Kevin's candidates into worked research and hands the results back
as a structured ``research_output`` package - a SOURCE, never a belief.

Seven roles, deterministic orchestration, language-only LLM:

    Theorist -> Falsifier -> Literature Scout -> Experimental Designer
             -> Method Reviewer -> Paper Builder -> Adversarial Reviewer

The boundary that defines the system: **Doktores advises, it never decides.** It produces the
package; whether anything in it becomes a conviction is decided by Joni's governance alone. No
single model invents, checks, judges and confirms itself - that is exactly what the separated
roles prevent.

Public surface::

    from doktores import Doktores, ResearchTask
    pkg = Doktores().run(ResearchTask(conflict="...", topic="routing")).to_dict()
"""

from __future__ import annotations

from .llm_client import LLMClient, MockLLM, OpenAICompatibleLLM, get_default_client
from .models import (
    ClaimUpdate,
    EvidenceItem,
    Experiment,
    FalsificationReport,
    LiteratureFindings,
    MethodReview,
    Publication,
    PublicationKind,
    ResearchOutput,
    ResearchTask,
    ReviewerVerdict,
    Theory,
    Verdict,
    stable_id,
    validate_research_output,
)
from .orchestrator import Doktores, research

__all__ = [
    "Doktores",
    "research",
    "ResearchTask",
    "ResearchOutput",
    "Theory",
    "EvidenceItem",
    "Experiment",
    "ClaimUpdate",
    "Publication",
    "PublicationKind",
    "Verdict",
    "ReviewerVerdict",
    "FalsificationReport",
    "LiteratureFindings",
    "MethodReview",
    "validate_research_output",
    "stable_id",
    "LLMClient",
    "MockLLM",
    "OpenAICompatibleLLM",
    "get_default_client",
]

__version__ = "0.1.0"

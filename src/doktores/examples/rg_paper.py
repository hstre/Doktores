"""A compact slice of the Reality Gap (RG) working paper, as a PaperDraft fixture.

Used by the paper-improver demo and tests. The prose is condensed from the public RG
working paper (Rentschler, 2026); it is a *fixture*, not the full manuscript - enough to
exercise the controlled circle on a real argument.
"""

from __future__ import annotations

from ..paper import PaperDraft, Section


def rg_paper_draft() -> PaperDraft:
    return PaperDraft(
        title="Reality Gap (RG): A Heuristic Indicator for the Distance Between "
        "Market Valuation and Fundamental Coverage",
        topic="equity valuation / financial statement analysis",
        abstract=(
            "RG measures how far a firm's market capitalization stands from a conservatively "
            "constructed fundamental base of tangible equity plus capitalized ten-year smoothed "
            "positive earnings. It is a coverage diagnostic, not an intrinsic-value model."
        ),
        claims=(
            "RG = market cap / (tangible equity + N x ten-year smoothed positive earnings)",
            "negative long-run earnings are set to zero, not allowed to shrink the base",
            "RG is diagnostic, not normative: it measures distance, not truth",
        ),
        sections=(
            Section(
                heading="Definition of Reality Gap",
                text=(
                    "For company i at time t, RG is market capitalization divided by a "
                    "fundamental base. The fundamental base is tangible equity plus a "
                    "capitalized measure of long-run smoothed earnings, with the capitalization "
                    "factor N set to ten in the base specification. If ten-year average earnings "
                    "are non-positive the earnings term is set to zero, so only tangible capital "
                    "remains as coverage."
                ),
            ),
            Section(
                heading="Why Tangible Equity",
                text=(
                    "Book equity contains goodwill and capitalized intangibles whose reliability "
                    "depends on past acquisitions and assumptions. Tangible equity removes them, "
                    "giving a conservative substance floor. Counting goodwill fully would declare "
                    "old market enthusiasm the fundamental base for new market enthusiasm."
                ),
            ),
            Section(
                heading="Case Study: Tesla",
                text=(
                    "Tesla reported modest net income against a market capitalization in the "
                    "trillions, producing a very high RG. The valuation rests on optionality: "
                    "autonomous mobility, robotics, energy platforms. A high RG here is a "
                    "statement about narrative and expectation dominating conservatively "
                    "derivable coverage, not a prediction of decline."
                ),
            ),
            Section(
                heading="Limitations",
                text=(
                    "RG is not an intrinsic-value model and not a short-term trading signal. It "
                    "is weaker for banks, insurers, and intangible-heavy platforms, and depends "
                    "on accounting standards and history length. A high RG requires a second "
                    "level of interpretation: why is the distance high?"
                ),
            ),
        ),
    )

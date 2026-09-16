"""
Level 1 test: rerank_papers() as a pure function.

No ADK, no network, no LLM. Feeds hand-built PaperMetadata-shaped
dicts with deliberately varying relevance to a research question
and checks the resulting order/scores by hand.
"""

import sys

sys.stdout.reconfigure(encoding="utf-8")

from tools import rerank_papers


def make_paper(**overrides) -> dict:

    paper = {
        "paper_id": "paper_placeholder",
        "title": "Untitled",
        "authors": [],
        "abstract": None,
        "citation_count": None,
        "keywords": [],
    }

    paper.update(overrides)

    return paper


def main():

    research_question = (
        "How do multi-agent reinforcement learning systems "
        "coordinate communication between agents?"
    )

    # Strong match: research question terms appear in the title.
    paper_strong_title = make_paper(
        paper_id="paper_strong_title",
        title="Multi-Agent Reinforcement Learning Communication Coordination",
        abstract="A general discussion of unrelated topics.",
        citation_count=5,
    )

    # Medium match: terms appear only in the abstract/keywords.
    paper_medium_body = make_paper(
        paper_id="paper_medium_body",
        title="A Survey of Distributed Systems",
        abstract=(
            "This survey discusses reinforcement learning agents "
            "and communication strategies used for coordination."
        ),
        citation_count=100,
    )

    # No overlap at all with the research question.
    paper_no_match = make_paper(
        paper_id="paper_no_match",
        title="Photosynthesis in Alpine Plants",
        abstract="A botany paper about plant biology.",
        citation_count=9999,
    )

    # Two papers with identical relevance -> must tie-break by
    # citation_count, then by title.
    paper_tie_high_citations = make_paper(
        paper_id="paper_tie_high_citations",
        title="Agent Communication Coordination",
        abstract=None,
        citation_count=50,
    )

    paper_tie_low_citations = make_paper(
        paper_id="paper_tie_low_citations",
        title="Agent Communication Coordination",
        abstract=None,
        citation_count=10,
    )

    candidate_papers = [
        paper_no_match,
        paper_tie_low_citations,
        paper_medium_body,
        paper_tie_high_citations,
        paper_strong_title,
    ]

    result = rerank_papers(
        papers=candidate_papers,
        research_question=research_question,
    )

    print("Paper count:", result["paper_count"])
    print()

    for ranked in result["ranked_papers"]:
        print(
            "rank=", ranked["rank"], "|",
            "paper_id=", ranked["paper_id"], "|",
            "score=", ranked["relevance_score"], "|",
            "reason=", ranked["ranking_reason"],
        )

    # ----------------------------------------------------------
    # Assertions
    # ----------------------------------------------------------

    assert result["paper_count"] == 5

    rank_by_id = {
        r["paper_id"]: r["rank"] for r in result["ranked_papers"]
    }
    score_by_id = {
        r["paper_id"]: r["relevance_score"]
        for r in result["ranked_papers"]
    }

    # Title matches must outscore body-only matches.
    assert score_by_id["paper_strong_title"] > score_by_id["paper_medium_body"]

    # The unrelated paper must score exactly 0 and rank last,
    # regardless of its (very high) citation count.
    assert score_by_id["paper_no_match"] == 0.0
    assert rank_by_id["paper_no_match"] == 5

    # Tied relevance score must be broken by citation_count.
    assert (
        score_by_id["paper_tie_high_citations"]
        == score_by_id["paper_tie_low_citations"]
    )
    assert (
        rank_by_id["paper_tie_high_citations"]
        < rank_by_id["paper_tie_low_citations"]
    )

    # Every relevance_score must be a valid RankedPaper score.
    for ranked in result["ranked_papers"]:
        assert 0.0 <= ranked["relevance_score"] <= 1.0
        assert ranked["rank"] >= 1

    # Ranks must be a contiguous 1..N sequence with no gaps/repeats.
    assert sorted(rank_by_id.values()) == [1, 2, 3, 4, 5]

    print("\nALL ASSERTIONS PASSED")


if __name__ == "__main__":
    main()

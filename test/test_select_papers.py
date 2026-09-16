"""
Level 1 test: select_papers() as a pure function.

No ADK, no network, no LLM. Feeds hand-built RankedPaper-shaped
dicts (the shape rerank_papers() produces) and checks the
selection policy by hand: relevance threshold, max_papers cutoff,
both combined, and the "fewer candidates than max_papers" edge
case.
"""

import sys

sys.stdout.reconfigure(encoding="utf-8")

from tools import select_papers


def make_ranked_paper(**overrides) -> dict:
    """
    Minimal RankedPaper-shaped dict with sane defaults, so each
    test case only has to specify the fields it cares about.
    """

    paper = {
        "paper_id": "paper_placeholder",
        "rank": 1,
        "relevance_score": 0.0,
        "ranking_reason": None,
    }

    paper.update(overrides)

    return paper


def main():

    # ----------------------------------------------------------
    # Case 1: plain top-N cutoff. Five papers, no relevance floor,
    # max_papers=3 -> keep ranks 1-3, exclude 4-5 for budget only.
    # ----------------------------------------------------------

    five_papers = [
        make_ranked_paper(paper_id=f"paper_{rank}", rank=rank, relevance_score=0.9)
        for rank in range(1, 6)
    ]

    result_top_n = select_papers(
        ranked_papers=five_papers,
        max_papers=3,
        min_relevance_score=0.0,
    )

    print("Case 1 (top-N cutoff)")
    print("Selected:", result_top_n["selected_paper_ids"])
    print("Excluded:", result_top_n["excluded_papers"])
    print()

    assert result_top_n["selected_paper_ids"] == [
        "paper_1", "paper_2", "paper_3",
    ]
    assert result_top_n["candidate_count"] == 5
    assert result_top_n["selected_count"] == 3
    assert result_top_n["excluded_count"] == 2
    assert all(
        entry["reason"] == "max_papers_reached"
        for entry in result_top_n["excluded_papers"]
    )

    # ----------------------------------------------------------
    # Case 2: relevance threshold only (max_papers wide open).
    # Rank 2 and rank 4 fall below the floor and must be excluded
    # regardless of rank position.
    # ----------------------------------------------------------

    mixed_relevance_papers = [
        make_ranked_paper(paper_id="paper_a", rank=1, relevance_score=0.8),
        make_ranked_paper(paper_id="paper_b", rank=2, relevance_score=0.1),
        make_ranked_paper(paper_id="paper_c", rank=3, relevance_score=0.5),
        make_ranked_paper(paper_id="paper_d", rank=4, relevance_score=0.2),
        make_ranked_paper(paper_id="paper_e", rank=5, relevance_score=0.6),
    ]

    result_threshold = select_papers(
        ranked_papers=mixed_relevance_papers,
        max_papers=20,
        min_relevance_score=0.3,
    )

    print("Case 2 (relevance threshold only)")
    print("Selected:", result_threshold["selected_paper_ids"])
    print("Excluded:", result_threshold["excluded_papers"])
    print()

    assert result_threshold["selected_paper_ids"] == [
        "paper_a", "paper_c", "paper_e",
    ]

    excluded_by_id = {
        entry["paper_id"]: entry["reason"]
        for entry in result_threshold["excluded_papers"]
    }
    assert excluded_by_id == {
        "paper_b": "below_relevance_threshold",
        "paper_d": "below_relevance_threshold",
    }

    # ----------------------------------------------------------
    # Case 3: threshold AND max_papers combined. Threshold removes
    # paper_b and paper_d first; of the 3 survivors (a, c, e),
    # max_papers=2 keeps only the best-ranked two (a, c).
    # ----------------------------------------------------------

    result_combined = select_papers(
        ranked_papers=mixed_relevance_papers,
        max_papers=2,
        min_relevance_score=0.3,
    )

    print("Case 3 (threshold + max_papers combined)")
    print("Selected:", result_combined["selected_paper_ids"])
    print("Excluded:", result_combined["excluded_papers"])
    print()

    assert result_combined["selected_paper_ids"] == ["paper_a", "paper_c"]

    excluded_by_id = {
        entry["paper_id"]: entry["reason"]
        for entry in result_combined["excluded_papers"]
    }
    assert excluded_by_id == {
        "paper_b": "below_relevance_threshold",
        "paper_d": "below_relevance_threshold",
        "paper_e": "max_papers_reached",
    }

    # ----------------------------------------------------------
    # Case 4: fewer candidates than max_papers. Everything above
    # the floor must survive untouched.
    # ----------------------------------------------------------

    three_papers = [
        make_ranked_paper(paper_id="paper_x", rank=1, relevance_score=0.9),
        make_ranked_paper(paper_id="paper_y", rank=2, relevance_score=0.7),
        make_ranked_paper(paper_id="paper_z", rank=3, relevance_score=0.4),
    ]

    result_small = select_papers(
        ranked_papers=three_papers,
        max_papers=10,
        min_relevance_score=0.0,
    )

    print("Case 4 (fewer candidates than max_papers)")
    print("Selected:", result_small["selected_paper_ids"])
    print("Excluded:", result_small["excluded_papers"])
    print()

    assert result_small["selected_paper_ids"] == [
        "paper_x", "paper_y", "paper_z",
    ]
    assert result_small["excluded_count"] == 0

    # ----------------------------------------------------------
    # Case 5: input not pre-sorted by rank. Output must still be
    # ordered by rank, proving the function sorts internally
    # rather than trusting input order.
    # ----------------------------------------------------------

    unsorted_papers = [
        make_ranked_paper(paper_id="paper_third", rank=3, relevance_score=0.9),
        make_ranked_paper(paper_id="paper_first", rank=1, relevance_score=0.9),
        make_ranked_paper(paper_id="paper_second", rank=2, relevance_score=0.9),
    ]

    result_unsorted = select_papers(
        ranked_papers=unsorted_papers,
        max_papers=10,
        min_relevance_score=0.0,
    )

    print("Case 5 (unsorted input)")
    print("Selected:", result_unsorted["selected_paper_ids"])
    print()

    assert result_unsorted["selected_paper_ids"] == [
        "paper_first", "paper_second", "paper_third",
    ]

    print("ALL ASSERTIONS PASSED")


if __name__ == "__main__":
    main()

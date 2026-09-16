"""
Level 1 test: deduplicate_papers() as a pure function.

No ADK, no network, no LLM. Feeds hand-built PaperMetadata-shaped
dicts covering every match path and checks the result by hand.
"""

import sys

sys.stdout.reconfigure(encoding="utf-8")

from tools import deduplicate_papers


def make_paper(**overrides) -> dict:
    """
    Minimal PaperMetadata-shaped dict with sane defaults, so each
    test case only has to specify the fields it cares about.
    """

    paper = {
        "paper_id": "paper_placeholder",
        "title": "Untitled",
        "authors": [],
        "abstract": None,
        "publication_year": None,
        "publication_date": None,
        "doi": None,
        "arxiv_id": None,
        "venue": None,
        "source": "arxiv",
        "source_id": None,
        "landing_url": None,
        "pdf_url": None,
        "citation_count": None,
        "keywords": [],
    }

    paper.update(overrides)

    return paper


def main():

    # ----------------------------------------------------------
    # Group 1: same paper found on arXiv, OpenAlex, and Crossref.
    #
    # - paper_a (arXiv): has arxiv_id, no DOI, has a pdf_url.
    # - paper_b (OpenAlex): different arxiv_id VERSION + a DOI +
    #   venue + citation_count. Should merge into paper_a via the
    #   arXiv match (same base ID, different version suffix).
    # - paper_c (Crossref): only has the DOI (matches paper_b's
    #   DOI, which was registered onto the group during the
    #   paper_b merge).
    # ----------------------------------------------------------

    paper_a = make_paper(
        paper_id="paper_a_arxiv",
        title="Deep Learning for Multi-Agent Systems",
        source="arxiv",
        arxiv_id="2203.08975v1",
        pdf_url="https://arxiv.org/pdf/2203.08975v1",
        keywords=["cs.MA"],
    )

    paper_b = make_paper(
        paper_id="paper_b_openalex",
        title="Deep Learning for Multi-Agent Systems",
        source="openalex",
        arxiv_id="2203.08975v2",
        doi="10.1000/xyz123",
        venue="NeurIPS",
        citation_count=42,
        keywords=["cs.LG"],
    )

    paper_c = make_paper(
        paper_id="paper_c_crossref",
        title="Deep Learning for Multi-Agent Systems",
        source="crossref",
        doi="10.1000/XYZ123",  # same DOI, different case
    )

    # ----------------------------------------------------------
    # Group 2: duplicate detectable only by normalized title
    # (no DOI, no arXiv ID on either record).
    # ----------------------------------------------------------

    paper_d1 = make_paper(
        paper_id="paper_d1",
        title="Foundations of Distributed AI",
        source="crossref",
    )

    paper_d2 = make_paper(
        paper_id="paper_d2",
        title="Foundations of Distributed AI.",  # trailing period
        source="openalex",
        venue="AAMAS",
    )

    # ----------------------------------------------------------
    # Group 3: a genuinely unique paper. Must remain standalone.
    # ----------------------------------------------------------

    paper_unique = make_paper(
        paper_id="paper_unique",
        title="Emergent Behavior in Robotic Swarms",
        source="crossref",
    )

    candidate_papers = [
        paper_a,
        paper_b,
        paper_c,
        paper_d1,
        paper_d2,
        paper_unique,
    ]

    result = deduplicate_papers(candidate_papers)

    print("Original count:", result["original_count"])
    print("Deduplicated count:", result["deduplicated_count"])
    print("Duplicates removed:", result["duplicates_removed"])

    print("\nKEPT PAPERS")
    for paper in result["papers"]:
        print(
            paper["paper_id"], "|",
            paper["title"], "|",
            "doi=", paper["doi"], "|",
            "venue=", paper["venue"], "|",
            "citation_count=", paper["citation_count"], "|",
            "pdf_url=", paper["pdf_url"], "|",
            "keywords=", paper["keywords"],
        )

    print("\nDUPLICATE GROUPS")
    for group in result["duplicate_groups"]:
        print(group)

    # ----------------------------------------------------------
    # Assertions
    # ----------------------------------------------------------

    assert result["original_count"] == 6
    assert result["deduplicated_count"] == 3, (
        "Expected 3 surviving papers (group 1, group 2, unique)."
    )
    assert result["duplicates_removed"] == 3

    kept_by_id = {p["paper_id"]: p for p in result["papers"]}

    # Group 1 should have been kept under paper_a's ID, enriched
    # with paper_b's DOI/venue/citation_count, while keeping
    # paper_a's own pdf_url (never overwritten).
    assert "paper_a_arxiv" in kept_by_id
    merged = kept_by_id["paper_a_arxiv"]
    assert merged["doi"] == "10.1000/xyz123"
    assert merged["venue"] == "NeurIPS"
    assert merged["citation_count"] == 42
    assert merged["pdf_url"] == "https://arxiv.org/pdf/2203.08975v1"
    assert set(merged["keywords"]) == {"cs.MA", "cs.LG"}

    # Group 2 should have been kept under paper_d1's ID, enriched
    # with paper_d2's venue.
    assert "paper_d1" in kept_by_id
    assert kept_by_id["paper_d1"]["venue"] == "AAMAS"

    # The unique paper must survive untouched.
    assert "paper_unique" in kept_by_id

    # Duplicates must not appear as standalone kept records.
    assert "paper_b_openalex" not in kept_by_id
    assert "paper_c_crossref" not in kept_by_id
    assert "paper_d2" not in kept_by_id

    # Duplicate group bookkeeping should list exactly which
    # paper_ids were merged into which kept record.
    groups_by_kept_id = {
        group["kept_paper_id"]: group
        
        for group in result["duplicate_groups"]
    }

    assert len(groups_by_kept_id) == 2

    removed_ids_group1 = {
        entry["paper_id"]
        for entry in groups_by_kept_id["paper_a_arxiv"]["removed"]
    }
    assert removed_ids_group1 == {"paper_b_openalex", "paper_c_crossref"}

    removed_ids_group2 = {
        entry["paper_id"]
        for entry in groups_by_kept_id["paper_d1"]["removed"]
    }
    assert removed_ids_group2 == {"paper_d2"}

    print("\nALL ASSERTIONS PASSED")


if __name__ == "__main__":
    main()

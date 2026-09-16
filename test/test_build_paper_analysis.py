"""
Level 1 test: build_paper_analysis() as a pure function.

No ADK, no network, no LLM. Feeds hand-built page_analyses (the shape
analyze_pages_with_vlm() produces) plus hand-built synthesis fields
(the shape the Analysis Agent's own reasoning would produce) and
checks the assembly/validation by hand.
"""

import sys

sys.stdout.reconfigure(encoding="utf-8")

from schemas import PaperAnalysis
from tools import build_paper_analysis


def make_page_analysis(page_number: int, **overrides) -> dict:
    page = {
        "paper_id": "paper_placeholder",
        "page_number": page_number,
        "image_path": f"data/paper_placeholder/pages/page_{page_number:04d}.png",
        "summary": f"Summary of page {page_number}.",
        "relevant_content": [],
        "methods": [],
        "datasets": [],
        "findings": [],
        "tables_observed": [],
        "figures_observed": [],
        "equations_observed": [],
        "limitations": [],
        "metrics_observed": {},
        "future_work_mentions": [],
    }
    page.update(overrides)
    return page


def main():

    # ----------------------------------------------------------
    # Case 1: a complete, valid synthesis over 2 pages.
    # ----------------------------------------------------------

    page_analyses = [
        make_page_analysis(1, summary="Title page and introduction."),
        make_page_analysis(
            2,
            summary="Methodology section.",
            methods=["Transformer-based encoder"],
            datasets=["CIFAR-10"],
        ),
    ]

    result = build_paper_analysis(
        paper_id="paper_placeholder",
        page_analyses=page_analyses,
        research_objective="Improve few-shot image classification.",
        methodology="Transformer-based encoder pretrained on CIFAR-10.",
        datasets=["CIFAR-10"],
        experimental_setup="5-way 1-shot classification benchmark.",
        metrics={"accuracy": "91.2%"},
        key_findings=["Outperforms baseline by 4 points."],
        contributions=["A new pretraining objective."],
        limitations=["Only evaluated on CIFAR-10."],
        future_work=["Evaluate on larger benchmarks."],
    )

    print("Case 1 (valid synthesis)")
    print(result)
    print()

    assert result["success"] is True
    assert result["error"] is None

    validated = PaperAnalysis.model_validate(result["paper_analysis"])
    assert validated.paper_id == "paper_placeholder"
    assert validated.research_objective == "Improve few-shot image classification."
    assert validated.datasets == ["CIFAR-10"]
    assert validated.metrics == {"accuracy": "91.2%"}
    assert len(validated.page_analyses) == 2
    assert validated.page_analyses[0].page_number == 1
    assert validated.page_analyses[1].page_number == 2
    assert validated.evidence == []

    # ----------------------------------------------------------
    # Case 2: minimal input - only paper_id and page_analyses, no
    # synthesis fields supplied at all. Every optional field should
    # fall back to its empty default, never be fabricated.
    # ----------------------------------------------------------

    minimal_result = build_paper_analysis(
        paper_id="paper_minimal",
        page_analyses=[make_page_analysis(1, paper_id="paper_minimal")],
    )

    print("Case 2 (minimal input)")
    print(minimal_result)
    print()

    assert minimal_result["success"] is True
    minimal_validated = PaperAnalysis.model_validate(
        minimal_result["paper_analysis"]
    )
    assert minimal_validated.research_objective is None
    assert minimal_validated.methodology is None
    assert minimal_validated.datasets == []
    assert minimal_validated.metrics == {}
    assert minimal_validated.key_findings == []
    assert len(minimal_validated.page_analyses) == 1

    # ----------------------------------------------------------
    # Case 3: invalid data - metrics is supposed to be a
    # dict[str, str], give it a list instead. Must be reported as a
    # structured failure, not coerced or silently dropped.
    # ----------------------------------------------------------

    invalid_result = build_paper_analysis(
        paper_id="paper_invalid",
        page_analyses=[make_page_analysis(1, paper_id="paper_invalid")],
        metrics=["accuracy: 91.2%"],  # wrong type on purpose
    )

    print("Case 3 (invalid metrics type)")
    print(invalid_result)
    print()

    assert invalid_result["success"] is False
    assert invalid_result["paper_analysis"] is None
    assert invalid_result["error"]

    # ----------------------------------------------------------
    # Case 4: invalid data - a page_analyses entry missing its
    # required "summary" field.
    # ----------------------------------------------------------

    broken_page = make_page_analysis(1, paper_id="paper_invalid")
    del broken_page["summary"]

    invalid_page_result = build_paper_analysis(
        paper_id="paper_invalid",
        page_analyses=[broken_page],
    )

    print("Case 4 (invalid page_analyses entry)")
    print(invalid_page_result)
    print()

    assert invalid_page_result["success"] is False
    assert invalid_page_result["paper_analysis"] is None
    assert invalid_page_result["error"]

    print("ALL ASSERTIONS PASSED")


if __name__ == "__main__":
    main()

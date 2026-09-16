"""
Level 2 test: analyze_pages_with_vlm() against a real PDF and a real
vision-language model call.

Not a pure function - it reads real page images from disk, makes a
real NVIDIA NIM (kimi-k3) VLM call, and inspects the actual response
by hand, the same way search_arxiv/download_pdf/render_pdf_pages
were tested.

Cases covered:
    1. A real, small multi-page PDF, first 2 rendered pages (one
       batch, since VLM_PAGES_PER_CALL=4) -> one valid PageAnalysis
       per page, correctly mapped to its page number/image_path.
    2. A page image path that does not exist -> reported as a
       structured failed_pages entry, no exception raised, no
       fabricated PageAnalysis.
"""

import asyncio
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

from schemas import PageAnalysis
from tools import download_pdf, render_pdf_pages, analyze_pages_with_vlm


async def main():

    # ----------------------------------------------------------
    # Case 1: analyze the first 2 pages of a real, freshly
    # downloaded and rendered PDF.
    # ----------------------------------------------------------

    download_result = await download_pdf(
        pdf_url="https://arxiv.org/pdf/2203.08975v1",
        paper_id="test_vlm_paper",
    )
    assert download_result["retrieval_status"] == "downloaded"

    render_result = render_pdf_pages(pdf_path=download_result["pdf_path"])
    assert render_result["success"] is True

    pages_to_analyze = render_result["page_image_paths"][:2]

    result = await analyze_pages_with_vlm(
        paper_id="test_vlm_paper",
        page_image_paths=pages_to_analyze,
    )

    print("Case 1 (real 2-page batch)")
    print("requested_page_count:", result["requested_page_count"])
    print("analyzed_page_count:", result["analyzed_page_count"])
    print("failed_pages:", result["failed_pages"])
    for page_analysis in result["page_analyses"]:
        print("-", page_analysis["page_number"], "->", page_analysis["summary"])
        print("  metrics_observed:", page_analysis["metrics_observed"])
        print("  future_work_mentions:", page_analysis["future_work_mentions"])
    print()

    assert result["requested_page_count"] == 2
    assert result["failed_pages"] == []
    assert result["analyzed_page_count"] == 2
    assert result["success"] is True
    assert len(result["page_analyses"]) == 2

    for index, page_analysis in enumerate(result["page_analyses"]):
        # Re-validate against the real schema, not just trust the dict.
        validated = PageAnalysis.model_validate(page_analysis)
        assert validated.paper_id == "test_vlm_paper"
        assert validated.page_number == index + 1
        assert validated.image_path == pages_to_analyze[index]
        assert validated.summary.strip() != ""

    # ----------------------------------------------------------
    # Clean up every artifact this test created.
    # ----------------------------------------------------------

    for image_path in render_result["page_image_paths"]:
        os.remove(image_path)
    os.rmdir(render_result["pages_dir"])
    os.remove(download_result["pdf_path"])
    os.rmdir(os.path.dirname(download_result["pdf_path"]))

    # ----------------------------------------------------------
    # Case 2: nonexistent page image path.
    # ----------------------------------------------------------

    missing_result = await analyze_pages_with_vlm(
        paper_id="test_vlm_paper",
        page_image_paths=["data/test_vlm_paper/pages/page_9999.png"],
    )

    print("Case 2 (missing image)")
    print(missing_result)
    print()

    assert missing_result["requested_page_count"] == 1
    assert missing_result["analyzed_page_count"] == 0
    assert missing_result["page_analyses"] == []
    assert len(missing_result["failed_pages"]) == 1
    assert missing_result["success"] is False

    print("ALL ASSERTIONS PASSED")


if __name__ == "__main__":
    asyncio.run(main())

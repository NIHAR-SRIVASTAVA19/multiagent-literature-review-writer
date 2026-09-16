"""
Level 2 test: download_pdf() against real network conditions.

Unlike deduplicate_papers/rerank_papers/select_papers, download_pdf
is not a pure function - it performs a real HTTP download and a
real filesystem write, so it is tested the same way the other
external-tool functions (search_arxiv, search_openalex, ...) were:
live, one case at a time, output inspected by hand.

Cases covered:
    1. A real, small, stable arXiv PDF -> successful download.
    2. paper_id=None pdf_url -> reported as a failed retrieval,
       no network call made.
    3. A URL that returns 404 -> reported as a failed retrieval,
       no file written.
"""

import asyncio
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

from tools import download_pdf
from config import PAPERS_DIR


async def main():

    # ----------------------------------------------------------
    # Case 1: real successful download.
    # ----------------------------------------------------------

    result_ok = await download_pdf(
        pdf_url="https://arxiv.org/pdf/2203.08975v1",
        paper_id="test_paper_success",
    )

    print("Case 1 (real PDF)")
    print(result_ok)
    print()

    assert result_ok["retrieval_status"] == "downloaded"
    assert result_ok["retrieval_error"] is None
    assert result_ok["pdf_path"] is not None
    assert os.path.isfile(result_ok["pdf_path"])

    with open(result_ok["pdf_path"], "rb") as pdf_file:
        header = pdf_file.read(4)
    assert header == b"%PDF"

    expected_path = os.path.join(
        PAPERS_DIR, "test_paper_success", "test_paper_success.pdf"
    )
    assert os.path.abspath(result_ok["pdf_path"]) == os.path.abspath(
        expected_path
    )

    # Clean up the whole per-paper folder this test created.
    paper_dir = os.path.dirname(result_ok["pdf_path"])
    os.remove(result_ok["pdf_path"])
    os.rmdir(paper_dir)

    # ----------------------------------------------------------
    # Case 2: no pdf_url available.
    # ----------------------------------------------------------

    result_missing_url = await download_pdf(
        pdf_url=None,
        paper_id="test_paper_no_url",
    )

    print("Case 2 (missing pdf_url)")
    print(result_missing_url)
    print()

    assert result_missing_url["retrieval_status"] == "failed"
    assert result_missing_url["pdf_path"] is None
    assert result_missing_url["retrieval_error"]

    # ----------------------------------------------------------
    # Case 3: URL that resolves but 404s.
    # ----------------------------------------------------------

    result_404 = await download_pdf(
        pdf_url="https://arxiv.org/pdf/0000.00000v99",
        paper_id="test_paper_404",
    )

    print("Case 3 (404 URL)")
    print(result_404)
    print()

    assert result_404["retrieval_status"] == "failed"
    assert result_404["pdf_path"] is None
    assert result_404["retrieval_error"]

    not_written_path = os.path.join(
        PAPERS_DIR, "test_paper_404", "test_paper_404.pdf"
    )
    assert not os.path.isfile(not_written_path)
    assert not os.path.isdir(os.path.dirname(not_written_path))

    print("ALL ASSERTIONS PASSED")


if __name__ == "__main__":
    asyncio.run(main())

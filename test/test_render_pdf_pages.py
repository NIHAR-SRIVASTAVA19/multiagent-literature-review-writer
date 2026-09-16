"""
Level 2 test: render_pdf_pages() against a real PDF.

Not a pure function - it reads a real file from disk with PyMuPDF
and writes real image files - so it is exercised the same way
download_pdf was: download a real, small, stable arXiv PDF first
(reusing download_pdf, already tested independently), then render
it, and inspect the output by hand.

Cases covered:
    1. A real multi-page PDF -> one PNG per page, correctly named
       and nested under <paper folder>/pages/, each a valid image.
    2. A path that does not exist -> reported as a clean failure,
       no directory created.
"""

import asyncio
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

import pymupdf

from tools import download_pdf, render_pdf_pages


async def main():

    # ----------------------------------------------------------
    # Case 1: render a real, freshly downloaded PDF.
    # ----------------------------------------------------------

    download_result = await download_pdf(
        pdf_url="https://arxiv.org/pdf/2203.08975v1",
        paper_id="test_render_paper",
    )

    assert download_result["retrieval_status"] == "downloaded"
    pdf_path = download_result["pdf_path"]

    # Ground truth for the expected page count, independent of
    # render_pdf_pages's own logic.
    with pymupdf.open(pdf_path) as reference_document:
        expected_page_count = reference_document.page_count

    result = render_pdf_pages(pdf_path=pdf_path)

    print("Case 1 (real PDF)")
    print("pages_dir:", result["pages_dir"])
    print("page_count:", result["page_count"])
    print("first path:", result["page_image_paths"][0])
    print()

    assert result["success"] is True
    assert result["error"] is None
    assert result["page_count"] == expected_page_count
    assert len(result["page_image_paths"]) == expected_page_count

    expected_pages_dir = os.path.join(
        os.path.dirname(pdf_path), "pages"
    )
    assert os.path.abspath(result["pages_dir"]) == os.path.abspath(
        expected_pages_dir
    )

    # Every path must exist, sit inside pages_dir, follow the
    # zero-padded naming convention, and be a real, openable image.
    for index, image_path in enumerate(result["page_image_paths"]):

        assert os.path.isfile(image_path)

        expected_name = f"page_{index + 1:04d}.png"
        assert os.path.basename(image_path) == expected_name

        with open(image_path, "rb") as image_file:
            header = image_file.read(8)
        assert header.startswith(b"\x89PNG"), (
            "Rendered page is not a valid PNG."
        )

    # ----------------------------------------------------------
    # Clean up every artifact this test created (PDF + pages +
    # the per-paper folder itself).
    # ----------------------------------------------------------

    for image_path in result["page_image_paths"]:
        os.remove(image_path)
    os.rmdir(result["pages_dir"])
    os.remove(pdf_path)
    os.rmdir(os.path.dirname(pdf_path))

    # ----------------------------------------------------------
    # Case 2: nonexistent PDF path.
    # ----------------------------------------------------------

    missing_result = render_pdf_pages(
        pdf_path="data/does_not_exist/does_not_exist.pdf"
    )

    print("Case 2 (missing PDF)")
    print(missing_result)
    print()

    assert missing_result["success"] is False
    assert missing_result["page_count"] == 0
    assert missing_result["page_image_paths"] == []
    assert missing_result["error"]
    assert not os.path.isdir("data/does_not_exist")

    print("ALL ASSERTIONS PASSED")


if __name__ == "__main__":
    asyncio.run(main())

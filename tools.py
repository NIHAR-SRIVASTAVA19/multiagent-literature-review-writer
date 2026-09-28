"""
Centralized tool definitions for the Multi-Agent Literature Review System.

NOTE:
These functions are currently placeholders.
Actual API integrations and processing logic will be implemented
after the agent architecture has been defined.
"""
import asyncio
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
import pymupdf
import httpx
import litellm
from bs4 import BeautifulSoup

from config import (
    ARXIV_API_URL,
    SEMANTIC_SCHOLAR_API_URL,
    OPENALEX_API_URL,
    OPENALEX_MAILTO,
    CROSSREF_API_URL,
    CROSSREF_MAILTO,
    TAVILY_API_URL,
    TAVILY_API_KEY,
    PAPERS_DIR,
    MAX_PDF_DOWNLOAD_BYTES,
    ANALYSIS_MODEL_NAME,
    VLM_MODEL_NAME,
    NVIDIA_NIM_API_KEY,
    NVIDIA_NIM_API_BASE,
    TABLE_CROP_DPI,
    MARKER_TIMEOUT_SECONDS,
    VLM_CONCURRENCY,
    VLM_REQUEST_TIMEOUT_SECONDS,
)

from prompts import (
    PAPER_LEVEL_ANALYSIS_PROMPT,
    IMAGE_DESCRIPTION_PROMPT,
)

from schemas import (
    AcademicSource,
    PaperMetadata,
    RankedPaper,
    RetrievalStatus,
    WebSource,
    PageAnalysis,
    PaperAnalysis,
    Synthesis,
    LiteratureReviewDraft,
    ContentReviewResult,
    CitationReviewResult,
)

# ============================================================
# SEARCH COORDINATOR TOOLS
# ============================================================




async def search_arxiv(
    query: str,
    max_results: int = 10,
) -> dict:
    """
    Search arXiv for candidate research papers.

    The function executes a provided search query only.
    It does not generate queries, deduplicate results,
    rank papers, or select papers.

    Args:
        query:
            Search query provided by the Root Agent.

        max_results:
            Maximum number of papers to retrieve.

    Returns:
        JSON-compatible dictionary containing normalized
        candidate paper metadata.
    """

    max_results = max(1, min(max_results, 50))

    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": max_results,
        "sortBy": "relevance",
        "sortOrder": "descending",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                ARXIV_API_URL,
                params=params,
            )

            if response.status_code == 429:
                return {
                    "success": False,
                    "source": AcademicSource.ARXIV.value,
                    "query": query,
                    "count": 0,
                    "papers": [],
                    "error": "arXiv rate limit exceeded.",
                }

            if response.status_code == 503:
                return {
                    "success": False,
                    "source": AcademicSource.ARXIV.value,
                    "query": query,
                    "count": 0,
                    "papers": [],
                    "error": "arXiv temporarily unavailable (503).",
                }

            response.raise_for_status()

    except httpx.HTTPError as exc:
        return {
            "success": False,
            "source": AcademicSource.ARXIV.value,
            "query": query,
            "count": 0,
            "papers": [],
            "error": str(exc) or f"{type(exc).__name__} with no message.",
        }

    try:
        root = ET.fromstring(response.text)

    except ET.ParseError as exc:
        return {
            "success": False,
            "source": AcademicSource.ARXIV.value,
            "query": query,
            "count": 0,
            "papers": [],
            "error": f"Failed to parse arXiv response: {exc}",
        }

    namespaces = {
        "atom": "http://www.w3.org/2005/Atom",
        "arxiv": "http://arxiv.org/schemas/atom",
    }

    papers = []

    for entry in root.findall("atom:entry", namespaces):

        # ----------------------------------------------------
        # arXiv ID
        # ----------------------------------------------------

        entry_id = entry.findtext(
            "atom:id",
            default="",
            namespaces=namespaces,
        )

        arxiv_id = (
            entry_id.rstrip("/")
            .split("/")[-1]
            if entry_id
            else None
        )

        # ----------------------------------------------------
        # Title
        # ----------------------------------------------------

        title = entry.findtext(
            "atom:title",
            default="",
            namespaces=namespaces,
        )

        title = " ".join(title.split())

        # ----------------------------------------------------
        # Abstract
        # ----------------------------------------------------

        abstract = entry.findtext(
            "atom:summary",
            default="",
            namespaces=namespaces,
        )

        abstract = " ".join(abstract.split()) or None

        # ----------------------------------------------------
        # Authors
        # ----------------------------------------------------

        authors = []

        for author in entry.findall(
            "atom:author",
            namespaces,
        ):
            name = author.findtext(
                "atom:name",
                default="",
                namespaces=namespaces,
            )

            if name:
                authors.append(name.strip())

        # ----------------------------------------------------
        # Publication date
        # ----------------------------------------------------

        published = entry.findtext(
            "atom:published",
            default="",
            namespaces=namespaces,
        )

        publication_year = None

        if published:
            try:
                publication_year = int(published[:4])
            except ValueError:
                pass

        # ----------------------------------------------------
        # DOI
        # ----------------------------------------------------

        doi = entry.findtext(
            "arxiv:doi",
            default=None,
            namespaces=namespaces,
        )

        if doi:
            doi = doi.strip()

        # ----------------------------------------------------
        # Venue
        # ----------------------------------------------------

        venue = entry.findtext(
            "arxiv:journal_ref",
            default=None,
            namespaces=namespaces,
        )

        if venue:
            venue = " ".join(venue.split())

        # ----------------------------------------------------
        # Categories / keywords
        # ----------------------------------------------------

        keywords = []

        for category in entry.findall(
            "atom:category",
            namespaces,
        ):
            term = category.attrib.get("term")

            if term:
                keywords.append(term)

        # ----------------------------------------------------
        # URLs
        # ----------------------------------------------------

        landing_url = entry_id or None
        pdf_url = None

        for link in entry.findall(
            "atom:link",
            namespaces,
        ):
            if link.attrib.get("title") == "pdf":
                pdf_url = link.attrib.get("href")
                break

        # ----------------------------------------------------
        # Stable internal ID
        # ----------------------------------------------------

        identity = arxiv_id or doi or title

        paper_id = "paper_" + hashlib.sha256(
            identity.encode("utf-8")
        ).hexdigest()[:16]

        # ----------------------------------------------------
        # Normalize into canonical schema
        # ----------------------------------------------------

        paper = PaperMetadata(
            paper_id=paper_id,
            title=title,
            authors=authors,
            abstract=abstract,
            publication_year=publication_year,
            publication_date=published or None,
            doi=doi,
            arxiv_id=arxiv_id,
            venue=venue,
            source=AcademicSource.ARXIV,
            source_id=arxiv_id,
            landing_url=landing_url,
            pdf_url=pdf_url,
            citation_count=None,
            keywords=keywords,
        )

        papers.append(
            paper.model_dump(mode="json")
        )

    return {
        "success": True,
        "source": AcademicSource.ARXIV.value,
        "query": query,
        "count": len(papers),
        "papers": papers,
        "error": None,
    }


async def search_semantic_scholar(
    query: str,
    max_results: int = 10,
) -> dict:
    """
    Search Semantic Scholar for candidate research papers.

    This function only executes the provided search query.
    It does not generate queries, deduplicate papers,
    rank papers, or select papers.

    Args:
        query:
            Search query provided by the Root Agent.

        max_results:
            Maximum number of results to retrieve.

    Returns:
        JSON-compatible dictionary containing normalized
        PaperMetadata objects.
    """

    max_results = max(1, min(max_results, 100))

    fields = ",".join([
        "paperId",
        "title",
        "authors",
        "abstract",
        "year",
        "publicationDate",
        "venue",
        "citationCount",
        "externalIds",
        "url",
        "openAccessPdf",
        "fieldsOfStudy",
    ])

    params = {
        "query": query,
        "limit": max_results,
        "fields": fields,
    }



    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                SEMANTIC_SCHOLAR_API_URL,
                params=params,
            )

            if response.status_code == 429:
                return {
                    "success": False,
                    "source": AcademicSource.SEMANTIC_SCHOLAR.value,
                    "query": query,
                    "count": 0,
                    "papers": [],
                    "error": "Semantic Scholar rate limit exceeded.",
                }

            response.raise_for_status()

    except httpx.HTTPError as exc:
        return {
            "success": False,
            "source": AcademicSource.SEMANTIC_SCHOLAR.value,
            "query": query,
            "count": 0,
            "papers": [],
            "error": str(exc) or f"{type(exc).__name__} with no message.",
        }

    try:
        payload = response.json()

    except ValueError as exc:
        return {
            "success": False,
            "source": AcademicSource.SEMANTIC_SCHOLAR.value,
            "query": query,
            "count": 0,
            "papers": [],
            "error": f"Failed to parse Semantic Scholar response: {exc}",
        }

    papers = []

    for item in payload.get("data", []):

        semantic_scholar_id = item.get("paperId")

        title = (item.get("title") or "").strip()

        if not title:
            continue

        # ----------------------------------------------------
        # Authors
        # ----------------------------------------------------

        authors = [
            author.get("name", "").strip()
            for author in item.get("authors", [])
            if author.get("name")
        ]

        # ----------------------------------------------------
        # External identifiers
        # ----------------------------------------------------

        external_ids = item.get("externalIds") or {}

        doi = external_ids.get("DOI")
        arxiv_id = external_ids.get("ArXiv")

        # ----------------------------------------------------
        # PDF URL
        # ----------------------------------------------------

        open_access_pdf = item.get("openAccessPdf") or {}

        pdf_url = open_access_pdf.get("url")

        # ----------------------------------------------------
        # Keywords / fields of study
        # ----------------------------------------------------

        keywords = item.get("fieldsOfStudy") or []

        # ----------------------------------------------------
        # Stable internal ID
        # ----------------------------------------------------

        identity = (
            doi
            or arxiv_id
            or semantic_scholar_id
            or title
        )

        paper_id = "paper_" + hashlib.sha256(
            identity.lower().encode("utf-8")
        ).hexdigest()[:16]

        # ----------------------------------------------------
        # Normalize into canonical schema
        # ----------------------------------------------------

        paper = PaperMetadata(
            paper_id=paper_id,
            title=title,
            authors=authors,
            abstract=item.get("abstract"),
            publication_year=item.get("year"),
            publication_date=item.get("publicationDate"),
            doi=doi,
            arxiv_id=arxiv_id,
            venue=item.get("venue"),
            source=AcademicSource.SEMANTIC_SCHOLAR,
            source_id=semantic_scholar_id,
            landing_url=item.get("url"),
            pdf_url=pdf_url,
            citation_count=item.get("citationCount"),
            keywords=keywords,
        )

        papers.append(
            paper.model_dump(mode="json")
        )

    return {
        "success": True,
        "source": AcademicSource.SEMANTIC_SCHOLAR.value,
        "query": query,
        "count": len(papers),
        "papers": papers,
        "error": None,
    }


def reconstruct_openalex_abstract(
    inverted_index: dict | None,
) -> str | None:
    """
    Reconstruct normal abstract text from OpenAlex's
    abstract_inverted_index representation.
    """

    if not inverted_index:
        return None

    positions = []

    for word, indexes in inverted_index.items():
        for index in indexes:
            positions.append(
                (index, word)
            )

    positions.sort(
        key=lambda item: item[0]
    )

    return " ".join(
        word
        for _, word in positions
    )

async def search_openalex(
    query: str,
    max_results: int = 10,
) -> dict:
    """
    Search OpenAlex for candidate research papers.

    This function only executes the provided search query.
    It does not generate queries, deduplicate papers,
    rank papers, or select papers.
    """

    max_results = max(1, min(max_results, 100))

    params = {
        "search": query,
        "per-page": max_results,
    }

    if OPENALEX_MAILTO:
        params["mailto"] = OPENALEX_MAILTO

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                OPENALEX_API_URL,
                params=params,
            )

            if response.status_code == 429:
                return {
                    "success": False,
                    "source": AcademicSource.OPENALEX.value,
                    "query": query,
                    "count": 0,
                    "papers": [],
                    "error": "OpenAlex rate limit exceeded.",
                }

            response.raise_for_status()

    except httpx.HTTPError as exc:
        return {
            "success": False,
            "source": AcademicSource.OPENALEX.value,
            "query": query,
            "count": 0,
            "papers": [],
            "error": str(exc) or f"{type(exc).__name__} with no message.",
        }

    try:
        payload = response.json()

    except ValueError as exc:
        return {
            "success": False,
            "source": AcademicSource.OPENALEX.value,
            "query": query,
            "count": 0,
            "papers": [],
            "error": f"Failed to parse OpenAlex response: {exc}",
        }

    papers = []

    for item in payload.get("results", []):

        title = (item.get("title") or "").strip()

        if not title:
            continue

        # ----------------------------------------------------
        # OpenAlex source ID
        # ----------------------------------------------------

        openalex_id = item.get("id")

        if openalex_id:
            source_id = openalex_id.rstrip("/").split("/")[-1]
        else:
            source_id = None

        # ----------------------------------------------------
        # Authors
        # ----------------------------------------------------

        authors = []

        for authorship in item.get("authorships", []):
            author = authorship.get("author") or {}
            name = author.get("display_name")

            if name:
                authors.append(name.strip())

        # ----------------------------------------------------
        # DOI
        # ----------------------------------------------------

        doi = item.get("doi")

        if doi:
            doi = doi.replace(
                "https://doi.org/",
                ""
            ).strip()

        # ----------------------------------------------------
        # arXiv ID
        # ----------------------------------------------------

        arxiv_id = None

        ids = item.get("ids") or {}

        arxiv_url = ids.get("arxiv")

        if arxiv_url:
            arxiv_id = (
                arxiv_url.rstrip("/")
                .split("/")[-1]
            )

        # ----------------------------------------------------
        # Venue
        # ----------------------------------------------------

        venue = None

        primary_location = (
            item.get("primary_location") or {}
        )

        source = (
            primary_location.get("source") or {}
        )

        venue = source.get("display_name")

        # ----------------------------------------------------
        # Landing URL
        # ----------------------------------------------------

        landing_url = primary_location.get(
            "landing_page_url"
        )

        if not landing_url:
            landing_url = openalex_id

        # ----------------------------------------------------
        # PDF URL
        # ----------------------------------------------------

        pdf_url = primary_location.get("pdf_url")

        if not pdf_url:

            best_oa_location = (
                item.get("best_oa_location") or {}
            )

            pdf_url = best_oa_location.get("pdf_url")

        # ----------------------------------------------------
        # Keywords
        # ----------------------------------------------------

        keywords = []

        for concept in item.get("concepts", []):
            name = concept.get("display_name")

            if name:
                keywords.append(name)

        # ----------------------------------------------------
        # Abstract
        # ----------------------------------------------------

        abstract = reconstruct_openalex_abstract(
            item.get("abstract_inverted_index")
        )

        # ----------------------------------------------------
        # Stable internal ID
        # ----------------------------------------------------

        identity = (
            doi
            or arxiv_id
            or source_id
            or title
        )

        paper_id = "paper_" + hashlib.sha256(
            identity.lower().encode("utf-8")
        ).hexdigest()[:16]

        # ----------------------------------------------------
        # Normalize
        # ----------------------------------------------------

        paper = PaperMetadata(
            paper_id=paper_id,
            title=title,
            authors=authors,
            abstract=abstract,
            publication_year=item.get(
                "publication_year"
            ),
            publication_date=item.get(
                "publication_date"
            ),
            doi=doi,
            arxiv_id=arxiv_id,
            venue=venue,
            source=AcademicSource.OPENALEX,
            source_id=source_id,
            landing_url=landing_url,
            pdf_url=pdf_url,
            citation_count=item.get(
                "cited_by_count"
            ),
            keywords=keywords,
        )

        papers.append(
            paper.model_dump(mode="json")
        )

    return {
        "success": True,
        "source": AcademicSource.OPENALEX.value,
        "query": query,
        "count": len(papers),
        "papers": papers,
        "error": None,
    }


def parse_crossref_date(
    date_data: dict | None,
) -> tuple[int | None, str | None]:
    """
    Convert Crossref date-parts into publication year
    and an ISO-like publication date.
    """

    if not date_data:
        return None, None

    date_parts = date_data.get("date-parts")

    if not date_parts or not date_parts[0]:
        return None, None

    parts = date_parts[0]

    try:
        year = int(parts[0])
    except (TypeError, ValueError, IndexError):
        return None, None

    if len(parts) >= 3:
        publication_date = (
            f"{year:04d}-{int(parts[1]):02d}-{int(parts[2]):02d}"
        )
    elif len(parts) >= 2:
        publication_date = (
            f"{year:04d}-{int(parts[1]):02d}"
        )
    else:
        publication_date = str(year)

    return year, publication_date

async def search_crossref(
    query: str,
    max_results: int = 10,
) -> dict:
    """
    Search Crossref for candidate scholarly works.

    This function only executes the provided query.
    It does not generate search queries, deduplicate papers,
    rank papers, or select papers.
    """

    max_results = max(1, min(max_results, 100))

    params = {
        "query.bibliographic": query,
        "rows": max_results,
        "select": (
            "DOI,title,author,abstract,published,"
            "published-print,published-online,"
            "container-title,URL,link,is-referenced-by-count,"
            "subject"
        ),
    }

    if CROSSREF_MAILTO:
        params["mailto"] = CROSSREF_MAILTO

    headers = {
        "User-Agent": (
            "MultiAgentResearchSystem/1.0"
            + (
                f" (mailto:{CROSSREF_MAILTO})"
                if CROSSREF_MAILTO
                else ""
            )
        )
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                CROSSREF_API_URL,
                params=params,
                headers=headers,
            )

            if response.status_code == 429:
                return {
                    "success": False,
                    "source": AcademicSource.CROSSREF.value,
                    "query": query,
                    "count": 0,
                    "papers": [],
                    "error": "Crossref rate limit exceeded.",
                }

            response.raise_for_status()

    except httpx.HTTPError as exc:
        return {
            "success": False,
            "source": AcademicSource.CROSSREF.value,
            "query": query,
            "count": 0,
            "papers": [],
            "error": str(exc) or f"{type(exc).__name__} with no message.",
        }

    try:
        payload = response.json()

    except ValueError as exc:
        return {
            "success": False,
            "source": AcademicSource.CROSSREF.value,
            "query": query,
            "count": 0,
            "papers": [],
            "error": f"Failed to parse Crossref response: {exc}",
        }

    papers = []

    items = (
        payload.get("message", {})
        .get("items", [])
    )

    for item in items:

        # ----------------------------------------------------
        # Title
        # ----------------------------------------------------

        titles = item.get("title") or []

        title = (
            titles[0].strip()
            if titles
            else ""
        )

        if not title:
            continue

        # ----------------------------------------------------
        # Authors
        # ----------------------------------------------------

        authors = []

        for author in item.get("author", []):
            given = (author.get("given") or "").strip()
            family = (author.get("family") or "").strip()

            full_name = " ".join(
                part
                for part in [given, family]
                if part
            )

            if full_name:
                authors.append(full_name)

        # ----------------------------------------------------
        # DOI
        # ----------------------------------------------------

        doi = item.get("DOI")

        if doi:
            doi = doi.strip().lower()

        # ----------------------------------------------------
        # Publication date
        # ----------------------------------------------------

        date_data = (
            item.get("published")
            or item.get("published-print")
            or item.get("published-online")
        )

        publication_year, publication_date = (
            parse_crossref_date(date_data)
        )

        # ----------------------------------------------------
        # Venue
        # ----------------------------------------------------

        container_titles = (
            item.get("container-title") or []
        )

        venue = (
            container_titles[0].strip()
            if container_titles
            else None
        )

        # ----------------------------------------------------
        # Abstract
        # ----------------------------------------------------

        abstract = item.get("abstract")

        if abstract:
            abstract = " ".join(
                abstract.split()
            )

        # ----------------------------------------------------
        # Subject / keywords
        # ----------------------------------------------------

        keywords = [
            subject.strip()
            for subject in (item.get("subject") or [])
            if subject and subject.strip()
        ]

        # ----------------------------------------------------
        # PDF URL
        # ----------------------------------------------------

        pdf_url = None

        for link in item.get("link", []) or []:

            content_type = (
                link.get("content-type") or ""
            ).lower()

            url = link.get("URL")

            if url and content_type == "application/pdf":
                pdf_url = url
                break

        # ----------------------------------------------------
        # Stable internal ID
        # ----------------------------------------------------

        identity = (
            doi
            or item.get("URL")
            or title
        )

        paper_id = "paper_" + hashlib.sha256(
            identity.lower().encode("utf-8")
        ).hexdigest()[:16]

        # ----------------------------------------------------
        # Normalize into PaperMetadata
        # ----------------------------------------------------

        paper = PaperMetadata(
            paper_id=paper_id,
            title=title,
            authors=authors,
            abstract=abstract,
            publication_year=publication_year,
            publication_date=publication_date,
            doi=doi,
            arxiv_id=None,
            venue=venue,
            source=AcademicSource.CROSSREF,
            source_id=doi,
            landing_url=item.get("URL"),
            pdf_url=pdf_url,
            citation_count=item.get(
                "is-referenced-by-count"
            ),
            keywords=keywords,
        )

        papers.append(
            paper.model_dump(mode="json")
        )

    return {
        "success": True,
        "source": AcademicSource.CROSSREF.value,
        "query": query,
        "count": len(papers),
        "papers": papers,
        "error": None,
    }


async def search_tavily(
    query: str,
    max_results: int = 5,
) -> dict:
    """
    Search the web using Tavily.

    Tavily is used for supporting web context rather than
    canonical academic paper retrieval.

    This function only executes a query provided by the
    Root Agent. It does not generate search queries,
    deduplicate papers, rank papers, or select papers.
    """

    max_results = max(1, min(max_results, 20))

    if not TAVILY_API_KEY:
        return {
            "success": False,
            "source": AcademicSource.TAVILY.value,
            "query": query,
            "count": 0,
            "web_sources": [],
            "error": "TAVILY_API_KEY is not configured.",
        }

    headers = {
        "Authorization": f"Bearer {TAVILY_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "query": query,
        "search_depth": "basic",
        "max_results": max_results,
        "include_answer": False,
        "include_raw_content": False,
        "include_images": False,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                TAVILY_API_URL,
                json=payload,
                headers=headers,
            )

            if response.status_code == 401:
                return {
                    "success": False,
                    "source": AcademicSource.TAVILY.value,
                    "query": query,
                    "count": 0,
                    "web_sources": [],
                    "error": "Invalid or missing Tavily API key.",
                }

            if response.status_code == 429:
                return {
                    "success": False,
                    "source": AcademicSource.TAVILY.value,
                    "query": query,
                    "count": 0,
                    "web_sources": [],
                    "error": "Tavily rate limit exceeded.",
                }

            response.raise_for_status()

    except httpx.HTTPError as exc:
        return {
            "success": False,
            "source": AcademicSource.TAVILY.value,
            "query": query,
            "count": 0,
            "web_sources": [],
            "error": str(exc) or f"{type(exc).__name__} with no message.",
        }

    try:
        data = response.json()

    except ValueError as exc:
        return {
            "success": False,
            "source": AcademicSource.TAVILY.value,
            "query": query,
            "count": 0,
            "web_sources": [],
            "error": f"Failed to parse Tavily response: {exc}",
        }

    web_sources = []

    for index, item in enumerate(data.get("results", []), start=1):

        title = (item.get("title") or "").strip()
        url = (item.get("url") or "").strip()

        if not title or not url:
            continue

        identity = f"{query}:{url}"

        source_id = "web_" + hashlib.sha256(
            identity.encode("utf-8")
        ).hexdigest()[:16]

        source = WebSource(
            source_id=source_id,
            title=title,
            url=url,
            content=item.get("content"),
            query_id=None,
        )

        web_sources.append(
            source.model_dump(mode="json")
        )

    return {
        "success": True,
        "source": AcademicSource.TAVILY.value,
        "query": query,
        "count": len(web_sources),
        "web_sources": web_sources,
        "error": None,
    }


# ============================================================
# ANALYSIS AGENT TOOLS
# ============================================================

def normalize_doi_for_dedup(doi: str | None) -> str | None:
    """
    Normalize a DOI for duplicate matching.
    """

    if not doi:
        return None

    normalized = doi.strip().lower()

    normalized = normalized.replace(
        "https://doi.org/", ""
    ).replace(
        "http://doi.org/", ""
    )

    return normalized or None


def normalize_arxiv_id_for_dedup(arxiv_id: str | None) -> str | None:
    """
    Normalize an arXiv ID for duplicate matching.

    Different versions of the same paper (e.g. "2203.08975v1" and
    "2203.08975v2") must be treated as the same paper, so the
    version suffix is stripped.
    """

    if not arxiv_id:
        return None

    normalized = arxiv_id.strip().lower()
    normalized = re.sub(r"v\d+$", "", normalized)

    return normalized or None


def normalize_title_for_dedup(title: str | None) -> str | None:
    """
    Normalize a title for duplicate matching by lowercasing and
    collapsing all non-alphanumeric characters to single spaces.

    This tolerates minor punctuation/whitespace differences between
    sources without doing any fuzzy/approximate matching.
    """

    if not title:
        return None

    normalized = re.sub(
        r"[^a-z0-9]+", " ", title.lower()
    ).strip()

    return normalized or None


def deduplicate_papers(papers: list[dict]) -> dict:
    """
    Detect and remove duplicate papers retrieved from multiple
    academic databases.

    This does not rank or select papers; it only collapses records
    that describe the same underlying paper into one record.

    Duplicate matching priority (checked in this order):
        1. Normalized DOI
        2. Normalized arXiv ID (version suffix ignored)
        3. Normalized title

    When two records are judged to be the same paper, the first
    encountered record is kept and enriched with any fields the
    duplicate provides that the kept record is missing. Existing
    fields on the kept record are never overwritten, and no field
    values are invented.
    """

    kept_papers: list[dict] = []
    key_to_index: dict[tuple[str, str], int] = {}
    duplicate_groups: list[dict] = []

    enrichable_fields = [
        "abstract",
        "doi",
        "arxiv_id",
        "venue",
        "publication_year",
        "publication_date",
        "landing_url",
        "pdf_url",
        "citation_count",
    ]

    for paper in papers:

        candidate_keys = []

        doi_key = normalize_doi_for_dedup(paper.get("doi"))
        if doi_key:
            candidate_keys.append(("doi", doi_key))

        arxiv_key = normalize_arxiv_id_for_dedup(paper.get("arxiv_id"))
        if arxiv_key:
            candidate_keys.append(("arxiv", arxiv_key))

        title_key = normalize_title_for_dedup(paper.get("title"))
        if title_key:
            candidate_keys.append(("title", title_key))

        # ------------------------------------------------------
        # Find an existing match, checking DOI first, then
        # arXiv ID, then title.
        # ------------------------------------------------------

        match_index = None
        match_type = None

        for key in candidate_keys:
            if key in key_to_index:
                match_index = key_to_index[key]
                match_type = key[0]
                break

        if match_index is None:

            # Previously unseen paper.
            kept_papers.append(paper)
            new_index = len(kept_papers) - 1

            for key in candidate_keys:
                key_to_index[key] = new_index

            duplicate_groups.append(
                {
                    "kept_paper_id": paper.get("paper_id"),
                    "removed": [],
                }
            )

            continue

        # ------------------------------------------------------
        # Duplicate found: enrich the kept record and record
        # which paper_id was merged away.
        # ------------------------------------------------------

        kept_paper = kept_papers[match_index]

        for field in enrichable_fields:
            if not kept_paper.get(field) and paper.get(field):
                kept_paper[field] = paper[field]

        # Union keywords while preserving order.
        existing_keywords = kept_paper.get("keywords") or []

        for keyword in paper.get("keywords") or []:
            if keyword not in existing_keywords:
                existing_keywords.append(keyword)

        kept_paper["keywords"] = existing_keywords

        if not kept_paper.get("authors") and paper.get("authors"):
            kept_paper["authors"] = paper["authors"]

        # Register this paper's keys too, so a later paper can
        # match this group through any known identifier.
        for key in candidate_keys:
            key_to_index[key] = match_index

        duplicate_groups[match_index]["removed"].append(
            {
                "paper_id": paper.get("paper_id"),
                "match_type": match_type,
            }
        )

    # ------------------------------------------------------------
    # Re-validate every kept record against the canonical schema
    # so a merge can never leave a paper in an inconsistent shape.
    # ------------------------------------------------------------

    validated_papers = [
        PaperMetadata.model_validate(paper).model_dump(mode="json")
        for paper in kept_papers
    ]

    return {
        "papers": validated_papers,
        "original_count": len(papers),
        "deduplicated_count": len(validated_papers),
        "duplicates_removed": len(papers) - len(validated_papers),
        "duplicate_groups": [
            group
            for group in duplicate_groups
            if group["removed"]
        ],
    }


_RERANK_STOPWORDS = {
    "a", "an", "the", "of", "in", "on", "for", "and", "or", "to",
    "is", "are", "with", "using", "based", "by", "from", "at",
    "as", "into", "this", "that", "their", "its", "be", "how",
    "what", "which", "study", "review",
}


def tokenize_for_rerank(text: str | None) -> set[str]:
    """
    Lowercase a string and split it into a set of comparable
    words, dropping stopwords and very short tokens.

    A set is intentional: this scores WHICH query terms are
    present, not how many times, so repeated words don't inflate
    a paper's relevance.
    """

    if not text:
        return set()

    words = re.findall(r"[a-z0-9]+", text.lower())

    return {
        word
        for word in words
        if len(word) > 2 and word not in _RERANK_STOPWORDS
    }


def rerank_papers(
    papers: list[dict],
    research_question: str,
) -> dict:
    """
    Re-rank candidate papers according to their lexical relevance
    to the research question.

    This is deterministic term-overlap scoring, not an LLM
    judgment call. It gives the Analysis Agent a reproducible
    relevance signal to reason over; it does not select or
    discard papers.

    Scoring:
        - Query terms found in a paper's TITLE count double.
        - Query terms found only in the abstract/keywords count
          once.
        - The score is normalized to [0.0, 1.0] by the maximum
          possible weighted match count.

    Papers are ordered by score (descending), then by
    citation_count (descending, missing treated as 0), then by
    title (alphabetically) so the ordering is fully deterministic
    even when scores tie.
    """

    query_tokens = tokenize_for_rerank(research_question)

    scored_papers = []

    for paper in papers:

        title_tokens = tokenize_for_rerank(paper.get("title"))

        body_tokens = tokenize_for_rerank(
            paper.get("abstract")
        ) | tokenize_for_rerank(
            " ".join(paper.get("keywords") or [])
        )

        matched_in_title = query_tokens & title_tokens
        matched_in_body = (query_tokens & body_tokens) - matched_in_title

        max_possible = 2 * len(query_tokens)

        if max_possible:
            weighted_matches = (
                2 * len(matched_in_title) + len(matched_in_body)
            )
            relevance_score = weighted_matches / max_possible
        else:
            relevance_score = 0.0

        if not query_tokens:
            ranking_reason = (
                "Research question produced no comparable terms."
            )
        else:
            ranking_reason = (
                f"{len(matched_in_title)} query term(s) matched in "
                f"the title, {len(matched_in_body)} matched in the "
                f"abstract/keywords, out of {len(query_tokens)} "
                f"distinct query term(s)."
            )

        scored_papers.append(
            {
                "paper_id": paper.get("paper_id"),
                "title": paper.get("title") or "",
                "citation_count": paper.get("citation_count") or 0,
                "relevance_score": round(relevance_score, 4),
                "ranking_reason": ranking_reason,
            }
        )

    scored_papers.sort(
        key=lambda item: (
            -item["relevance_score"],
            -item["citation_count"],
            item["title"],
        )
    )

    ranked_papers = [
        RankedPaper(
            paper_id=paper["paper_id"],
            rank=rank,
            relevance_score=paper["relevance_score"],
            ranking_reason=paper["ranking_reason"],
        ).model_dump(mode="json")
        for rank, paper in enumerate(scored_papers, start=1)
    ]

    return {
        "ranked_papers": ranked_papers,
        "research_question": research_question,
        "paper_count": len(ranked_papers),
    }


def select_papers(
    ranked_papers: list[dict],
    max_papers: int = 20,
    min_relevance_score: float = 0.0,
) -> dict:
    """
    Select papers for deep analysis from a ranked-paper list.

    This is a deterministic baseline selection policy, not an LLM
    judgment call. It gives the Analysis Agent a reproducible
    starting corpus; it does not evaluate topical coverage or
    diversity across the selected papers - that judgment, if
    needed, is the Analysis Agent's responsibility.

    Selection policy (applied in this order):
        1. Discard any paper whose relevance_score is below
           min_relevance_score.
        2. Of the remaining papers, keep at most max_papers,
           preferring the best (lowest) rank first.

    Args:
        ranked_papers:
            RankedPaper-shaped dicts, as produced by
            rerank_papers()["ranked_papers"]. Not required to be
            pre-sorted.

        max_papers:
            Maximum number of papers to select. Values below 1 are
            treated as 1.

        min_relevance_score:
            Minimum relevance_score (inclusive) a paper must have
            to be eligible for selection.

    Returns:
        selected_paper_ids, selected_papers (kept, ordered by
        rank), excluded_papers (paper_id + exclusion reason), and
        counts.
    """

    max_papers = max(1, max_papers)

    sorted_papers = sorted(
        ranked_papers,
        key=lambda paper: paper["rank"],
    )

    selected_papers = []
    excluded_papers = []

    for paper in sorted_papers:

        if paper.get("relevance_score", 0.0) < min_relevance_score:
            excluded_papers.append(
                {
                    "paper_id": paper.get("paper_id"),
                    "reason": "below_relevance_threshold",
                }
            )
            continue

        if len(selected_papers) >= max_papers:
            excluded_papers.append(
                {
                    "paper_id": paper.get("paper_id"),
                    "reason": "max_papers_reached",
                }
            )
            continue

        selected_papers.append(paper)

    return {
        "selected_paper_ids": [
            paper["paper_id"] for paper in selected_papers
        ],
        "selected_papers": selected_papers,
        "excluded_papers": excluded_papers,
        "candidate_count": len(ranked_papers),
        "selected_count": len(selected_papers),
        "excluded_count": len(excluded_papers),
    }


async def download_pdf(
    pdf_url: str | None,
    paper_id: str,
) -> dict:
    """
    Download the PDF associated with a selected research paper.

    Writes the file to PAPERS_DIR/<paper_id>/<paper_id>.pdf and
    reports the outcome using the same RetrievalStatus values
    RetrievedPaper uses (downloaded/failed), so the Analysis Agent's
    result can be carried straight into ResearchState without
    translation.

    This function does not choose which papers to download; it
    only executes a single download that has already been decided
    upstream (by select_papers).

    A missing pdf_url is an expected, common case - many academic
    records have no open-access PDF - so it is reported as a failed
    retrieval rather than treated as an unexpected error.
    """

    if not pdf_url:
        return {
            "paper_id": paper_id,
            "pdf_url": pdf_url,
            "pdf_path": None,
            "retrieval_status": RetrievalStatus.FAILED.value,
            "retrieval_error": "No pdf_url was available for this paper.",
        }

    paper_dir = os.path.join(PAPERS_DIR, paper_id)
    destination_path = os.path.join(paper_dir, f"{paper_id}.pdf")

    downloaded_bytes = bytearray()

    try:
        async with httpx.AsyncClient(
            timeout=60.0,
            follow_redirects=True,
        ) as client:

            async with client.stream("GET", pdf_url) as response:

                if response.status_code != 200:
                    return {
                        "paper_id": paper_id,
                        "pdf_url": pdf_url,
                        "pdf_path": None,
                        "retrieval_status": RetrievalStatus.FAILED.value,
                        "retrieval_error": (
                            f"PDF request failed with HTTP "
                            f"{response.status_code}."
                        ),
                    }

                content_length = response.headers.get("content-length")

                if (
                    content_length
                    and int(content_length) > MAX_PDF_DOWNLOAD_BYTES
                ):
                    return {
                        "paper_id": paper_id,
                        "pdf_url": pdf_url,
                        "pdf_path": None,
                        "retrieval_status": RetrievalStatus.FAILED.value,
                        "retrieval_error": (
                            "PDF exceeds the maximum allowed download "
                            f"size ({MAX_PDF_DOWNLOAD_BYTES} bytes)."
                        ),
                    }

                async for chunk in response.aiter_bytes():
                    downloaded_bytes.extend(chunk)

                    if len(downloaded_bytes) > MAX_PDF_DOWNLOAD_BYTES:
                        return {
                            "paper_id": paper_id,
                            "pdf_url": pdf_url,
                            "pdf_path": None,
                            "retrieval_status": RetrievalStatus.FAILED.value,
                            "retrieval_error": (
                                "PDF download exceeded the maximum "
                                f"allowed size ({MAX_PDF_DOWNLOAD_BYTES} "
                                "bytes) while streaming."
                            ),
                        }

    except httpx.HTTPError as exc:
        return {
            "paper_id": paper_id,
            "pdf_url": pdf_url,
            "pdf_path": None,
            "retrieval_status": RetrievalStatus.FAILED.value,
            "retrieval_error": str(exc) or f"{type(exc).__name__} with no message.",
        }

    if not downloaded_bytes.startswith(b"%PDF"):
        return {
            "paper_id": paper_id,
            "pdf_url": pdf_url,
            "pdf_path": None,
            "retrieval_status": RetrievalStatus.FAILED.value,
            "retrieval_error": (
                "Downloaded content is not a valid PDF (missing %PDF "
                "header) - likely an HTML error or paywall page."
            ),
        }

    os.makedirs(paper_dir, exist_ok=True)

    with open(destination_path, "wb") as pdf_file:
        pdf_file.write(downloaded_bytes)

    return {
        "paper_id": paper_id,
        "pdf_url": pdf_url,
        "pdf_path": destination_path,
        "retrieval_status": RetrievalStatus.DOWNLOADED.value,
        "retrieval_error": None,
    }


# ============================================================
# PAPER CONTENT EXTRACTION (Marker + PyMuPDF)
# ============================================================
#
# Prepares a downloaded PDF for vision-grounded analysis by
# extracting the paper's real text (exact, via Marker - a local
# ML-based PDF-to-structure tool, not the VLM) and only sending the
# VLM small cropped images for the things that genuinely need visual
# interpretation - figures and tables - each positioned in the
# original reading order. Marker's own table->markdown conversion was
# found unreliable on complex scientific tables (confirmed by hand on
# a real paper), so tables are cropped as images from the original
# PDF via PyMuPDF instead of trusting Marker's table text.
#
# This replaced an earlier full-page-rendering approach
# (render every page whole, send full pages to the VLM) that was
# measured far too slow in practice (10+ minutes for a 2-page batch)
# to be usable.


def html_block_to_text(html: str | None) -> str:
    """
    Convert one Marker block's HTML fragment to plain text.

    Marker's per-block HTML is simple (e.g. a single wrapped <p>),
    so this only needs to strip tags, not handle arbitrary markup.
    """

    if not html:
        return ""

    return BeautifulSoup(html, "html.parser").get_text(separator=" ", strip=True)


def detect_image_mime_type(image_bytes: bytes) -> str:
    """
    Sniff an image's real encoding from its magic bytes rather than
    assuming PNG. Marker's own figure/diagram crops (returned as
    base64 in its JSON output) are not guaranteed to be PNG even
    though the PyMuPDF-cropped table images always are - confirmed by
    hand on a real paper, where every figure crop was actually JPEG.
    Sending a mismatched Content-Type to the VLM for an image that is
    actually JPEG risks the request being rejected or misread.
    """

    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"

    if image_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"

    return "image/png"


def crop_table_region(
    pdf_document: pymupdf.Document,
    page_index: int,
    bbox: list[float],
    dpi: int,
) -> bytes:
    """
    Render just one table's bounding box (as reported by Marker, in
    PDF point space) from the ORIGINAL pdf_document as a PNG.

    Cropping from the original PDF - not from Marker's own output -
    keeps this independent of whatever Marker did with the table
    content itself.
    """

    page = pdf_document[page_index]
    zoom = dpi / 72.0
    render_matrix = pymupdf.Matrix(zoom, zoom)
    clip_rect = pymupdf.Rect(*bbox)
    pixmap = page.get_pixmap(matrix=render_matrix, clip=clip_rect)
    return pixmap.tobytes("png")


def walk_marker_block(
    node: dict,
    page_index: int,
    pdf_document: pymupdf.Document,
    segments_dir: str,
    segments: list[dict],
    image_counter: dict[str, int],
) -> None:
    """
    Recursively walk one Marker block (and its children, if any) in
    document order, appending text/image segments to `segments`.

    Table and Diagram/Picture/Figure blocks are treated as leaves
    (their own children, if any, are not walked into) since their
    content is fully replaced by a single cropped image. Every other
    block with children (section groups, list groups, etc.) is
    walked into; every other leaf block contributes its text, if any
    - headers/footers are dropped since they carry no analytical
    content (running page headers/footers, not real content).
    """

    block_type = node.get("block_type")

    if block_type in ("PageHeader", "PageFooter"):
        return

    if block_type == "Table":
        image_counter["table"] += 1
        image_bytes = crop_table_region(
            pdf_document, page_index, node["bbox"], TABLE_CROP_DPI
        )
        image_path = os.path.join(
            segments_dir, f"table_{image_counter['table']:04d}.png"
        )
        with open(image_path, "wb") as image_file:
            image_file.write(image_bytes)

        segments.append(
            {
                "type": "image",
                "role": "table",
                "page_index": page_index,
                "image_path": image_path,
            }
        )
        return

    if block_type in ("Diagram", "Picture", "Figure"):
        images = node.get("images") or {}
        own_image_b64 = images.get(node.get("id"))

        if own_image_b64:
            image_bytes = base64.b64decode(own_image_b64)
            extension = (
                ".jpg"
                if detect_image_mime_type(image_bytes) == "image/jpeg"
                else ".png"
            )
            image_counter["figure"] += 1
            image_path = os.path.join(
                segments_dir, f"figure_{image_counter['figure']:04d}{extension}"
            )
            with open(image_path, "wb") as image_file:
                image_file.write(image_bytes)

            segments.append(
                {
                    "type": "image",
                    "role": "figure",
                    "page_index": page_index,
                    "image_path": image_path,
                }
            )
        return

    children = node.get("children")

    if children:
        for child in children:
            walk_marker_block(
                child, page_index, pdf_document, segments_dir, segments, image_counter
            )
        return

    text = html_block_to_text(node.get("html"))

    if text:
        segments.append(
            {
                "type": "text",
                "role": block_type,
                "page_index": page_index,
                "text": text,
            }
        )


def extract_paper_segments(pdf_path: str) -> dict:
    """
    Extract a paper's content as an ordered sequence of text/table-
    image/figure-image segments, in original reading order, for
    vision-language-model analysis.

    Runs Marker (a local PDF-to-structure tool) to get exact text
    and figure crops, then crops table regions from the original PDF
    via PyMuPDF (see module docstring above for why). Returns file
    paths for every image segment - never raw image bytes - so the
    calling agent's own turn only ever sees lightweight metadata,
    matching describe_image_with_vlm()/analyze_paper_with_vlm()'s
    own reasoning below (the vision call itself happens inside a
    tool, never inline in the agent's own turn).

    Writes into a "segments" subfolder next to the PDF:

        <pdf_path's directory>/segments/table_0001.png
        <pdf_path's directory>/segments/figure_0001.png
        ...

    and Marker's own raw output into an "extraction" subfolder.
    """

    if not os.path.isfile(pdf_path):
        return {
            "pdf_path": pdf_path,
            "segments": [],
            "segment_count": 0,
            "success": False,
            "error": f"No PDF file found at: {pdf_path}",
        }

    paper_dir = os.path.dirname(pdf_path)
    extraction_dir = os.path.join(paper_dir, "extraction")
    segments_dir = os.path.join(paper_dir, "segments")

    marker_executable = os.path.join(
        os.path.dirname(sys.executable),
        "marker_single.exe" if os.name == "nt" else "marker_single",
    )

    try:
        result = subprocess.run(
            [
                marker_executable,
                "--output_dir",
                extraction_dir,
                "--output_format",
                "json",
                pdf_path,
            ],
            capture_output=True,
            text=True,
            timeout=MARKER_TIMEOUT_SECONDS,
        )

    except FileNotFoundError:
        return {
            "pdf_path": pdf_path,
            "segments": [],
            "segment_count": 0,
            "success": False,
            "error": f"marker_single executable not found at: {marker_executable}",
        }

    except subprocess.TimeoutExpired:
        return {
            "pdf_path": pdf_path,
            "segments": [],
            "segment_count": 0,
            "success": False,
            "error": f"Marker extraction exceeded {MARKER_TIMEOUT_SECONDS}s.",
        }

    if result.returncode != 0:
        return {
            "pdf_path": pdf_path,
            "segments": [],
            "segment_count": 0,
            "success": False,
            "error": f"Marker extraction failed: {result.stderr[-500:]}",
        }

    base_name = os.path.splitext(os.path.basename(pdf_path))[0]
    json_path = os.path.join(extraction_dir, base_name, f"{base_name}.json")

    if not os.path.isfile(json_path):
        return {
            "pdf_path": pdf_path,
            "segments": [],
            "segment_count": 0,
            "success": False,
            "error": f"Marker did not produce the expected output: {json_path}",
        }

    try:
        with open(json_path, encoding="utf-8") as json_file:
            document_tree = json.load(json_file)

    except (OSError, json.JSONDecodeError) as exc:
        return {
            "pdf_path": pdf_path,
            "segments": [],
            "segment_count": 0,
            "success": False,
            "error": f"Failed to read Marker's output: {exc}",
        }

    try:
        pdf_document = pymupdf.open(pdf_path)

    except Exception as exc:
        return {
            "pdf_path": pdf_path,
            "segments": [],
            "segment_count": 0,
            "success": False,
            "error": f"Failed to open PDF for table cropping: {exc}",
        }

    os.makedirs(segments_dir, exist_ok=True)

    segments: list[dict] = []
    image_counter = {"table": 0, "figure": 0}

    try:
        for page_index, page_node in enumerate(document_tree.get("children") or []):
            walk_marker_block(
                page_node, page_index, pdf_document, segments_dir, segments, image_counter
            )

    finally:
        pdf_document.close()

    return {
        "pdf_path": pdf_path,
        "segments": segments,
        "segment_count": len(segments),
        "text_segment_count": sum(1 for s in segments if s["type"] == "text"),
        "table_count": image_counter["table"],
        "figure_count": image_counter["figure"],
        "success": True,
        "error": None,
    }


def build_vlm_message_content(segments: list[dict]) -> list[dict]:
    """
    Turn extract_paper_segments()'s ordered segment list into one
    chat-message content list: consecutive text segments are merged
    into single text parts (so the model reads flowing prose, not
    hundreds of tiny fragments), and each image segment becomes a
    small text label (what it is, which page) immediately followed
    by the actual image - all in original reading order.
    """

    content: list[dict] = []
    text_buffer: list[str] = []

    def flush_text_buffer() -> None:
        if text_buffer:
            content.append({"type": "text", "text": "\n\n".join(text_buffer)})
            text_buffer.clear()

    for segment in segments:

        if segment["type"] == "text":
            prefix = "## " if segment["role"] == "SectionHeader" else ""
            text_buffer.append(prefix + segment["text"])
            continue

        flush_text_buffer()

        content.append(
            {
                "type": "text",
                "text": f"[{segment['role'].upper()} from page {segment['page_index'] + 1}]",
            }
        )

        with open(segment["image_path"], "rb") as image_file:
            raw_image_bytes = image_file.read()

        mime_type = detect_image_mime_type(raw_image_bytes)
        encoded_image = base64.b64encode(raw_image_bytes).decode("ascii")

        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:{mime_type};base64,{encoded_image}"},
            }
        )

    flush_text_buffer()
    return content


def parse_vlm_json_object(raw_output: str | None) -> dict | None:
    """
    Parse the VLM's raw text response into a single JSON object.

    Tolerates markdown code-fence wrapping some models add anyway.
    Returns None (never a guess) if the result isn't valid JSON or
    isn't an object.
    """

    if not raw_output:
        return None

    text = raw_output.strip()

    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[len("json"):]
        text = text.strip()

    try:
        parsed = json.loads(text)

    except json.JSONDecodeError:
        return None

    if not isinstance(parsed, dict):
        return None

    return parsed


async def describe_image_with_vlm(image_path: str) -> dict:
    """
    Describe one cropped table/figure image with a single VLM call.

    NVIDIA NIM's hosted VLM_MODEL_NAME endpoint enforces at most one
    image per request (confirmed by hand: a multi-image request
    against it fails with "At most 1 image(s) may be provided in one
    prompt"), so a paper's images cannot be sent together in one
    call to this model - each is described individually here, and
    analyze_paper_with_vlm() below assembles those descriptions back
    into the document as text before the actual paper-level
    synthesis call.
    """

    try:
        with open(image_path, "rb") as image_file:
            raw_image_bytes = image_file.read()

        mime_type = detect_image_mime_type(raw_image_bytes)
        encoded_image = base64.b64encode(raw_image_bytes).decode("ascii")

    except Exception as exc:
        return {
            "description": None,
            "success": False,
            "error": f"Failed to read image: {exc}",
        }

    raw_output = None
    call_error = None

    for attempt in range(2):
        try:
            response = await litellm.acompletion(
                model=f"nvidia_nim/{VLM_MODEL_NAME}",
                api_key=NVIDIA_NIM_API_KEY,
                api_base=NVIDIA_NIM_API_BASE,
                timeout=VLM_REQUEST_TIMEOUT_SECONDS,
                messages=[
                    {"role": "system", "content": IMAGE_DESCRIPTION_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{encoded_image}"
                                },
                            }
                        ],
                    },
                ],
            )
            raw_output = response.choices[0].message.content
            call_error = None
            break

        except Exception as exc:
            call_error = exc
            if attempt == 0 and is_retryable_vlm_error(exc):
                continue
            break

    if call_error is not None:
        return {
            "description": None,
            "success": False,
            "error": f"VLM request failed: {call_error}",
        }

    if not raw_output or not raw_output.strip():
        return {
            "description": None,
            "success": False,
            "error": "VLM returned an empty description.",
        }

    return {"description": raw_output.strip(), "success": True, "error": None}


async def expand_image_segments_to_text(segments: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Replace every image segment (table/figure crop) with a text
    segment carrying that image's VLM-generated description,
    preserving original order and page_index/role.

    Each image's description is an independent VLM call, so all of a
    paper's images are described concurrently (bounded by
    VLM_CONCURRENCY, so a paper with many images doesn't burst an
    unbounded number of requests at once) instead of one at a time -
    this is the main cost in analyze_paper_with_vlm()'s runtime.
    Results are placed back by each image's original position in
    `segments`, never by completion order, so document order is
    unaffected by which call happens to finish first. A segment whose
    description fails is dropped from the returned sequence - never
    replaced with a fabricated description - and reported in the
    second return value so the caller can see what was lost.
    """

    semaphore = asyncio.Semaphore(VLM_CONCURRENCY)

    async def describe_with_limit(image_path: str) -> dict:
        async with semaphore:
            return await describe_image_with_vlm(image_path)

    image_indices = [
        index for index, segment in enumerate(segments) if segment["type"] == "image"
    ]

    results = await asyncio.gather(
        *(describe_with_limit(segments[index]["image_path"]) for index in image_indices)
    )
    result_by_index = dict(zip(image_indices, results))

    expanded: list[dict] = []
    failed: list[dict] = []

    for index, segment in enumerate(segments):

        if segment["type"] != "image":
            expanded.append(segment)
            continue

        result = result_by_index[index]

        if not result["success"]:
            failed.append(
                {
                    "role": segment["role"],
                    "page_index": segment["page_index"],
                    "image_path": segment["image_path"],
                    "error": result["error"],
                }
            )
            continue

        expanded.append(
            {
                "type": "text",
                "role": segment["role"],
                "page_index": segment["page_index"],
                "text": result["description"],
            }
        )

    return expanded, failed


async def analyze_paper_with_vlm(paper_id: str, segments: list[dict]) -> dict:
    """
    Analyze an entire paper and return a validated PaperAnalysis,
    using extract_paper_segments()'s ordered text/table-image/
    figure-image sequence.

    Two-phase, because the available vision model only accepts one
    image per request (see describe_image_with_vlm):

    1. Every table/figure image is described individually by the
       vision model (VLM_MODEL_NAME) and substituted into the
       document as text, in place.
    2. The now-fully-textual document (exact extracted text +
       VLM-generated image descriptions, in original reading order)
       is sent as ONE call to the reasoning model (ANALYSIS_MODEL_NAME
       - no vision needed at this point) to produce the paper-level
       synthesis, which is then validated via build_paper_analysis().

    This still means every table/figure was actually looked at by a
    vision model (grounded, not guessed from surrounding text) - it
    just happens as a preceding step rather than inside the final
    synthesis call.

    page_analyses is left empty in the returned PaperAnalysis - there
    is no per-page result in this pipeline; page-level provenance is
    each segment's page_index/role, not a PageAnalysis object.

    The returned "segments" field is this same grounded document (real
    extracted text + real VLM-generated image descriptions, in
    original reading order, each tagged page_index/role) that was
    actually sent to the synthesis call - returned alongside
    paper_analysis so the caller can cite specific pages (e.g. for
    Evidence generation) instead of only having the high-level
    synthesized summary fields to work from.
    """

    text_segments, failed_images = await expand_image_segments_to_text(segments)

    try:
        message_content = build_vlm_message_content(text_segments)

    except Exception as exc:
        return {
            "paper_id": paper_id,
            "paper_analysis": None,
            "success": False,
            "error": f"Failed to assemble synthesis message from segments: {exc}",
            "segments": text_segments,
            "failed_images": failed_images,
        }

    raw_output = None
    call_error = None

    for attempt in range(2):
        try:
            response = await litellm.acompletion(
                model=f"nvidia_nim/{ANALYSIS_MODEL_NAME}",
                api_key=NVIDIA_NIM_API_KEY,
                api_base=NVIDIA_NIM_API_BASE,
                timeout=VLM_REQUEST_TIMEOUT_SECONDS,
                messages=[
                    {"role": "system", "content": PAPER_LEVEL_ANALYSIS_PROMPT},
                    {"role": "user", "content": message_content},
                ],
            )
            raw_output = response.choices[0].message.content
            call_error = None
            break

        except Exception as exc:
            call_error = exc
            if attempt == 0 and is_retryable_vlm_error(exc):
                continue
            break

    if call_error is not None:
        return {
            "paper_id": paper_id,
            "paper_analysis": None,
            "success": False,
            "error": f"Synthesis request failed: {call_error}",
            "segments": text_segments,
            "failed_images": failed_images,
        }

    synthesis = parse_vlm_json_object(raw_output)

    if synthesis is None:
        return {
            "paper_id": paper_id,
            "paper_analysis": None,
            "success": False,
            "error": "Synthesis response was not a valid JSON object.",
            "segments": text_segments,
            "failed_images": failed_images,
        }

    result = build_paper_analysis(
        paper_id=paper_id,
        page_analyses=[],
        research_objective=synthesis.get("research_objective"),
        methodology=synthesis.get("methodology"),
        datasets=synthesis.get("datasets"),
        experimental_setup=synthesis.get("experimental_setup"),
        metrics=synthesis.get("metrics"),
        key_findings=synthesis.get("key_findings"),
        contributions=synthesis.get("contributions"),
        limitations=synthesis.get("limitations"),
        future_work=synthesis.get("future_work"),
    )
    result["segments"] = text_segments
    result["failed_images"] = failed_images
    return result


def is_retryable_vlm_error(exc: Exception) -> bool:
    """
    True only for transient failures worth retrying once: a request
    timeout, or a 5xx from the provider's own gateway. Never retries
    on anything else (bad request, auth failure, malformed input,
    etc.) - those will not succeed on a second attempt.
    """

    if isinstance(exc, litellm.Timeout):
        return True

    status_code = getattr(exc, "status_code", None)
    return status_code is not None and 500 <= status_code < 600


def build_paper_analysis(
    paper_id: str,
    page_analyses: list[dict],
    research_objective: str | None = None,
    methodology: str | None = None,
    datasets: list[str] | None = None,
    experimental_setup: str | None = None,
    metrics: dict[str, str] | None = None,
    key_findings: list[str] | None = None,
    contributions: list[str] | None = None,
    limitations: list[str] | None = None,
    future_work: list[str] | None = None,
) -> dict:
    """
    Assemble and validate one paper's structured PaperAnalysis.

    Combining page-level understanding into a paper-level synthesis
    (what is this paper's methodology, what did it actually
    contribute, etc.) is judgment the Analysis Agent works out itself
    from the page_analyses it already has - this function does not
    do that reasoning. It only validates the agent's synthesized
    fields against the canonical PaperAnalysis schema and re-attaches
    the already-produced page_analyses deterministically, so they
    never have to be (and cannot be garbled by) re-typing them.

    evidence is intentionally left empty here - Evidence generation
    is a separate, later step, not part of this assembly.

    Returns a structured validation failure (never a fabricated or
    partially-coerced PaperAnalysis) if the supplied fields don't
    satisfy the schema.
    """

    try:
        paper_analysis = PaperAnalysis.model_validate(
            {
                "paper_id": paper_id,
                "research_objective": research_objective,
                "methodology": methodology,
                "datasets": datasets or [],
                "experimental_setup": experimental_setup,
                "metrics": metrics or {},
                "key_findings": key_findings or [],
                "contributions": contributions or [],
                "limitations": limitations or [],
                "future_work": future_work or [],
                "page_analyses": page_analyses,
                "evidence": [],
            }
        )

    except Exception as exc:
        return {
            "paper_id": paper_id,
            "paper_analysis": None,
            "success": False,
            "error": f"PaperAnalysis validation failed: {exc}",
        }

    return {
        "paper_id": paper_id,
        "paper_analysis": paper_analysis.model_dump(mode="json"),
        "success": True,
        "error": None,
    }


def build_evidence(paper_analysis: dict, evidence_items: list[dict]) -> dict:
    """
    Attach a list of agent-judged Evidence objects onto an already-
    built PaperAnalysis (as returned by build_paper_analysis() /
    analyze_paper_with_vlm()'s "paper_analysis" field).

    Deciding what counts as evidence-worthy - which finding, table,
    figure, or methodology detail actually matters, why it is
    relevant to the research question, how confident to be, which
    pages support it - is the Analysis Agent's own judgment, grounded
    in the paper's real extracted text/table/figure descriptions
    (analyze_paper_with_vlm()'s returned "segments", each carrying the
    page_index that page-cited evidence must be derived from). This
    function does not do that reasoning.

    What it does do deterministically: assigns every evidence item a
    unique evidence_id scoped to the paper (e.g. "<paper_id>_evidence_001",
    in the given order) - never trusting the agent to invent unique
    IDs across a batch - and forces paper_id to match the given
    paper_analysis (never trusting an agent-supplied value there
    either, present or not), then validates the result against the
    canonical PaperAnalysis schema (which validates each item against
    Evidence in the process). Returns a structured validation failure
    (never a fabricated or partially-coerced PaperAnalysis) if any
    evidence item doesn't satisfy the schema.
    """

    paper_id = paper_analysis.get("paper_id")

    numbered_evidence = []

    for index, item in enumerate(evidence_items, start=1):
        candidate = dict(item)
        candidate["evidence_id"] = f"{paper_id}_evidence_{index:03d}"
        candidate["paper_id"] = paper_id
        numbered_evidence.append(candidate)

    updated_paper_analysis = dict(paper_analysis)
    updated_paper_analysis["evidence"] = numbered_evidence

    try:
        validated = PaperAnalysis.model_validate(updated_paper_analysis)

    except Exception as exc:
        return {
            "paper_id": paper_id,
            "paper_analysis": None,
            "success": False,
            "error": f"PaperAnalysis validation failed after attaching evidence: {exc}",
        }

    return {
        "paper_id": paper_id,
        "paper_analysis": validated.model_dump(mode="json"),
        "success": True,
        "error": None,
    }


# ============================================================
# SYNTHESIZER TOOLS
# ============================================================

def build_synthesis(
    thematic_findings: list[str] | None = None,
    methodological_comparison: list[str] | None = None,
    dataset_comparison: list[str] | None = None,
    metric_comparison: list[str] | None = None,
    contradictions: list[str] | None = None,
    common_trends: list[str] | None = None,
    strengths: list[str] | None = None,
    weaknesses: list[str] | None = None,
    research_gaps: list[dict] | None = None,
    claims: list[dict] | None = None,
) -> dict:
    """
    Assemble and validate the cross-paper Synthesis.

    Working out themes, methodological/dataset/metric comparisons,
    agreements, contradictions, trends, limitations, research gaps,
    and supported claims from the analyzed PaperAnalysis/Evidence
    corpus is the Synthesizer Agent's own cross-paper reasoning - this
    function does not do that reasoning. It only assigns deterministic,
    unique IDs to research_gaps/claims (gap_001, gap_002, ...;
    claim_001, claim_002, ... - in the given order, never trusting the
    agent to invent unique IDs across a batch, the same reasoning as
    build_evidence()'s evidence_id) and validates the combined result
    against the canonical Synthesis schema.

    Returns a structured validation failure (never a fabricated or
    partially-coerced Synthesis) if the supplied fields don't satisfy
    the schema.
    """

    numbered_gaps = []
    for index, gap in enumerate(research_gaps or [], start=1):
        candidate = dict(gap)
        candidate["gap_id"] = f"gap_{index:03d}"
        numbered_gaps.append(candidate)

    numbered_claims = []
    for index, claim in enumerate(claims or [], start=1):
        candidate = dict(claim)
        candidate["claim_id"] = f"claim_{index:03d}"
        numbered_claims.append(candidate)

    try:
        synthesis = Synthesis.model_validate(
            {
                "thematic_findings": thematic_findings or [],
                "methodological_comparison": methodological_comparison or [],
                "dataset_comparison": dataset_comparison or [],
                "metric_comparison": metric_comparison or [],
                "contradictions": contradictions or [],
                "common_trends": common_trends or [],
                "strengths": strengths or [],
                "weaknesses": weaknesses or [],
                "research_gaps": numbered_gaps,
                "claims": numbered_claims,
            }
        )

    except Exception as exc:
        return {
            "synthesis": None,
            "success": False,
            "error": f"Synthesis validation failed: {exc}",
        }

    return {
        "synthesis": synthesis.model_dump(mode="json"),
        "success": True,
        "error": None,
    }


# ============================================================
# WRITER TOOLS
# ============================================================

def build_literature_review_draft(
    title: str,
    introduction: str,
    sections: list[dict],
    conclusion: str,
    claims: list[dict],
    citations: list[dict],
) -> dict:
    """
    Assemble and validate the structured LiteratureReviewDraft.

    Organizing the review, writing evidence-grounded academic prose,
    and deciding which claims/citations support which section is the
    Writer Agent's own reasoning - this function does not do that
    reasoning. It only handles deterministic bookkeeping and schema
    validation:

    - sections: each is assigned a unique section_id (section_001,
      section_002, ... in the given order) - never trusting the agent
      to invent unique IDs, the same reasoning as build_evidence()'s
      evidence_id / build_synthesis()'s gap_id/claim_id.
    - citations: each is a NEW record (this is where Citation objects
      first come into existence in the pipeline) built from real
      PaperMetadata the agent was given - each is assigned a unique
      citation_id (citation_001, ...) the same way.
    - claims: these are NOT new - they are the Synthesizer's own
      already-ID'd Claim objects (claim_001, ...) being carried
      forward into the draft, so their claim_id is trusted/preserved
      as-is here. Reassigning it would break the Claim -> Evidence ->
      Paper -> Page traceability chain the Writer/Validator both rely
      on. The schema still validates each one is well-formed.

    Returns a structured validation failure (never a fabricated or
    partially-coerced LiteratureReviewDraft) if the supplied fields
    don't satisfy the schema.
    """

    numbered_sections = []
    for index, section in enumerate(sections, start=1):
        candidate = dict(section)
        candidate["section_id"] = f"section_{index:03d}"
        numbered_sections.append(candidate)

    numbered_citations = []
    for index, citation in enumerate(citations, start=1):
        candidate = dict(citation)
        candidate["citation_id"] = f"citation_{index:03d}"
        numbered_citations.append(candidate)

    try:
        draft = LiteratureReviewDraft.model_validate(
            {
                "title": title,
                "introduction": introduction,
                "sections": numbered_sections,
                "conclusion": conclusion,
                "claims": claims,
                "citations": numbered_citations,
            }
        )

    except Exception as exc:
        return {
            "draft": None,
            "success": False,
            "error": f"LiteratureReviewDraft validation failed: {exc}",
        }

    return {
        "draft": draft.model_dump(mode="json"),
        "success": True,
        "error": None,
    }


# ============================================================
# CONTENT REVIEWER TOOLS
# ============================================================

def build_content_review_result(
    status: str,
    issues: list[dict] | None = None,
    unsupported_claim_ids: list[str] | None = None,
    missing_coverage: list[str] | None = None,
    revision_instructions: list[str] | None = None,
    summary: str | None = None,
) -> dict:
    """
    Assemble and validate the Content Reviewer's structured
    ContentReviewResult.

    Judging whether the draft is coherent, evidence-grounded,
    complete, and faithful to the synthesis - and deciding PASS vs
    REVISE - is the Content Reviewer's own reasoning; this function
    does not do that judgment. It only assigns each issue a
    deterministic, unique issue_id (issue_001, issue_002, ... in the
    given order - never trusting the agent to invent unique IDs, the
    same reasoning as every other build_*() tool in this pipeline)
    and validates the combined result against the canonical
    ContentReviewResult schema.

    Returns a structured validation failure (never a fabricated or
    partially-coerced ContentReviewResult) if the supplied fields
    don't satisfy the schema.
    """

    numbered_issues = []

    for index, issue in enumerate(issues or [], start=1):
        candidate = dict(issue)
        candidate["issue_id"] = f"issue_{index:03d}"
        numbered_issues.append(candidate)

    try:
        result = ContentReviewResult.model_validate(
            {
                "status": status,
                "issues": numbered_issues,
                "unsupported_claim_ids": unsupported_claim_ids or [],
                "missing_coverage": missing_coverage or [],
                "revision_instructions": revision_instructions or [],
                "summary": summary,
            }
        )

    except Exception as exc:
        return {
            "content_review_result": None,
            "success": False,
            "error": f"ContentReviewResult validation failed: {exc}",
        }

    return {
        "content_review_result": result.model_dump(mode="json"),
        "success": True,
        "error": None,
    }


# ============================================================
# CITATION REVIEWER TOOLS
# ============================================================

async def verify_doi(doi: str) -> dict:
    """
    Verify whether a DOI exists and, if it does, report what it
    actually resolves to - via Crossref's per-DOI lookup endpoint
    (the same Crossref API already used by search_crossref()).

    This function only checks existence/resolution. It does NOT judge
    whether the resolved record matches any particular claimed title
    - that identity comparison is verify_source_identity()'s job, so
    the same resolution logic isn't duplicated with different
    judgment baked in.

    Reports a tri-state outcome so "confirmed does not exist" is
    never conflated with "could not be checked" - CITATION_REVIEWER_PROMPT
    explicitly distinguishes VERIFIED/INVALID/UNVERIFIED, and treating
    a transient tool failure as proof of fabrication would violate
    "Never treat a search-tool failure as proof that a paper does not
    exist.":

        exists=True  -> Crossref has a record for this DOI.
        exists=False -> Crossref returned 404: the DOI does not exist.
        exists=None  -> could not be determined (malformed DOI, rate
                         limit, transport failure) - success=False.
    """

    normalized_doi = normalize_doi_for_dedup(doi)

    if not normalized_doi:
        return {
            "doi": doi,
            "exists": None,
            "resolved_title": None,
            "resolved_authors": [],
            "resolved_year": None,
            "resolved_venue": None,
            "success": False,
            "error": "No DOI provided.",
        }

    params = {"mailto": CROSSREF_MAILTO} if CROSSREF_MAILTO else {}

    headers = {
        "User-Agent": (
            "MultiAgentResearchSystem/1.0"
            + (
                f" (mailto:{CROSSREF_MAILTO})"
                if CROSSREF_MAILTO
                else ""
            )
        )
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{CROSSREF_API_URL}/{normalized_doi}",
                params=params,
                headers=headers,
            )

            if response.status_code == 404:
                return {
                    "doi": doi,
                    "exists": False,
                    "resolved_title": None,
                    "resolved_authors": [],
                    "resolved_year": None,
                    "resolved_venue": None,
                    "success": True,
                    "error": None,
                }

            if response.status_code == 429:
                return {
                    "doi": doi,
                    "exists": None,
                    "resolved_title": None,
                    "resolved_authors": [],
                    "resolved_year": None,
                    "resolved_venue": None,
                    "success": False,
                    "error": "Crossref rate limit exceeded.",
                }

            response.raise_for_status()

    except httpx.HTTPError as exc:
        return {
            "doi": doi,
            "exists": None,
            "resolved_title": None,
            "resolved_authors": [],
            "resolved_year": None,
            "resolved_venue": None,
            "success": False,
            "error": str(exc) or f"{type(exc).__name__} with no message.",
        }

    try:
        payload = response.json()

    except ValueError as exc:
        return {
            "doi": doi,
            "exists": None,
            "resolved_title": None,
            "resolved_authors": [],
            "resolved_year": None,
            "resolved_venue": None,
            "success": False,
            "error": f"Failed to parse Crossref response: {exc}",
        }

    item = payload.get("message") or {}

    titles = item.get("title") or []
    resolved_title = titles[0].strip() if titles else None

    resolved_authors = []

    for author in item.get("author", []):
        given = (author.get("given") or "").strip()
        family = (author.get("family") or "").strip()

        full_name = " ".join(
            part for part in [given, family] if part
        )

        if full_name:
            resolved_authors.append(full_name)

    date_data = (
        item.get("published")
        or item.get("published-print")
        or item.get("published-online")
    )

    resolved_year, _ = parse_crossref_date(date_data)

    container_titles = item.get("container-title") or []
    resolved_venue = container_titles[0].strip() if container_titles else None

    return {
        "doi": doi,
        "exists": True,
        "resolved_title": resolved_title,
        "resolved_authors": resolved_authors,
        "resolved_year": resolved_year,
        "resolved_venue": resolved_venue,
        "success": True,
        "error": None,
    }


async def verify_paper_metadata(
    title: str,
    authors: list[str],
    year: int | None = None,
    doi: str | None = None
) -> dict:
    """
    Verify bibliographic metadata against live academic sources.

    DOI-first: if a DOI is given, reuses verify_doi() to resolve it
    directly - no need to duplicate that lookup logic here. Falls
    back to a Crossref title search (reusing search_crossref()) when
    no DOI was given, or the given DOI didn't resolve to a real
    record (never assumes a failed/missing DOI means the paper itself
    doesn't exist - it might just be findable under a title search
    instead).

    Like verify_doi(), this reports comparison FACTS
    (title_match/author_overlap/year_match), not a single opinionated
    "verified" boolean - deciding whether those facts add up to a
    genuinely verified citation is the Citation Reviewer's own
    judgment (CITATION_REVIEWER_PROMPT: "Minor formatting differences
    should not automatically cause rejection... Focus on identity and
    substantive metadata consistency"), consistent with this
    project's tool/agent boundary elsewhere.

    title_match uses the same normalized-equality comparison already
    used for deduplication (normalize_title_for_dedup) - tolerant of
    case/punctuation/whitespace differences, not a fuzzy match.
    """

    normalized_claimed_title = normalize_title_for_dedup(title)

    matched_title = None
    matched_authors: list[str] = []
    matched_year = None
    matched_doi = None
    verification_source = "none"
    found = False
    tool_error = None

    if doi:
        doi_result = await verify_doi(doi)

        if doi_result["success"] and doi_result["exists"]:
            matched_title = doi_result["resolved_title"]
            matched_authors = doi_result["resolved_authors"]
            matched_year = doi_result["resolved_year"]
            matched_doi = normalize_doi_for_dedup(doi)
            verification_source = "doi"
            found = True

        elif not doi_result["success"]:
            tool_error = doi_result["error"]

    if not found:
        search_result = await search_crossref(title, max_results=5)

        if search_result["success"]:
            # A successful (even if empty) search is a real outcome,
            # not a failure - clears any earlier DOI-check error since
            # that error no longer describes what actually happened.
            tool_error = None

            for paper in search_result["papers"]:
                if (
                    normalize_title_for_dedup(paper.get("title"))
                    == normalized_claimed_title
                ):
                    matched_title = paper.get("title")
                    matched_authors = paper.get("authors") or []
                    matched_year = paper.get("publication_year")
                    matched_doi = normalize_doi_for_dedup(paper.get("doi"))
                    verification_source = "title_search"
                    found = True
                    break

        elif tool_error is None:
            tool_error = search_result["error"]

    title_match = bool(
        normalized_claimed_title
        and matched_title
        and normalize_title_for_dedup(matched_title) == normalized_claimed_title
    )

    normalized_claimed_authors = {
        author.strip().lower() for author in (authors or []) if author and author.strip()
    }
    normalized_matched_authors = {
        author.strip().lower() for author in matched_authors if author and author.strip()
    }
    author_overlap_count = len(normalized_claimed_authors & normalized_matched_authors)

    if year is not None and matched_year is not None:
        year_match = year == matched_year
    else:
        year_match = None

    return {
        "title": title,
        "doi": doi,
        "verification_source": verification_source,
        "found": found,
        "matched_title": matched_title,
        "matched_authors": matched_authors,
        "matched_year": matched_year,
        "matched_doi": matched_doi,
        "title_match": title_match,
        "author_overlap_count": author_overlap_count,
        "claimed_author_count": len(normalized_claimed_authors),
        "matched_author_count": len(normalized_matched_authors),
        "year_match": year_match,
        "success": found or tool_error is None,
        "error": tool_error,
    }


async def verify_source_identity(
    paper_id: str,
    title: str,
    doi: str | None = None
) -> dict:
    """
    Confirm that a claimed title/doi pair genuinely identify the same
    real scholarly work - the narrow "does this citation's identity
    hold together" check CITATION_REVIEWER_PROMPT distinguishes from
    general metadata verification (Section 4 vs Section 3): a DOI
    that resolves fine but to a DIFFERENT paper than the claimed
    title is exactly the failure mode this catches.

    paper_id is carried through unchanged into the result purely for
    the caller's own bookkeeping (correlating this identity check
    back to its Claim -> Evidence -> Paper -> Citation chain) - this
    function does not look paper_id up anywhere itself.

    Reuses verify_paper_metadata()'s DOI-first / title-search-fallback
    logic rather than duplicating it - author/year aren't relevant to
    a pure identity check, so only its title-match result is used.

    Tri-state identity_verified, same reasoning as verify_doi()'s
    exists field:
        True  -> a real record was found and its title matches the
                 claimed title.
        False -> a real record was found but its title does NOT
                 match - a genuine identity mismatch (e.g. DOI points
                 to a different paper).
        None  -> no record could be found/checked at all - unverified,
                 not a confirmed mismatch.
    """

    metadata_result = await verify_paper_metadata(
        title=title,
        authors=[],
        year=None,
        doi=doi,
    )

    if not metadata_result["found"]:
        identity_verified = None
        explanation = (
            "No scholarly record could be found for this title/DOI - "
            "identity could not be verified."
            if metadata_result["success"]
            else f"Identity check failed: {metadata_result['error']}"
        )

    elif metadata_result["title_match"]:
        identity_verified = True
        explanation = "The resolved record's title matches the claimed title."

    else:
        identity_verified = False
        explanation = (
            "A record was found, but its title does not match the claimed "
            "title - possible source-identity mismatch "
            f"(resolved: {metadata_result['matched_title']!r})."
        )

    return {
        "paper_id": paper_id,
        "title": title,
        "doi": doi,
        "identity_verified": identity_verified,
        "resolved_title": metadata_result["matched_title"],
        "resolved_doi": metadata_result["matched_doi"],
        "verification_source": metadata_result["verification_source"],
        "explanation": explanation,
        "success": metadata_result["success"],
        "error": metadata_result["error"],
    }


def build_citation_review_result(
    status: str,
    verifications: list[dict] | None = None,
    invalid_citation_ids: list[str] | None = None,
    unsupported_claim_ids: list[str] | None = None,
    revision_instructions: list[str] | None = None,
    summary: str | None = None,
) -> dict:
    """
    Assemble and validate the Citation Reviewer's structured
    CitationReviewResult.

    Judging whether each citation is genuinely verified - combining
    the factual outputs of verify_doi()/verify_paper_metadata()/
    verify_source_identity() into paper_exists/doi_verified/
    metadata_verified/source_verified/claim_supported judgments per
    citation, and deciding PASS vs REVISE - is the Citation Reviewer's
    own reasoning; this function does not do that judgment.

    Unlike every other build_*() tool in this pipeline, this one does
    NOT mint new IDs: each CitationVerification.citation_id must be
    an EXISTING citation_id from the draft under review - citations
    were already minted in build_literature_review_draft(), so
    reassigning citation_id here would break the citation-to-draft
    traceability this whole review exists to protect. Same reasoning
    as claim_id being preserved (not reassigned) in
    build_literature_review_draft().

    Returns a structured validation failure (never a fabricated or
    partially-coerced CitationReviewResult) if the supplied fields
    don't satisfy the schema.
    """

    try:
        result = CitationReviewResult.model_validate(
            {
                "status": status,
                "verifications": verifications or [],
                "invalid_citation_ids": invalid_citation_ids or [],
                "unsupported_claim_ids": unsupported_claim_ids or [],
                "revision_instructions": revision_instructions or [],
                "summary": summary,
            }
        )

    except Exception as exc:
        return {
            "citation_review_result": None,
            "success": False,
            "error": f"CitationReviewResult validation failed: {exc}",
        }

    return {
        "citation_review_result": result.model_dump(mode="json"),
        "success": True,
        "error": None,
    }
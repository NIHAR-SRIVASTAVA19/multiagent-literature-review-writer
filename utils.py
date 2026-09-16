from __future__ import annotations

from schemas import AcademicSource, SearchQuery
from tools import (
    search_arxiv,
    search_semantic_scholar,
    search_openalex,
    search_crossref,
    search_tavily,
)


async def execute_search_query(
    search_query: SearchQuery,
    max_results: int = 10,
) -> dict:
    """
    Route a SearchQuery to the correct retrieval tool.

    Important architecture rule:
    - Root Agent generates SearchQuery objects.
    - Search Coordinator executes them.
    - This function does not generate, rank, deduplicate,
      or select papers.
    """

    if search_query.source == AcademicSource.ARXIV:
        return await search_arxiv(
            query=search_query.query,
            max_results=max_results,
        )

    if search_query.source == AcademicSource.SEMANTIC_SCHOLAR:
        return await search_semantic_scholar(
            query=search_query.query,
            max_results=max_results,
        )

    if search_query.source == AcademicSource.OPENALEX:
        return await search_openalex(
            query=search_query.query,
            max_results=max_results,
        )

    if search_query.source == AcademicSource.CROSSREF:
        return await search_crossref(
            query=search_query.query,
            max_results=max_results,
        )

    if search_query.source == AcademicSource.TAVILY:
        return await search_tavily(
            query=search_query.query,
            max_results=max_results,
        )

    return {
        "success": False,
        "source": search_query.source.value,
        "query": search_query.query,
        "count": 0,
        "error": f"Unsupported search source: {search_query.source}",
    }


async def execute_search_queries(
    search_queries: list[SearchQuery],
    max_results_per_query: int = 10,
) -> dict:
    """
    Execute multiple SearchQuery objects and aggregate results.

    Academic results are collected separately from Tavily
    web-context results.
    """

    candidate_papers = []
    web_sources = []
    errors = []
    executions = []

    for search_query in search_queries:

        result = await execute_search_query(
            search_query=search_query,
            max_results=max_results_per_query,
        )

        executions.append(
            {
                "query_id": search_query.query_id,
                "query": search_query.query,
                "source": search_query.source.value,
                "success": result.get("success", False),
                "count": result.get("count", 0),
            }
        )

        if not result.get("success"):
            errors.append(
                {
                    "query_id": search_query.query_id,
                    "source": search_query.source.value,
                    "query": search_query.query,
                    "error": result.get("error")
                    or "Unknown retrieval error",
                }
            )
            continue

        if search_query.source == AcademicSource.TAVILY:
            web_sources.extend(
                result.get("web_sources", [])
            )

        else:
            candidate_papers.extend(
                result.get("papers", [])
            )

    return {
        "success": len(errors) < len(search_queries),
        "candidate_papers": candidate_papers,
        "web_sources": web_sources,
        "errors": errors,
        "executions": executions,
        "paper_count": len(candidate_papers),
        "web_source_count": len(web_sources),
    }
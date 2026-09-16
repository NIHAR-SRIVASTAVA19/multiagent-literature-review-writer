from __future__ import annotations

from google.adk.agents import Agent

from config import SEARCH_MODEL
from prompts import SEARCH_COORDINATOR_PROMPT
from schemas import SearchQuery
from utils import execute_search_queries


async def execute_research_searches(
    search_queries: list[dict],
    max_results_per_query: int = 10,
) -> dict:
    """
    Execute search queries created by the Root Agent.

    This function:
    - validates incoming query dictionaries
    - routes each query to the correct retrieval provider
    - aggregates academic papers and web sources

    It does NOT:
    - generate new search queries
    - deduplicate papers
    - rank papers
    - select final papers
    """

    validated_queries = [
        SearchQuery.model_validate(query)
        for query in search_queries
    ]

    result = await execute_search_queries(
        search_queries=validated_queries,
        max_results_per_query=max_results_per_query,
    )

    return result


search_coordinator = Agent(
    name="search_coordinator",

    model=SEARCH_MODEL,

    description=(
        "Search execution specialist responsible for retrieving candidate research "
        "papers and relevant web context from live academic and web sources using "
        "search queries provided by the Root Agent."
    ),

    instruction=SEARCH_COORDINATOR_PROMPT,

    tools=[
        execute_research_searches,
    ],
)
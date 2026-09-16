import asyncio
import sys

# Windows' default console codec (cp1252) can't encode characters models
# or APIs commonly emit (em dashes, narrow no-break spaces, etc.), which
# crashes print() mid-run. Force UTF-8 stdout so output never depends on
# the terminal's active code page.
sys.stdout.reconfigure(encoding="utf-8")

# from tools import search_arxiv


# async def main():

#     result = await search_arxiv(
#         query="multi agent systems",
#         max_results=3,
#     )

#     print("Success:", result["success"])
#     print("Count:", result["count"])

#     for paper in result["papers"]:
#         print()
#         print("Title:", paper["title"])
#         print("Authors:", paper["authors"])
#         print("Year:", paper["publication_year"])
#         print("arXiv ID:", paper["arxiv_id"])
#         print("PDF:", paper["pdf_url"])


# if __name__ == "__main__":
#     asyncio.run(main())




# from tools import search_semantic_scholar


# async def main():

#     result = await search_semantic_scholar(
#         query="multi agent systems",
#         max_results=3,
#     )

#     print("Success:", result["success"])
#     print("Count:", result["count"])

#     if result["error"]:
#         print("Error:", result["error"])

#     for paper in result["papers"]:
#         print()
#         print("Title:", paper["title"])
#         print("Authors:", paper["authors"])
#         print("Year:", paper["publication_year"])
#         print("DOI:", paper["doi"])
#         print("arXiv ID:", paper["arxiv_id"])
#         print("Citations:", paper["citation_count"])
#         print("PDF:", paper["pdf_url"])
#         print("Source ID:", paper["source_id"])


# if __name__ == "__main__":
#     asyncio.run(main())




# from tools import search_openalex


# async def main():

#     result = await search_openalex(
#         query="multi agent systems",
#         max_results=3,
#     )

#     print("Success:", result["success"])
#     print("Count:", result["count"])

#     if result["error"]:
#         print("Error:", result["error"])

#     for paper in result["papers"]:
#         print()
#         print("Title:", paper["title"])
#         print("Authors:", paper["authors"])
#         print("Year:", paper["publication_year"])
#         print("DOI:", paper["doi"])
#         print("arXiv ID:", paper["arxiv_id"])
#         print("Citations:", paper["citation_count"])
#         print("Venue:", paper["venue"])
#         print("PDF:", paper["pdf_url"])
#         print("Source ID:", paper["source_id"])


# if __name__ == "__main__":
#     asyncio.run(main())



# from tools import search_crossref


# async def main():

#     result = await search_crossref(
#         query="multi agent systems",
#         max_results=3,
#     )

#     print("Success:", result["success"])
#     print("Count:", result["count"])

#     if result["error"]:
#         print("Error:", result["error"])

#     for paper in result["papers"]:
#         print()
#         print("Title:", paper["title"])
#         print("Authors:", paper["authors"])
#         print("Year:", paper["publication_year"])
#         print("Date:", paper["publication_date"])
#         print("DOI:", paper["doi"])
#         print("Citations:", paper["citation_count"])
#         print("Venue:", paper["venue"])
#         print("PDF:", paper["pdf_url"])
#         print("Source ID:", paper["source_id"])


# if __name__ == "__main__":
#     asyncio.run(main())



# from tools import search_tavily


# async def main():

#     result = await search_tavily(
#         query="multi agent systems recent research trends",
#         max_results=3,
#     )

#     print("Success:", result["success"])
#     print("Count:", result["count"])

#     if result["error"]:
#         print("Error:", result["error"])

#     for source in result["web_sources"]:
#         print()
#         print("Title:", source["title"])
#         print("URL:", source["url"])
#         print("Content:", source["content"])


# if __name__ == "__main__":
#     asyncio.run(main())



from schemas import AcademicSource, SearchQuery
from utils import execute_search_queries


async def main():

    queries = [
        SearchQuery(
            query_id="q1",
            query="multi agent systems",
            purpose="Find academic papers on multi-agent systems",
            source=AcademicSource.ARXIV,
            priority=1,
        ),

        SearchQuery(
            query_id="q2",
            query="multi agent systems",
            purpose="Find scholarly metadata",
            source=AcademicSource.OPENALEX,
            priority=1,
        ),

        SearchQuery(
            query_id="q3",
            query="multi agent systems",
            purpose="Find DOI and publication metadata",
            source=AcademicSource.CROSSREF,
            priority=2,
        ),

        SearchQuery(
            query_id="q4",
            query="multi agent systems recent research trends",
            purpose="Find supporting web context",
            source=AcademicSource.TAVILY,
            priority=3,
        ),
    ]

    result = await execute_search_queries(
        search_queries=queries,
        max_results_per_query=2,
    )

    print("Overall success:", result["success"])
    print("Candidate papers:", result["paper_count"])
    print("Web sources:", result["web_source_count"])

    print("\nEXECUTIONS")

    for execution in result["executions"]:
        print(execution)

    print("\nERRORS")

    for error in result["errors"]:
        print(error)

    print("\nACADEMIC PAPERS")

    for paper in result["candidate_papers"]:
        print(
            paper["source"],
            "|",
            paper["title"],
        )

    print("\nWEB SOURCES")

    for source in result["web_sources"]:
        print(
            source["title"],
            "|",
            source["url"],
        )


if __name__ == "__main__":
    asyncio.run(main())
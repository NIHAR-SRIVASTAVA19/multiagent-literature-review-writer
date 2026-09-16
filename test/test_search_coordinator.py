import asyncio
import sys

# Windows' default console codec (cp1252) can't encode characters models
# commonly emit (em dashes, narrow no-break spaces, etc.), which crashes
# print() mid-run. Force UTF-8 stdout so output never depends on the
# terminal's active code page.
sys.stdout.reconfigure(encoding="utf-8")

from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService
from google.genai import types

from literature_review_writer.subagents.search_coordinator.agent import (
    search_coordinator,
)


APP_NAME = "search_coordinator_test"
USER_ID = "test_user"
SESSION_ID = "search_test_session"

DATABASE_URL = "sqlite+aiosqlite:///./data/adk_sessions.db"


async def main():

    session_service = DatabaseSessionService(
        db_url=DATABASE_URL
    )

    # Create a fresh test session
    try:
        await session_service.create_session(
            app_name=APP_NAME,
            user_id=USER_ID,
            session_id=SESSION_ID,
        )
    except Exception:
        # Session may already exist from a previous test.
        pass

    runner = Runner(
        agent=search_coordinator,
        app_name=APP_NAME,
        session_service=session_service,
    )

    test_message = """
Execute the following search queries exactly as provided.

Do not generate new queries.
Do not modify the queries.
Do not deduplicate, rank, or select papers.

Search queries:

[
    {
        "query_id": "q1",
        "query": "multi agent systems",
        "purpose": "Find academic papers about multi-agent systems",
        "source": "arxiv",
        "priority": 1
    },
    {
        "query_id": "q2",
        "query": "multi agent systems",
        "purpose": "Find academic papers about multi-agent systems",
        "source": "openalex",
        "priority": 1
    },
    {
        "query_id": "q3",
        "query": "multi agent systems",
        "purpose": "Find additional bibliographic records",
        "source": "crossref",
        "priority": 2
    },
    {
        "query_id": "q4",
        "query": "multi agent systems recent research trends",
        "purpose": "Find supporting web context",
        "source": "tavily",
        "priority": 2
    }
]

Use a maximum of 2 results per query.

Return the retrieved candidate papers,
web sources, execution information, and errors.
"""

    message = types.Content(
        role="user",
        parts=[
            types.Part(
                text=test_message
            )
        ],
    )

    print("\n==============================")
    print("SEARCH COORDINATOR TEST")
    print("==============================\n")

    async for event in runner.run_async(
        user_id=USER_ID,
        session_id=SESSION_ID,
        new_message=message,
    ):

        # Print final textual responses from the agent
        if event.content and event.content.parts:

            for part in event.content.parts:

                if getattr(part, "text", None):
                    print(part.text)


if __name__ == "__main__":
    asyncio.run(main())
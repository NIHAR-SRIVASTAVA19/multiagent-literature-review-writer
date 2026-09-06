import asyncio
import uuid

from google.adk import Runner
from google.adk.sessions import DatabaseSessionService
from google.genai import types

from config import APP_NAME, DATABASE_URL
from literature_review_writer import root_agent


# ============================================================
# PERSISTENT SESSION SERVICE
# ============================================================

session_service = DatabaseSessionService(
    db_url=DATABASE_URL
)


# ============================================================
# ADK RUNNER
# ============================================================

runner = Runner(
    agent=root_agent,
    app_name=APP_NAME,
    session_service=session_service,
)


# ============================================================
# SESSION MANAGEMENT
# ============================================================

async def get_or_create_session(
    user_id: str,
    session_id: str | None = None,
):
    """
    Retrieve an existing session for the user or create a new one.

    Parameters
    ----------
    user_id:
        Unique application-level user identifier.
        Later this will come from authenticated FastAPI users.

    session_id:
        Unique literature-review conversation/project identifier.
        If omitted, a new UUID is generated.
    """

    # --------------------------------------------------------
    # Try to retrieve an existing session
    # --------------------------------------------------------

    if session_id:
        existing_session = await session_service.get_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=session_id,
        )

        if existing_session is not None:
            return existing_session

    # --------------------------------------------------------
    # Create a new persistent session
    # --------------------------------------------------------

    new_session_id = session_id or str(uuid.uuid4())

    session = await session_service.create_session(
        app_name=APP_NAME,
        user_id=user_id,
        session_id=new_session_id,
        state={
            "current_stage": "initialized",
            "content_revision_round": 0,
            "citation_revision_round": 0,
        },
    )

    return session


# ============================================================
# AGENT EXECUTION
# ============================================================

async def run_agent(
    user_id: str,
    session_id: str,
    message: str,
    debug: bool = False,
) -> str | None:
    """
    Execute one user message against an existing ADK session.

    Returns the final textual response produced by the agent.
    """

    user_message = types.Content(
        role="user",
        parts=[
            types.Part(text=message)
        ],
    )

    final_response = None

    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=user_message,
    ):

        # ----------------------------------------------------
        # Debug output for Phase 1 development
        # ----------------------------------------------------

        if debug:
            print(
                f"[EVENT] "
                f"author={event.author} "
                f"final={event.is_final_response()}"
            )

        # ----------------------------------------------------
        # Print intermediate text while debugging
        # ----------------------------------------------------

        if debug and event.content and event.content.parts:
            for part in event.content.parts:
                text = getattr(part, "text", None)

                if text:
                    print(f"[TEXT] {text}")

        # ----------------------------------------------------
        # Capture final response
        # ----------------------------------------------------

        if event.is_final_response():
            if event.content and event.content.parts:

                text_parts = []

                for part in event.content.parts:
                    text = getattr(part, "text", None)

                    if text:
                        text_parts.append(text)

                if text_parts:
                    final_response = "\n".join(text_parts)

    return final_response


# ============================================================
# LOCAL DEVELOPMENT TEST
# ============================================================

async def main():
    """
    Temporary CLI entry point used during Phase 1.

    Later, FastAPI endpoints will call get_or_create_session()
    and run_agent() directly.
    """

    test_user_id = "local_test_user"

    # --------------------------------------------------------
    # Create a new persistent session
    # --------------------------------------------------------

    session = await get_or_create_session(
        user_id=test_user_id,
    )

    print(f"User ID: {test_user_id}")
    print(f"Session ID: {session.id}")

    # --------------------------------------------------------
    # Minimal Root Agent test
    # --------------------------------------------------------

    response = await run_agent(
        user_id=test_user_id,
        session_id=session.id,
        message=(
            "Briefly introduce yourself and explain what information "
            "you need from me before starting a literature review. "
            "Do not delegate to another agent yet."
        ),
        debug=True,
    )

    # --------------------------------------------------------
    # Final response
    # --------------------------------------------------------

    print("\n" + "=" * 60)
    print("FINAL RESPONSE")
    print("=" * 60)

    if response:
        print(response)
    else:
        print("No final response was returned.")


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    asyncio.run(main())
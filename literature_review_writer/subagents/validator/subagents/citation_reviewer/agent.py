from google.adk.agents import Agent
from dotenv import load_dotenv
from config import CITATION_REVIEWER_MODEL
from prompts import CITATION_REVIEWER_PROMPT

from tools import (
    verify_doi,
    verify_paper_metadata,
    verify_source_identity,
)

load_dotenv()


citation_reviewer = Agent(
    name="citation_reviewer",

    model=CITATION_REVIEWER_MODEL,

    description=(
        "Citation validation specialist responsible for verifying citation "
        "existence, bibliographic metadata, source identity, and citation-to-claim "
        "consistency using live scholarly verification tools."
    ),

    instruction=CITATION_REVIEWER_PROMPT,

    tools=[
        verify_doi,
        verify_paper_metadata,
        verify_source_identity,
    ],
)
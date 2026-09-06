from google.adk.agents import Agent
from dotenv import load_dotenv
from config import VALIDATOR_MODEL
from prompts import VALIDATOR_PROMPT

from .subagents import (
    content_reviewer,
    citation_reviewer,
)

load_dotenv()


validator = Agent(
    name="validator",

    model=VALIDATOR_MODEL,

    description=(
        "Validation coordinator responsible for controlling the sequential "
        "content-review and citation-review workflow for literature review drafts."
    ),

    instruction=VALIDATOR_PROMPT,

    sub_agents=[
        content_reviewer,
        citation_reviewer,
    ],

    tools=[],
)
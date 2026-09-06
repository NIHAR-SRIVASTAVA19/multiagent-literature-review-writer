from dotenv import load_dotenv
from google.adk.agents import Agent
from config import ROOT_MODEL

from prompts import LITERATURE_REVIEW_WRITER_PROMPT

from .subagents import (
    analysis_agent,
    search_coordinator,
    synthesizer,
    validator,
    writer,
)

load_dotenv()


root_agent = Agent(
    name="literature_review_writer",

    model=ROOT_MODEL,

    description=(
        "Root coordinator for an automated multi-agent literature review "
        "system that plans research, delegates retrieval, analysis, "
        "synthesis, writing, and validation."
    ),

    instruction=LITERATURE_REVIEW_WRITER_PROMPT,

    sub_agents=[
        search_coordinator,
        analysis_agent,
        synthesizer,
        writer,
        validator,
    ],
)
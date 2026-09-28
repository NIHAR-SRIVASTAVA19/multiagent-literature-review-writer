from google.adk.agents import Agent
from dotenv import load_dotenv
from config import WRITER_MODEL
from prompts import WRITER_PROMPT

from tools import build_literature_review_draft

load_dotenv()


writer = Agent(
    name="writer",

    model=WRITER_MODEL,

    description=(
        "Literature review writing specialist responsible for transforming "
        "validated synthesis, evidence, and citation metadata into a structured, "
        "coherent, and evidence-grounded literature review draft."
    ),

    instruction=WRITER_PROMPT,

    tools=[
        build_literature_review_draft,
    ],
)
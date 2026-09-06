from google.adk.agents import Agent
from dotenv import load_dotenv
from config import CONTENT_REVIEWER_MODEL
from prompts import CONTENT_REVIEWER_PROMPT

load_dotenv()


content_reviewer = Agent(
    name="content_reviewer",

    model=CONTENT_REVIEWER_MODEL,

    description=(
        "Scientific content reviewer responsible for evaluating whether the "
        "literature review draft is coherent, evidence-grounded, complete, "
        "and faithful to the underlying research synthesis."
    ),

    instruction=CONTENT_REVIEWER_PROMPT,

    tools=[],
)
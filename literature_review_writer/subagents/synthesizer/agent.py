from google.adk.agents import Agent
from dotenv import load_dotenv
from config import SYNTHESIZER_MODEL
from prompts import SYNTHESIZER_PROMPT

load_dotenv()


synthesizer = Agent(
    name="synthesizer",

    model=SYNTHESIZER_MODEL,

    description=(
        "Cross-paper synthesis specialist responsible for comparing analyzed "
        "research papers, identifying themes, trends, contradictions, strengths, "
        "weaknesses, and evidence-supported research gaps."
    ),

    instruction=SYNTHESIZER_PROMPT,
)
from google.adk.agents import Agent
from dotenv import load_dotenv
from config import SEARCH_MODEL
from prompts import SEARCH_COORDINATOR_PROMPT
from tools import (
    search_arxiv,
    search_semantic_scholar,
    search_openalex,
    search_crossref,
    search_tavily

)
load_dotenv()

search_coordinator=Agent(
    name="search_coordinator",
    model=SEARCH_MODEL,
    description= "Search execution specialist responsible for retrieving candidate research papers and relevant web context from live academic and web sources using search queries provided by the Root Agent.",
    instruction=SEARCH_COORDINATOR_PROMPT,
    tools=[
    search_arxiv,
    search_semantic_scholar,
    search_openalex,
    search_crossref,
    search_tavily,
]
)
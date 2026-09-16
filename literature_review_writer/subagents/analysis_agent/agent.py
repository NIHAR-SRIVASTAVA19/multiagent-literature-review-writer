from google.adk.agents import Agent
from dotenv import load_dotenv
from config import ANALYSIS_MODEL
from prompts import ANALYSIS_AGENT_PROMPT

from tools import (
    deduplicate_papers,
    rerank_papers,
    select_papers,
    download_pdf,
    extract_paper_segments,
    analyze_paper_with_vlm,
)

load_dotenv()


analysis_agent = Agent(
    name="analysis_agent",

    model=ANALYSIS_MODEL,

    description=(
        "Paper analysis specialist responsible for deduplicating and re-ranking "
        "candidate research papers, selecting relevant papers, preparing their PDFs "
        "for vision analysis, and producing structured evidence-grounded paper analyses."
    ),

    instruction=ANALYSIS_AGENT_PROMPT,

    tools=[
        deduplicate_papers,
        rerank_papers,
        select_papers,
        download_pdf,
        extract_paper_segments,
        analyze_paper_with_vlm,
    ],
)
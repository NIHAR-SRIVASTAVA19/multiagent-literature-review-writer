import os

from dotenv import load_dotenv
from google.adk.models.lite_llm import LiteLlm


load_dotenv()

# ============================================================
# API URLS
# ============================================================

ARXIV_API_URL = os.getenv(
    "ARXIV_API_URL",
    "https://export.arxiv.org/api/query",
)

SEMANTIC_SCHOLAR_API_URL = os.getenv(
    "SEMANTIC_SCHOLAR_API_URL",
    "https://api.semanticscholar.org/graph/v1/paper/search",
)

OPENALEX_API_URL = os.getenv(
    "OPENALEX_API_URL",
    "https://api.openalex.org/works",
)

OPENALEX_MAILTO = os.getenv(
    "OPENALEX_MAILTO"
)

CROSSREF_API_URL = os.getenv(
    "CROSSREF_API_URL",
    "https://api.crossref.org/works",
)

CROSSREF_MAILTO = os.getenv(
    "CROSSREF_MAILTO"
)

TAVILY_API_URL = os.getenv(
    "TAVILY_API_URL",
    "https://api.tavily.com/search",
)

TAVILY_API_KEY = os.getenv(
    "TAVILY_API_KEY"
)

# ============================================================
# PAPER ARTIFACT STORAGE
# ============================================================

# Root directory under which each paper gets its own folder:
#
#   data/<paper_id>/<paper_id>.pdf
#   data/<paper_id>/pages/page_0001.png
#
# Keeping a paper's PDF and its rendered pages together (instead of
# separate data/pdfs/ and data/pages/ trees) keeps every artifact
# for one paper in one place.
PAPERS_DIR = os.getenv(
    "PAPERS_DIR",
    "data",
)

# 50 MB. Selected research-paper PDFs are almost always well under
# this; it exists to stop a bad URL or paywall interstitial from
# streaming an unbounded response to disk.
MAX_PDF_DOWNLOAD_BYTES = int(
    os.getenv(
        "MAX_PDF_DOWNLOAD_BYTES",
        str(50 * 1024 * 1024),
    )
)

# Resolution used when cropping table regions out of the original PDF
# (extract_paper_segments()). Marker's own table->markdown conversion
# is unreliable on complex scientific tables, so tables are cropped
# as images and sent to the VLM directly instead.
TABLE_CROP_DPI = int(
    os.getenv(
        "TABLE_CROP_DPI",
        "150",
    )
)

# Max time allowed for a single marker_single subprocess call
# (extract_paper_segments()).
MARKER_TIMEOUT_SECONDS = int(
    os.getenv(
        "MARKER_TIMEOUT_SECONDS",
        "300",
    )
)

# ============================================================
# DATABASE CONFIGURATION
# ============================================================

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite+aiosqlite:///./data/adk_sessions.db",
)


# ============================================================
# NVIDIA NIM CONFIGURATION
# ============================================================

NVIDIA_NIM_API_KEY = os.getenv("NVIDIA_NIM_API_KEY")

NVIDIA_NIM_API_BASE = os.getenv(
    "NVIDIA_NIM_API_BASE",
    "https://integrate.api.nvidia.com/v1",
)


if not NVIDIA_NIM_API_KEY:
    raise ValueError(
        "NVIDIA_NIM_API_KEY is missing. "
        "Add it to your .env file."
    )


# ============================================================
# MODEL FACTORY
# ============================================================

def nvidia_model(model_name: str) -> LiteLlm:
    """
    Create a Google ADK LiteLLM model configured to use
    NVIDIA NIM's hosted inference endpoint.
    """

    return LiteLlm(
        model=f"nvidia_nim/{model_name}",
        api_key=NVIDIA_NIM_API_KEY,
        api_base=NVIDIA_NIM_API_BASE,
    )


# ============================================================
# MODEL ASSIGNMENTS
# ============================================================

ROOT_MODEL = nvidia_model(
    os.getenv(
        "ROOT_MODEL",
        "nvidia/nemotron-3.5-lightning-30b-a3b",
    )
)


SEARCH_MODEL = nvidia_model(
    os.getenv(
        "SEARCH_MODEL",
        "nvidia/nemotron-3.5-lightning-30b-a3b",
    )
)


ANALYSIS_MODEL_NAME = os.getenv(
    "ANALYSIS_MODEL",
    # Reasoning/orchestration only (tool calls, judgment) - matches
    # the same workhorse reasoning model used elsewhere (Root, Search
    # Coordinator, Validator). Vision calls use VLM_MODEL_NAME below,
    # not this - kimi-k3's hosted vision endpoint was measured at
    # 7+ minutes for a single request (still not returned when
    # aborted); llama-3.2-11b-vision-instruct returned an accurate
    # answer in ~15s on the same infrastructure.
    "nvidia/nemotron-3.5-lightning-30b-a3b",
)

ANALYSIS_MODEL = nvidia_model(ANALYSIS_MODEL_NAME)

# Dedicated vision-language model for describe_image_with_vlm() in
# tools.py - deliberately separate from ANALYSIS_MODEL_NAME (see
# note above). No ADK Agent uses this directly; it's passed straight
# into litellm.acompletion() by the vision tools themselves.
VLM_MODEL_NAME = os.getenv(
    "VLM_MODEL",
    "meta/llama-3.2-11b-vision-instruct",
)


SYNTHESIZER_MODEL = nvidia_model(
    os.getenv(
        "SYNTHESIZER_MODEL",
        "nvidia/nemotron-3-ultra-550b-a55b",
    )
)


WRITER_MODEL = nvidia_model(
    os.getenv(
        "WRITER_MODEL",
        "deepseek-ai/deepseek-v4-pro-0813",
    )
)


VALIDATOR_MODEL = nvidia_model(
    os.getenv(
        "VALIDATOR_MODEL",
        "nvidia/nemotron-3.5-lightning-30b-a3b",
    )
)


CONTENT_REVIEWER_MODEL = nvidia_model(
    os.getenv(
        "CONTENT_REVIEWER_MODEL",
        "nvidia/nemotron-3-ultra-550b-a55b",
    )
)


CITATION_REVIEWER_MODEL = nvidia_model(
    os.getenv(
        "CITATION_REVIEWER_MODEL",
        "nvidia/nemotron-3.5-lightning-30b-a3b",
    )
)


# ============================================================
# APPLICATION CONFIGURATION
# ============================================================

APP_NAME = "multiagent_research_system"

MAX_CONTENT_REVISION_ROUNDS = 3

MAX_CITATION_REVISION_ROUNDS = 3
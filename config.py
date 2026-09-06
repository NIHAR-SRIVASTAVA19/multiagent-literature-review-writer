import os

from dotenv import load_dotenv
from google.adk.models.lite_llm import LiteLlm


load_dotenv()

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


ANALYSIS_MODEL = nvidia_model(
    os.getenv(
        "ANALYSIS_MODEL",
        "moonshotai/kimi-k3",
    )
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
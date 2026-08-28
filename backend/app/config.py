"""
Central configuration for HelpBot.

All model/provider choices are read from environment variables so the
same code can run locally or on the deployed EC2 instance without
code changes. Only free-tier providers are supported, per the
assignment's tech-stack constraint.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# --- LLM provider -----------------------------------------------------
# Supported: "groq" (default). Groq's free tier is fast enough for an
# agentic loop with several LLM calls per request, which is why it was
# chosen over e.g. OpenRouter free models (much lower rate limits) or
# Gemini free tier (stricter daily quotas at the time of writing).
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

# Low-temperature everywhere: this is a helpdesk assistant, not a
# creative writer. We want consistent routing/classification behavior.
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))

# --- Retrieval ----------------------------------------------------------
# Confidence threshold below which the RAG agent hands the query back
# to the router so it becomes a ticket instead of a guess.
RAG_CONFIDENCE_THRESHOLD = float(os.getenv("RAG_CONFIDENCE_THRESHOLD", "0.55"))

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
DOCS_DIR = os.path.join(DATA_DIR, "docs")
TICKETS_JSON = os.path.join(DATA_DIR, "tickets.json")
TICKETS_DB = os.path.join(DATA_DIR, "tickets.db")


def get_llm(temperature: float | None = None):
    """Factory so agents never import a specific provider directly."""
    temp = LLM_TEMPERATURE if temperature is None else temperature
    if LLM_PROVIDER == "groq":
        from langchain_groq import ChatGroq
        if not GROQ_API_KEY:
            raise RuntimeError(
                "GROQ_API_KEY is not set. Get a free key at "
                "https://console.groq.com/keys and put it in backend/.env"
            )
        llm = ChatGroq(model=GROQ_MODEL, temperature=temp, api_key=GROQ_API_KEY)
        # The RAG agent sends the whole knowledge-base corpus on every call,
        # which is token-heavy relative to Groq's free-tier per-minute limit
        # for larger models -- a burst of requests (e.g. the eval script) can
        # trip a transient 429. Retry with backoff rather than failing the
        # whole request outright.
        return llm.with_retry(stop_after_attempt=4, wait_exponential_jitter=True)
    raise ValueError(f"Unsupported LLM_PROVIDER: {LLM_PROVIDER}")

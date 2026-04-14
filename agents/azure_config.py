import os
import threading
from typing import Optional, List, Dict, Any
from openai import AzureOpenAI
from utils.logger import get_logger
import settings_store

logger = get_logger("agents.azure_config")


def _setting(key: str, default=None):
    """Get a config value: runtime settings override environment variables."""
    val = settings_store.get(key)
    if val:
        return val
    return os.getenv(key, default)


_lock = threading.RLock()
_chat_client = None
_embedding_client = None


def reset_clients():
    """Invalidate all cached Azure clients so they're recreated with new settings."""
    global _chat_client, _embedding_client
    with _lock:
        _chat_client = None
        _embedding_client = None
    logger.info("All cached Azure/OpenAI clients have been reset")


# ---------------------------------------------------------------------------
# Agent definitions — used as system prompts for chat completions
# ---------------------------------------------------------------------------
AGENT_DEFINITIONS = {
    "pico": {
        "name": "ai4sr-pico",
        "instructions": """You are a PICO expansion specialist for systematic literature reviews.
Your role is to expand PICO (Population, Intervention, Comparison, Outcome) frameworks into search queries.
Given a PICO description, you generate:
1. A clear summary of the review question
2. Boolean search queries for PubMed (with field tags like [tiab], [mh])
3. Simple text queries for OpenAlex
4. Expanded keywords for each PICO component
Always respond in valid JSON format."""
    },
    "screener": {
        "name": "ai4sr-screener",
        "instructions": """You are an expert paper screening agent for systematic literature reviews.
Your role is to evaluate if papers should be included based on title and abstract.
Assess relevance to the research question and PICO criteria.
Return decisions as: include, maybe, or exclude with a relevance score (0-100).
When key information is missing, prefer 'maybe' over 'exclude'.
Always respond in valid JSON format with keys: decision, score."""
    },
    "cot-screener": {
        "name": "ai4sr-cot-screener",
        "instructions": """You are an expert systematic review researcher performing detailed PICO analysis.
Think step-by-step through each PICO component:
- P (Population): Who is studied?
- I (Intervention): What is the main intervention or exposure?
- C (Comparator): What is the comparison or control?
- O (Outcomes): What outcomes are measured?
Provide thorough rationale for your inclusion decisions.
Always respond in valid JSON format with keys: decision, rationale."""
    },
    "keyword": {
        "name": "ai4sr-keyword",
        "instructions": """You are a keyword expansion specialist for systematic literature reviews.
Your role is to expand research questions into comprehensive keyword lists and Boolean search strings.
Generate synonyms, related terms, and MeSH-compatible terms.
Create both generic Boolean queries and PubMed-specific queries.
Always respond in valid JSON format."""
    },
    "rag": {
        "name": "ai4sr-rag",
        "instructions": """You are an expert systematic review researcher providing answers based on retrieved literature.
Synthesize information from multiple papers to answer questions comprehensively.
Cite specific papers when making claims.
Acknowledge limitations and gaps in the evidence.
Provide balanced, evidence-based responses."""
    },
    "review": {
        "name": "ai4sr-review",
        "instructions": """You are a paper review agent extracting structured information from research papers.
Extract and summarize:
- Population studied
- Intervention/treatment
- Comparator/control
- Outcomes measured
- Main findings
- Sample size
Be precise and accurate. Always respond in valid JSON format."""
    },
    "cold-start": {
        "name": "ai4sr-cold-start",
        "instructions": """You are a cold-start screening agent for systematic reviews.
Your role is to label initial papers to seed the active learning process.
Evaluate papers against PICO criteria and decide INCLUDE or EXCLUDE.
Provide clear rationale for each decision.
Always respond in valid JSON format with keys: decision, rationale."""
    },
    "default": {
        "name": "ai4sr-agent",
        "instructions": """You are an AI assistant helping with systematic literature reviews.
Provide clear, accurate, and concise responses based on the context provided.
Always respond in valid JSON format when requested."""
    }
}


# ---------------------------------------------------------------------------
# Client construction helpers
# ---------------------------------------------------------------------------

def _get_azure_credential():
    """Get Azure credential — service principal if available, else CLI, else default."""
    tenant_id = _setting("MICROSOFT_TENANT_ID")
    client_id = _setting("MICROSOFT_CLIENT_ID")
    client_secret = _setting("MICROSOFT_CLIENT_SECRET")

    if tenant_id and client_id and client_secret:
        from azure.identity import ClientSecretCredential
        return ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret
        )

    import shutil
    if shutil.which("az") is not None:
        from azure.identity import AzureCliCredential
        return AzureCliCredential()

    from azure.identity import DefaultAzureCredential
    return DefaultAzureCredential()


def _resolve_azure_endpoint() -> str:
    """Return the direct Azure OpenAI endpoint for chat/embeddings.

    Priority:
    1. AZURE_OPENAI_DIRECT_ENDPOINT (explicit override)
    2. Derived from AZURE_EXISTING_AIPROJECT_ENDPOINT
    """
    direct = _setting("AZURE_OPENAI_DIRECT_ENDPOINT")
    if direct:
        return direct.rstrip("/")

    ai_endpoint = _setting("AZURE_EXISTING_AIPROJECT_ENDPOINT")
    if not ai_endpoint:
        raise ValueError(
            "Azure not configured. Set AZURE_OPENAI_DIRECT_ENDPOINT or "
            "AZURE_EXISTING_AIPROJECT_ENDPOINT in Settings or .env file."
        )

    # Convert AI Projects endpoint → direct Azure OpenAI endpoint
    # e.g. https://oai-ai4sr.services.ai.azure.com/api/projects/...
    #    → https://oai-ai4sr.cognitiveservices.azure.com
    if "services.ai.azure.com" in ai_endpoint:
        try:
            from urllib.parse import urlparse
            hostname = urlparse(ai_endpoint).hostname
            if hostname:
                subdomain = hostname.split(".")[0]
                return f"https://{subdomain}.cognitiveservices.azure.com"
        except Exception:
            pass

    # Best-effort conversion
    try:
        return (
            ai_endpoint
            .replace("services.ai.azure.com", "cognitiveservices.azure.com")
            .split("/api/")[0]
            .rstrip("/")
        )
    except Exception:
        raise ValueError(
            "Could not derive Azure OpenAI endpoint. "
            "Please set AZURE_OPENAI_DIRECT_ENDPOINT explicitly."
        )


def _build_azure_openai_client() -> AzureOpenAI:
    """Build an AzureOpenAI client using token-based auth."""
    endpoint = _resolve_azure_endpoint()
    credential = _get_azure_credential()
    token_scope = "https://cognitiveservices.azure.com/.default"

    client = AzureOpenAI(
        azure_endpoint=endpoint,
        azure_ad_token_provider=lambda: credential.get_token(token_scope).token,
        api_version=_setting("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
    )
    logger.info("AzureOpenAI client created for endpoint %s", endpoint)
    return client


def _get_chat_client():
    """Return a cached AzureOpenAI client for chat completions."""
    global _chat_client
    if _chat_client is not None:
        return _chat_client
    with _lock:
        if _chat_client is None:
            _chat_client = _build_azure_openai_client()
        return _chat_client


# ---------------------------------------------------------------------------
# Embedding client (may use a different endpoint / deployment)
# ---------------------------------------------------------------------------

def get_embedding_client():
    """Return a cached AzureOpenAI client for embeddings."""
    global _embedding_client
    if _embedding_client is not None:
        return _embedding_client
    with _lock:
        if _embedding_client is None:
            _embedding_client = _build_azure_openai_client()
        return _embedding_client


def get_openai_embedding_client():
    """Return an OpenAI client for embeddings (fallback when Azure unavailable)."""
    openai_key = _setting("OPENAI_KEY")
    if not openai_key:
        raise ValueError("OPENAI_KEY not set — cannot use OpenAI embeddings fallback")
    from openai import OpenAI
    return OpenAI(api_key=openai_key)


def _get_openai_chat_client():
    """Return an OpenAI client for chat completions (fallback when Azure unavailable)."""
    openai_key = _setting("OPENAI_KEY")
    if not openai_key:
        raise ValueError("OPENAI_KEY not set — cannot use OpenAI chat fallback")
    from openai import OpenAI
    return OpenAI(api_key=openai_key)


# ---------------------------------------------------------------------------
# Chat completion — the single entry point all agents call
# ---------------------------------------------------------------------------

def chat_completion(
    messages: List[Dict[str, str]],
    deployment_name: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    agent_type: str = "default",
    timeout: Optional[float] = None,
    **kwargs,
) -> str:
    """Send a chat completion request to Azure OpenAI, with OpenAI fallback.

    The *agent_type* selects a system prompt from AGENT_DEFINITIONS.
    All other parameters (temperature, max_tokens, etc.) are forwarded to the
    underlying ``chat.completions.create`` call.

    Args:
        messages: List of message dicts with 'role' and 'content'.
        deployment_name: Model/deployment to use (default: env config).
        temperature: Sampling temperature.
        max_tokens: Max response tokens (None = model default).
        agent_type: Which system prompt to inject.
        timeout: Per-request timeout in seconds.

    Returns:
        The assistant's response text.
    """
    if deployment_name is None:
        deployment_name = _setting("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4.1")

    # Inject system prompt from agent definitions
    agent_def = AGENT_DEFINITIONS.get(agent_type, AGENT_DEFINITIONS["default"])
    full_messages = [{"role": "system", "content": agent_def["instructions"]}] + messages

    call_kwargs: Dict[str, Any] = {
        "model": deployment_name,
        "messages": full_messages,
        "temperature": temperature,
    }
    if max_tokens is not None:
        call_kwargs["max_tokens"] = max_tokens
    if timeout is not None:
        call_kwargs["timeout"] = timeout

    # --- Try Azure first ---
    azure_error_str = None
    try:
        client = _get_chat_client()
        logger.debug("Calling Azure chat.completions (model=%s, agent=%s)", deployment_name, agent_type)
        response = client.chat.completions.create(**call_kwargs)
        text = response.choices[0].message.content
        if not text:
            raise ValueError("Empty response from Azure OpenAI")
        logger.debug("Azure response received (%d chars)", len(text))
        return text
    except Exception as e:
        azure_error_str = str(e)
        logger.warning("Azure chat completion failed: %s", azure_error_str)

    # --- Fallback to OpenAI ---
    openai_key = _setting("OPENAI_KEY")
    if not openai_key:
        raise RuntimeError(
            f"Azure chat completion failed and OPENAI_KEY not set for fallback.\n"
            f"Azure error: {azure_error_str}"
        )

    try:
        logger.debug("Falling back to OpenAI for chat completion")
        openai_client = _get_openai_chat_client()
        # Map Azure deployment names to OpenAI model names
        openai_model = deployment_name
        if openai_model in ("gpt-4o-mini",):
            pass  # same name works
        response = openai_client.chat.completions.create(**{**call_kwargs, "model": openai_model})
        text = response.choices[0].message.content
        if not text:
            raise ValueError("Empty response from OpenAI")
        logger.debug("OpenAI fallback response received (%d chars)", len(text))
        return text
    except Exception as openai_error:
        raise RuntimeError(
            f"Both Azure and OpenAI chat completions failed.\n"
            f"Azure error: {azure_error_str}\n"
            f"OpenAI error: {str(openai_error)}"
        ) from openai_error


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------

def get_embedding(text: str, deployment_name: Optional[str] = None) -> List[float]:
    """Get embedding for a single text. Tries Azure, falls back to OpenAI."""
    if not text or not text.strip():
        raise ValueError("Text cannot be empty for embedding")

    if deployment_name is None:
        deployment_name = _setting("AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME", "text-embedding-3-small")

    # Try Azure
    try:
        client = get_embedding_client()
        response = client.embeddings.create(model=deployment_name, input=text)
        if not response.data:
            raise ValueError("Empty response from Azure embedding API")
        return response.data[0].embedding
    except Exception as azure_err:
        logger.debug("Azure embedding failed: %s", azure_err)

    # Fallback to OpenAI
    openai_key = _setting("OPENAI_KEY")
    if not openai_key:
        raise RuntimeError(f"Azure embedding failed and OPENAI_KEY not set: {azure_err}")

    try:
        openai_client = get_openai_embedding_client()
        response = openai_client.embeddings.create(model=deployment_name, input=text)
        if not response.data:
            raise ValueError("Empty response from OpenAI embedding API")
        return response.data[0].embedding
    except Exception as openai_err:
        raise RuntimeError(
            f"Both Azure and OpenAI embeddings failed. "
            f"Azure: {azure_err}. OpenAI: {openai_err}"
        ) from openai_err


def get_embeddings_batch(texts: List[str], deployment_name: Optional[str] = None) -> List[List[float]]:
    """Get embeddings for multiple texts. Tries Azure, falls back to OpenAI."""
    if not texts:
        return []

    if deployment_name is None:
        deployment_name = _setting("AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME", "text-embedding-3-small")

    valid_texts = [t for t in texts if t and t.strip()]
    if not valid_texts:
        raise ValueError("No valid texts provided for embedding")

    # Try Azure
    try:
        client = get_embedding_client()
        response = client.embeddings.create(model=deployment_name, input=valid_texts)
        if not response.data or len(response.data) != len(valid_texts):
            raise ValueError(f"Expected {len(valid_texts)} embeddings, got {len(response.data) if response.data else 0}")
        return [item.embedding for item in response.data]
    except Exception as azure_err:
        logger.debug("Azure batch embedding failed: %s", azure_err)

    # Fallback to OpenAI
    openai_key = _setting("OPENAI_KEY")
    if not openai_key:
        raise RuntimeError(f"Azure embedding failed and OPENAI_KEY not set: {azure_err}")

    try:
        openai_client = get_openai_embedding_client()
        response = openai_client.embeddings.create(model=deployment_name, input=valid_texts)
        if not response.data or len(response.data) != len(valid_texts):
            raise ValueError(f"Expected {len(valid_texts)} embeddings from OpenAI, got {len(response.data) if response.data else 0}")
        return [item.embedding for item in response.data]
    except Exception as openai_err:
        raise RuntimeError(
            f"Both Azure and OpenAI embeddings failed. "
            f"Azure: {azure_err}. OpenAI: {openai_err}"
        ) from openai_err


# ---------------------------------------------------------------------------
# Backward-compatible aliases (used by some imports)
# ---------------------------------------------------------------------------

def get_azure_client():
    """Alias for _get_chat_client() — backward compatibility."""
    return _get_chat_client()

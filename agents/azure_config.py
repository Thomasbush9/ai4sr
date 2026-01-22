import os
import threading
from typing import Optional, List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from azure.identity import DefaultAzureCredential, ClientSecretCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition
from openai import AzureOpenAI

# Use RLock (reentrant lock) to avoid deadlock when get_azure_client() calls get_project_client()
_azure_client_lock = threading.RLock()
_project_client = None
_openai_client = None
_agents: Dict[str, Any] = {}  # Cache for multiple agents

# Thread-local storage for clients to avoid issues in Flask's threading model
_thread_local = threading.local()

# Cache for direct Azure OpenAI client (for embeddings)
_embedding_client = None

# Agent definitions with specialized instructions
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


def get_credential():
    """Get Azure credential - use service principal if available, else DefaultAzureCredential."""
    tenant_id = os.getenv("MICROSOFT_TENANT_ID")
    client_id = os.getenv("MICROSOFT_CLIENT_ID")
    client_secret = os.getenv("MICROSOFT_CLIENT_SECRET")

    if tenant_id and client_id and client_secret:
        return ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret
        )
    else:
        return DefaultAzureCredential()


def get_project_client() -> AIProjectClient:
    """Get Azure AI Project client with credentials."""
    global _project_client
    
    # Double-check pattern to avoid lock contention
    if _project_client is not None:
        print(f"DEBUG: Using existing project client (cached)", flush=True)
        return _project_client

    print(f"DEBUG: Acquiring lock to create project client...", flush=True)
    with _azure_client_lock:
        print(f"DEBUG: Lock acquired for project client, checking if still None...", flush=True)
        # Double-check again inside lock
        if _project_client is not None:
            print(f"DEBUG: Project client created by another thread, returning cached", flush=True)
            return _project_client
        
        try:
            endpoint = os.getenv("AZURE_EXISTING_AIPROJECT_ENDPOINT")

            if not endpoint:
                raise ValueError(
                    "Azure AI Project not configured. "
                    "Please set AZURE_EXISTING_AIPROJECT_ENDPOINT environment variable."
                )

            print(f"DEBUG: Creating Azure AI Project client with endpoint: {endpoint[:50]}...", flush=True)
            import time
            start = time.time()
            credential = get_credential()
            elapsed = time.time() - start
            print(f"DEBUG: Credential obtained in {elapsed:.2f}s, creating AIProjectClient...", flush=True)
            
            start = time.time()
            _project_client = AIProjectClient(
                endpoint=endpoint,
                credential=credential
            )
            elapsed = time.time() - start
            print(f"DEBUG: AIProjectClient created successfully in {elapsed:.2f}s", flush=True)
        except Exception as e:
            print(f"ERROR: Failed to create project client: {e}", flush=True)
            import traceback
            traceback.print_exc()
            raise

    return _project_client


def _extract_direct_endpoint(ai_project_endpoint: str) -> str:
    """Extract direct Azure OpenAI endpoint from AI Projects endpoint.
    
    Converts: https://xxx.services.ai.azure.com/api/projects/...
    To:      https://xxx.cognitiveservices.azure.com
    
    Args:
        ai_project_endpoint: AI Projects endpoint URL
        
    Returns:
        Direct Azure OpenAI endpoint URL
    """
    # First, check if explicitly set in environment
    direct_endpoint = os.getenv("AZURE_OPENAI_DIRECT_ENDPOINT")
    if direct_endpoint:
        return direct_endpoint.rstrip('/')
    
    # Try to extract the base domain and convert to cognitiveservices
    if "services.ai.azure.com" in ai_project_endpoint:
        # Extract the subdomain (e.g., "oai-ai4sr" from "https://oai-ai4sr.services.ai.azure.com/...")
        try:
            from urllib.parse import urlparse
            parsed = urlparse(ai_project_endpoint)
            hostname = parsed.hostname
            if hostname:
                subdomain = hostname.split('.')[0]
                return f"https://{subdomain}.cognitiveservices.azure.com"
        except Exception:
            pass
    
    # Last resort: try to construct from AI Projects endpoint
    # This is a best-effort conversion
    try:
        return ai_project_endpoint.replace("services.ai.azure.com", "cognitiveservices.azure.com").split("/api/")[0].rstrip('/')
    except Exception:
        # If all else fails, raise an error with helpful message
        raise ValueError(
            "Could not determine direct Azure OpenAI endpoint. "
            "Please set AZURE_OPENAI_DIRECT_ENDPOINT environment variable "
            "(e.g., https://oai-ai4sr.cognitiveservices.azure.com)"
        )


def get_embedding_client():
    """Get direct Azure OpenAI client for embeddings (bypasses AI Projects API).
    
    This uses the direct Azure OpenAI endpoint which is required for embeddings
    when the deployment is a GlobalStandard type.
    
    Returns:
        AzureOpenAI client configured for direct endpoint access
    """
    global _embedding_client
    
    # Check thread-local storage first
    if hasattr(_thread_local, 'embedding_client') and _thread_local.embedding_client is not None:
        return _thread_local.embedding_client
    
    # Check global cache
    if _embedding_client is not None:
        return _embedding_client
    
    with _azure_client_lock:
        # Double-check after acquiring lock
        if _embedding_client is not None:
            return _embedding_client
        
        try:
            # Get the direct endpoint
            ai_project_endpoint = os.getenv("AZURE_EXISTING_AIPROJECT_ENDPOINT")
            if not ai_project_endpoint:
                raise ValueError("AZURE_EXISTING_AIPROJECT_ENDPOINT not set")
            
            direct_endpoint = _extract_direct_endpoint(ai_project_endpoint)
            print(f"DEBUG: Creating direct Azure OpenAI client for embeddings at {direct_endpoint}", flush=True)
            
            # Get credential
            credential = get_credential()
            
            # Create direct Azure OpenAI client
            # For embeddings, we use the direct endpoint, not the AI Projects endpoint
            # Get token synchronously for the token provider
            token_scope = "https://cognitiveservices.azure.com/.default"
            
            def get_token():
                """Get Azure AD token for Cognitive Services."""
                return credential.get_token(token_scope).token
            
            _embedding_client = AzureOpenAI(
                azure_endpoint=direct_endpoint,
                azure_ad_token_provider=get_token,
                api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
            )
            
            # Store in thread-local for Flask
            try:
                from flask import has_request_context
                if has_request_context():
                    _thread_local.embedding_client = _embedding_client
            except ImportError:
                pass
            
            print(f"DEBUG: Direct Azure OpenAI client created successfully", flush=True)
            return _embedding_client
            
        except Exception as e:
            print(f"ERROR: Failed to create direct Azure OpenAI client: {e}", flush=True)
            import traceback
            traceback.print_exc()
            # Fall back to AI Projects client if direct client fails
            print(f"DEBUG: Falling back to AI Projects client for embeddings", flush=True)
            return get_azure_client()


def get_or_create_agent(agent_type: str = "default"):
    """Get or create a specialized AI4SR agent.
    
    Agents are created automatically on first use. You do NOT need to manually create them in Azure.
    
    Args:
        agent_type: One of 'pico', 'screener', 'cot-screener', 'keyword', 'rag', 'review', 'cold-start', 'default'
        
    Returns:
        Agent object from Azure AI Foundry
        
    Raises:
        ValueError: If agent_type is invalid
        Exception: If agent creation fails (check Azure permissions and configuration)
    """
    global _agents

    if agent_type not in AGENT_DEFINITIONS:
        raise ValueError(f"Invalid agent_type: {agent_type}. Must be one of: {list(AGENT_DEFINITIONS.keys())}")

    if agent_type not in _agents:
        with _azure_client_lock:
            if agent_type not in _agents:
                try:
                    project_client = get_project_client()
                    model_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini")

                    # Get agent definition
                    agent_def = AGENT_DEFINITIONS.get(agent_type, AGENT_DEFINITIONS["default"])

                    print(f"DEBUG: Creating Azure agent '{agent_def['name']}' (type: {agent_type})...", flush=True)
                    
                    # Create agent directly - don't use ThreadPoolExecutor in Flask
                    # The Azure SDK client should handle timeouts internally
                    print(f"DEBUG: Creating agent directly (no thread pool)...", flush=True)
                    try:
                        _agents[agent_type] = project_client.agents.create_version(
                            agent_name=agent_def["name"],
                            definition=PromptAgentDefinition(
                                model=model_deployment,
                                instructions=agent_def["instructions"]
                            )
                        )
                        print(f"DEBUG: Successfully created agent '{agent_def['name']}'", flush=True)
                    except Exception as create_error:
                        error_msg = f"Agent creation failed: {str(create_error)}"
                        print(f"ERROR: {error_msg}", flush=True)
                        # Check if it took too long (rough check)
                        print("Possible causes:", flush=True)
                        print("  1. Azure AI Foundry is slow or unresponsive", flush=True)
                        print("  2. Network connectivity issues", flush=True)
                        print("  3. Stuck pipeline runs in Azure Portal (cancel them)", flush=True)
                        raise Exception(error_msg) from create_error
                        
                except Exception as e:
                    error_msg = f"Failed to create Azure agent '{agent_def.get('name', agent_type)}': {str(e)}"
                    print(f"ERROR: {error_msg}", flush=True)
                    print("Please ensure:", flush=True)
                    print("  1. AZURE_EXISTING_AIPROJECT_ENDPOINT is set correctly", flush=True)
                    print("  2. You are authenticated with Azure (az login)", flush=True)
                    print("  3. You have permissions to create agents in Azure AI Foundry", flush=True)
                    raise Exception(error_msg) from e

    return _agents[agent_type]


def get_azure_client():
    """Get OpenAI client from Azure AI Project with timeout configuration.
    
    Uses thread-local storage in Flask to avoid threading issues.
    """
    # Check thread-local storage first (for Flask threading)
    if hasattr(_thread_local, 'openai_client') and _thread_local.openai_client is not None:
        print(f"DEBUG: Using thread-local OpenAI client (cached)", flush=True)
        return _thread_local.openai_client
    
    # Fall back to global cache for single-threaded environments
    global _openai_client
    if _openai_client is not None:
        print(f"DEBUG: Using global OpenAI client (cached)", flush=True)
        return _openai_client
    
    print(f"DEBUG: Creating new OpenAI client (not cached)", flush=True)
    
    # Create new client - don't cache in Flask to avoid threading issues
    # In single-threaded test scripts, we can use global cache
    try:
        print(f"DEBUG: Getting project client...", flush=True)
        project_client = get_project_client()
        print(f"DEBUG: Project client obtained, calling get_openai_client()...", flush=True)
        
        # This call might hang - add detailed logging
        import time
        start = time.time()
        
        # For Flask, use thread-local storage instead of global
        try:
            # Try to detect if we're in Flask by checking for request context
            from flask import has_request_context
            is_flask = has_request_context()
        except ImportError:
            is_flask = False
        
        if is_flask:
            print(f"DEBUG: Flask context detected, using thread-local storage", flush=True)
            _thread_local.openai_client = project_client.get_openai_client()
            client = _thread_local.openai_client
        else:
            # Single-threaded environment, use global cache with lock
            with _azure_client_lock:
                if _openai_client is None:
                    _openai_client = project_client.get_openai_client()
                client = _openai_client
        
        elapsed = time.time() - start
        print(f"DEBUG: get_openai_client() completed in {elapsed:.2f}s (type: {type(client).__name__})", flush=True)
        
        # Configure timeout (60 seconds for API calls)
        if hasattr(client, '_client'):
            # Set timeout on underlying httpx client if available
            timeout = os.getenv("AZURE_OPENAI_TIMEOUT", "60")
            try:
                timeout_seconds = float(timeout)
                if hasattr(client._client, 'timeout'):
                    client._client.timeout = timeout_seconds
                    print(f"DEBUG: Set client timeout to {timeout_seconds}s", flush=True)
            except (ValueError, AttributeError):
                print(f"DEBUG: Timeout configuration not supported, using default", flush=True)
        
        return client
        
    except Exception as e:
        print(f"ERROR: Failed to create OpenAI client: {e}", flush=True)
        import traceback
        traceback.print_exc()
        raise


def chat_completion(
    messages: List[Dict[str, str]],
    deployment_name: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    agent_type: str = "default",
    timeout: Optional[float] = None,
    **kwargs
) -> str:
    """Call Azure AI Foundry agent for chat completion.

    Args:
        messages: List of message dicts with 'role' and 'content'
        deployment_name: Not used (agent uses its configured model)
        temperature: Not used (must be configured on agent)
        max_tokens: Not used (must be configured on agent)
        agent_type: Which specialized agent to use
        timeout: Timeout in seconds (default: 60, or AZURE_OPENAI_TIMEOUT env var)
        
    Returns:
        Response text from the agent
        
    Raises:
        Exception: If chat completion fails or times out
    """
    import signal
    import time
    
    if timeout is None:
        timeout = float(os.getenv("AZURE_OPENAI_TIMEOUT", "60"))
    
    try:
        print(f"DEBUG: Starting chat completion for agent_type={agent_type} (timeout={timeout}s)", flush=True)
        
        # Get client first
        print(f"DEBUG: Getting Azure client...", flush=True)
        client = get_azure_client()
        print(f"DEBUG: Azure client obtained (type: {type(client).__name__})", flush=True)
        
        # Get or create agent (this might hang if agent creation is slow)
        print(f"DEBUG: Getting or creating agent (type: {agent_type})...", flush=True)
        agent = get_or_create_agent(agent_type)
        print(f"DEBUG: Agent obtained: {agent.name} (type: {type(agent).__name__})", flush=True)

        # Convert messages to input format (use last user message)
        user_content = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        
        if not user_content:
            raise ValueError("No user message found in messages list")

        print(f"DEBUG: Calling Azure AI Foundry agent '{agent.name}' with content length {len(user_content)}...", flush=True)
        start_time = time.time()
        
        # Make the API call directly - the underlying httpx client should handle timeout
        # ThreadPoolExecutor timeout doesn't work well in Flask's threading model
        print(f"DEBUG: Making direct API call to responses.create...", flush=True)
        try:
            # Call directly - Azure SDK's httpx client should respect timeout from client config
            # If timeout parameter is supported, use it; otherwise rely on client-level timeout
            call_kwargs = {
                "input": [{"role": "user", "content": user_content}],
                "extra_body": {
                    "agent": {
                        "name": agent.name,
                        "type": "agent_reference"
                    }
                }
            }
            
            # Try to pass timeout if the method supports it
            try:
                # Check if responses.create accepts timeout parameter
                import inspect
                sig = inspect.signature(client.responses.create)
                if 'timeout' in sig.parameters:
                    call_kwargs['timeout'] = timeout
                    print(f"DEBUG: Using timeout parameter in API call", flush=True)
            except (AttributeError, TypeError):
                # Method doesn't support timeout parameter, rely on client-level timeout
                print(f"DEBUG: Method doesn't support timeout parameter, using client-level timeout", flush=True)
            
            response = client.responses.create(**call_kwargs)
            
            elapsed = time.time() - start_time
            print(f"DEBUG: Agent response received in {elapsed:.2f}s", flush=True)
            
            if not hasattr(response, 'output_text') or not response.output_text:
                print(f"DEBUG: Response object attributes: {dir(response)}", flush=True)
                raise ValueError("Empty response from Azure agent")
            
            print(f"DEBUG: Response text length: {len(response.output_text)}", flush=True)
            return response.output_text
            
        except Exception as api_error:
            elapsed = time.time() - start_time
            error_msg = str(api_error)
            print(f"DEBUG: Agent call failed after {elapsed:.2f}s: {error_msg}", flush=True)
            
            # Check if it's a timeout
            if elapsed >= timeout * 0.9:  # Allow 10% tolerance
                print(f"ERROR: Agent call appears to have timed out after {elapsed:.2f}s", flush=True)
                raise Exception(f"Agent call timed out after {timeout} seconds. Please check:\n"
                              f"1. Azure AI Foundry service status\n"
                              f"2. Network connectivity\n"
                              f"3. Cancel any stuck pipeline runs in Azure Portal")
            
            import traceback
            traceback.print_exc()
            raise Exception(f"Azure API call failed: {error_msg}") from api_error
            
    except Exception as e:
        error_msg = f"Chat completion failed for agent_type={agent_type}: {str(e)}"
        print(f"ERROR: {error_msg}", flush=True)
        
        # Provide helpful error messages
        if "timeout" in str(e).lower() or "timed out" in str(e).lower():
            error_msg += "\n\nPossible solutions:\n"
            error_msg += "1. Check Azure AI Foundry service status\n"
            error_msg += "2. Verify network connectivity\n"
            error_msg += "3. Check if old pipeline runs are blocking (cancel them in Azure Portal)\n"
            error_msg += "4. Increase timeout by setting AZURE_OPENAI_TIMEOUT env var"
        elif "permission" in str(e).lower() or "unauthorized" in str(e).lower():
            error_msg += "\n\nPlease check:\n"
            error_msg += "1. Azure authentication (az login)\n"
            error_msg += "2. Permissions to access Azure AI Foundry\n"
            error_msg += "3. Service principal credentials if using service principal"
        
        raise Exception(error_msg) from e


def get_openai_embedding_client():
    """Get OpenAI client for embeddings (fallback when Azure unavailable).
    
    Returns:
        OpenAI client configured with API key
        
    Raises:
        ValueError: If OPENAI_KEY not set
        ImportError: If openai package not installed
    """
    openai_key = os.getenv("OPENAI_KEY")
    if not openai_key:
        raise ValueError("OPENAI_KEY not set - cannot use OpenAI embeddings fallback")
    
    try:
        from openai import OpenAI
        return OpenAI(api_key=openai_key)
    except ImportError:
        raise ImportError("openai package not installed. Install with: pip install openai")


def get_embedding(
    text: str,
    deployment_name: Optional[str] = None
) -> List[float]:
    """Get embedding for a single text using Azure OpenAI, with OpenAI fallback.
    
    Tries Azure first, falls back to OpenAI if Azure fails.
    
    Args:
        text: Text to embed
        deployment_name: Embedding model deployment name (uses env var if not provided)
        
    Returns:
        List of embedding values
        
    Raises:
        Exception: If embedding generation fails from both providers
    """
    if not text or not text.strip():
        raise ValueError("Text cannot be empty for embedding")
    
    if deployment_name is None:
        deployment_name = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME", "text-embedding-3-small")
    
    # Try Azure first
    try:
        # Use direct Azure OpenAI client for embeddings (works better with GlobalStandard deployments)
        try:
            client = get_embedding_client()
        except Exception as e:
            print(f"DEBUG: Failed to get direct embedding client, falling back to AI Projects client: {e}", flush=True)
            client = get_azure_client()

        response = client.embeddings.create(
            model=deployment_name,
            input=text
        )

        if not response.data or len(response.data) == 0:
            raise ValueError("Empty response from Azure embedding API")

        print(f"DEBUG: Successfully got embedding from Azure", flush=True)
        return response.data[0].embedding
        
    except Exception as azure_error:
        error_str = str(azure_error)
        print(f"DEBUG: Azure embedding failed: {error_str}", flush=True)
        
        # Check if we should try OpenAI fallback
        openai_key = os.getenv("OPENAI_KEY")
        if not openai_key:
            # No fallback available, raise the Azure error
            raise Exception(f"Azure embedding failed and OPENAI_KEY not set for fallback: {error_str}") from azure_error
        
        # Try OpenAI fallback
        try:
            print(f"DEBUG: Attempting OpenAI embedding fallback", flush=True)
            openai_client = get_openai_embedding_client()
            
            # Use same model name for OpenAI (text-embedding-3-small works with OpenAI too)
            openai_model = deployment_name if deployment_name else "text-embedding-3-small"
            
            response = openai_client.embeddings.create(
                model=openai_model,
                input=text
            )
            
            if not response.data or len(response.data) == 0:
                raise ValueError("Empty response from OpenAI embedding API")
            
            print(f"DEBUG: Successfully got embedding from OpenAI (fallback)", flush=True)
            return response.data[0].embedding
            
        except Exception as openai_error:
            # Both failed, raise with helpful message
            raise Exception(
                f"Both Azure and OpenAI embeddings failed. "
                f"Azure error: {error_str}. "
                f"OpenAI error: {str(openai_error)}"
            ) from openai_error


def get_embeddings_batch(
    texts: List[str],
    deployment_name: Optional[str] = None
) -> List[List[float]]:
    """Get embeddings for multiple texts using Azure OpenAI, with OpenAI fallback.
    
    Tries Azure first, falls back to OpenAI if Azure fails.
    
    Args:
        texts: List of texts to embed
        deployment_name: Embedding model deployment name (uses env var if not provided)
        
    Returns:
        List of embedding vectors (one per input text)
        
    Raises:
        Exception: If embedding generation fails from both providers
    """
    if not texts:
        return []

    if deployment_name is None:
        deployment_name = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME", "text-embedding-3-small")

    # Filter out empty texts
    valid_texts = [t for t in texts if t and t.strip()]
    if len(valid_texts) != len(texts):
        print(f"DEBUG: Filtered out {len(texts) - len(valid_texts)} empty texts", flush=True)

    if not valid_texts:
        raise ValueError("No valid texts provided for embedding")

    # Try Azure first
    try:
        # Use direct Azure OpenAI client for embeddings (works better with GlobalStandard deployments)
        # Try direct client first, fall back to AI Projects client if it fails
        client = None
        use_direct_client = True
        try:
            client = get_embedding_client()
            print(f"DEBUG: Using direct Azure OpenAI client for embeddings", flush=True)
        except Exception as e:
            print(f"DEBUG: Failed to get direct embedding client, falling back to AI Projects client: {e}", flush=True)
            client = get_azure_client()
            use_direct_client = False

        try:
            response = client.embeddings.create(
                model=deployment_name,
                input=valid_texts
            )
        except Exception as api_error:
            # If direct client failed with 404, try AI Projects client as fallback
            if use_direct_client and ("404" in str(api_error) or "NotFound" in str(type(api_error).__name__)):
                print(f"DEBUG: Direct client failed with 404, trying AI Projects client as fallback", flush=True)
                try:
                    client = get_azure_client()
                    response = client.embeddings.create(
                        model=deployment_name,
                        input=valid_texts
                    )
                except Exception as fallback_error:
                    raise Exception(f"Azure embedding failed: {str(fallback_error)}") from fallback_error
            else:
                raise

        if not response.data or len(response.data) != len(valid_texts):
            raise ValueError(f"Expected {len(valid_texts)} embeddings, got {len(response.data) if response.data else 0}")

        print(f"DEBUG: Successfully got {len(valid_texts)} embeddings from Azure", flush=True)
        return [item.embedding for item in response.data]
        
    except Exception as azure_error:
        error_str = str(azure_error)
        print(f"DEBUG: Azure batch embedding failed: {error_str}", flush=True)
        
        # Check if we should try OpenAI fallback
        openai_key = os.getenv("OPENAI_KEY")
        if not openai_key:
            raise Exception(f"Azure embedding failed and OPENAI_KEY not set for fallback: {error_str}") from azure_error
        
        # Try OpenAI fallback
        try:
            print(f"DEBUG: Attempting OpenAI embedding fallback for {len(valid_texts)} texts", flush=True)
            openai_client = get_openai_embedding_client()
            
            # Use same model name for OpenAI
            openai_model = deployment_name if deployment_name else "text-embedding-3-small"
            
            response = openai_client.embeddings.create(
                model=openai_model,
                input=valid_texts
            )
            
            if not response.data or len(response.data) != len(valid_texts):
                raise ValueError(f"Expected {len(valid_texts)} embeddings from OpenAI, got {len(response.data) if response.data else 0}")
            
            print(f"DEBUG: Successfully got {len(valid_texts)} embeddings from OpenAI (fallback)", flush=True)
            return [item.embedding for item in response.data]
            
        except Exception as openai_error:
            raise Exception(
                f"Both Azure and OpenAI embeddings failed. "
                f"Azure error: {error_str}. "
                f"OpenAI error: {str(openai_error)}"
            ) from openai_error

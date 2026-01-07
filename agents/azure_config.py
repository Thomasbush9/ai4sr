import os
import threading
from typing import Optional, List, Dict, Any
from azure.identity import DefaultAzureCredential, ClientSecretCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition

_azure_client_lock = threading.Lock()
_project_client = None
_openai_client = None
_agent = None


def get_credential():
    """Get Azure credential - use service principal if available, else DefaultAzureCredential."""
    tenant_id = os.getenv("MICROSOFT_TENANT_ID")
    client_id = os.getenv("MICROSOFT_CLIENT_ID")
    client_secret = os.getenv("MICROSOFT_CLIENT_SECRET")

    if tenant_id and client_id and client_secret:
        # Use explicit service principal credentials
        return ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret
        )
    else:
        # Fall back to DefaultAzureCredential (tries az login, managed identity, etc.)
        return DefaultAzureCredential()


def get_project_client() -> AIProjectClient:
    """Get Azure AI Project client with credentials."""
    global _project_client

    if _project_client is None:
        with _azure_client_lock:
            if _project_client is None:
                endpoint = os.getenv("AZURE_EXISTING_AIPROJECT_ENDPOINT")

                if not endpoint:
                    raise ValueError(
                        "Azure AI Project not configured. "
                        "Please set AZURE_EXISTING_AIPROJECT_ENDPOINT environment variable."
                    )

                credential = get_credential()
                _project_client = AIProjectClient(
                    endpoint=endpoint,
                    credential=credential
                )

    return _project_client


def get_or_create_agent():
    """Get or create the AI4SR agent."""
    global _agent

    if _agent is None:
        with _azure_client_lock:
            if _agent is None:
                project_client = get_project_client()
                agent_name = os.getenv("AZURE_AGENT_NAME", "ai4sr-agent")
                model_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini")

                # Create or update agent
                _agent = project_client.agents.create_version(
                    agent_name=agent_name,
                    definition=PromptAgentDefinition(
                        model=model_deployment,
                        instructions="You are an AI assistant helping with systematic literature reviews. "
                                   "Provide clear, accurate, and concise responses based on the context provided."
                    )
                )

    return _agent


def get_azure_client():
    """Get OpenAI client from Azure AI Project."""
    global _openai_client

    if _openai_client is None:
        with _azure_client_lock:
            if _openai_client is None:
                project_client = get_project_client()
                _openai_client = project_client.get_openai_client()

    return _openai_client


def chat_completion(
    messages: List[Dict[str, str]],
    deployment_name: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    **kwargs
) -> str:
    """Call Azure AI Foundry agent for chat completion."""
    client = get_azure_client()
    agent = get_or_create_agent()

    # Convert messages to input format (use last user message)
    user_content = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")

    # Use Azure AI Foundry agent API
    response = client.responses.create(
        input=[{"role": "user", "content": user_content}],
        extra_body={
            "agent": {
                "name": agent.name,
                "type": "agent_reference"
            },
            "max_tokens": max_tokens,
            "temperature": temperature
        }
    )

    return response.output_text


def get_embedding(
    text: str,
    deployment_name: Optional[str] = None
) -> List[float]:
    if deployment_name is None:
        deployment_name = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME", "text-embedding-3-small")

    client = get_azure_client()

    response = client.embeddings.create(
        model=deployment_name,
        input=text
    )

    return response.data[0].embedding


def get_embeddings_batch(
    texts: List[str],
    deployment_name: Optional[str] = None
) -> List[List[float]]:
    if deployment_name is None:
        deployment_name = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME", "text-embedding-3-small")

    client = get_azure_client()

    response = client.embeddings.create(
        model=deployment_name,
        input=texts
    )

    return [item.embedding for item in response.data]

import os
import threading
from typing import Optional, List, Dict, Any
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

_azure_client_lock = threading.Lock()
_project_client = None
_openai_client = None


def get_project_client() -> AIProjectClient:
    """Get Azure AI Project client with DefaultAzureCredential."""
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

                _project_client = AIProjectClient(
                    endpoint=endpoint,
                    credential=DefaultAzureCredential()
                )

    return _project_client


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
    if deployment_name is None:
        deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini")

    client = get_azure_client()

    response = client.chat.completions.create(
        model=deployment_name,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        **kwargs
    )

    return response.choices[0].message.content


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

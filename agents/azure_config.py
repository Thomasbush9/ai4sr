import os
import threading
from typing import Optional, List, Dict, Any
from openai import AzureOpenAI

_azure_client_lock = threading.Lock()
_azure_client = None


def get_azure_client() -> AzureOpenAI:
    global _azure_client

    if _azure_client is None:
        with _azure_client_lock:
            if _azure_client is None:
                endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
                api_key = os.getenv("AZURE_OPENAI_API_KEY")
                api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")

                if not endpoint or not api_key:
                    raise ValueError(
                        "Azure OpenAI credentials not configured. "
                        "Please set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY environment variables."
                    )

                _azure_client = AzureOpenAI(
                    azure_endpoint=endpoint,
                    api_key=api_key,
                    api_version=api_version
                )

    return _azure_client


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

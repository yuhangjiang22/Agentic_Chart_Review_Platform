"""LLM model configuration — supports Azure OpenAI and Ollama."""

import os
from dotenv import load_dotenv
from langchain_core.language_models import BaseChatModel

from pathlib import Path

load_dotenv(Path(__file__).parent / ".env")


DEFAULT_PROVIDER = os.getenv("LLM_PROVIDER", "azure")
DEFAULT_MODEL = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")
DEFAULT_OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "openai/gpt-oss-120b")


def create_model(model_name: str | None = None, provider: str | None = None) -> BaseChatModel:
    """Create a chat model instance for the given provider (azure or ollama)."""
    provider = (provider or DEFAULT_PROVIDER).lower()

    if provider == "ollama":
        return _create_ollama_model(model_name)
    elif provider == "azure":
        return _create_azure_model(model_name)
    else:
        raise ValueError(f"Unknown provider '{provider}'. Choose 'azure' or 'ollama'.")


def _create_azure_model(model_name: str | None = None) -> BaseChatModel:
    from langchain_openai import AzureChatOpenAI

    deployment = model_name or DEFAULT_MODEL
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-06-01")

    if not api_key:
        raise ValueError("AZURE_OPENAI_API_KEY environment variable is required")
    if not endpoint:
        raise ValueError("AZURE_OPENAI_ENDPOINT environment variable is required")

    return AzureChatOpenAI(
        azure_deployment=deployment,
        api_version=api_version,
        azure_endpoint=endpoint,
        api_key=api_key,
        temperature=0,
    )


def _create_ollama_model(model_name: str | None = None) -> BaseChatModel:
    from langchain_ollama import ChatOllama

    model = model_name or DEFAULT_OLLAMA_MODEL
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    return ChatOllama(
        model=model,
        base_url=base_url,
        temperature=0,
    )

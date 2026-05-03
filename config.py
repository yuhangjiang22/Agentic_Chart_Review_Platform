"""Azure OpenAI model configuration."""

import os
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI

from pathlib import Path

load_dotenv(Path(__file__).parent / ".env")


DEFAULT_MODEL = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")


def create_model(model_name: str | None = None) -> AzureChatOpenAI:
    """Create an AzureChatOpenAI instance pointed at Azure OpenAI."""
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

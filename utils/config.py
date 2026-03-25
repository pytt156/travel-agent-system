import os
from enum import Enum
from typing import Any

from dotenv import load_dotenv
from langchain_ollama import ChatOllama


class AvailableModels(str, Enum):
    LLAMA_8B = "llama3.1:8b"
    LLAMA_70B = "llama3.1:70b"


DEFAULT_MODEL = AvailableModels.LLAMA_8B

load_dotenv()

base_url = os.getenv("OLLAMA_BASE_URL")
bearer_token = os.getenv("OLLAMA_BEARER_TOKEN")


def get_llm(model_name: AvailableModels = DEFAULT_MODEL, **kwargs: Any) -> ChatOllama:
    if not base_url:
        raise ValueError("OLLAMA_BASE_URL must be set in .env")

    if not bearer_token:
        raise ValueError("OLLAMA_BEARER_TOKEN must be set in .env")

    params: dict[str, Any] = {
        "model": model_name.value,
        "base_url": base_url,
        "client_kwargs": {"headers": {"Authorization": f"Bearer {bearer_token}"}},
    }
    params.update(kwargs)

    return ChatOllama(**params)

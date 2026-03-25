from __future__ import annotations

import os
from dotenv import load_dotenv
from langchain_ollama import ChatOllama

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_BEARER_TOKEN = os.getenv("OLLAMA_BEARER_TOKEN", None)
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")

TEMPERATURE = float(os.getenv("TEMPERATURE", "0.2"))
TOP_P = float(os.getenv("TOP_P", "0.9"))

MCP_HOST = os.getenv("MCP_HOST", "127.0.0.1")
MCP_PORT = int(os.getenv("MCP_PORT", "8000"))

DEBUG = os.getenv("DEBUG", "true").lower() == "true"


def get_llm(**kwargs) -> ChatOllama:
    client_kwargs = kwargs.get("client_kwargs", {}).copy()

    if OLLAMA_BEARER_TOKEN:
        headers = client_kwargs.get("headers", {}).copy()
        headers["Authorization"] = f"Bearer {OLLAMA_BEARER_TOKEN}"
        client_kwargs["headers"] = headers

    return ChatOllama(
        base_url=OLLAMA_BASE_URL,
        model=kwargs.get("model", OLLAMA_MODEL),
        temperature=kwargs.get("temperature", TEMPERATURE),
        top_p=kwargs.get("top_p", TOP_P),
        client_kwargs=client_kwargs,
    )

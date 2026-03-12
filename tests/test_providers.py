"""Tests for provider factory functions."""

import pytest

from graphmem.providers.embeddings import (
    BedrockEmbedder,
    LocalEmbedder,
    OpenAIEmbedder,
    create_embedder,
)
from graphmem.providers.llm import (
    AnthropicLLMClient,
    BedrockLLMClient,
    OllamaLLMClient,
    OpenAILLMClient,
    create_llm_client,
)


def test_create_openai_embedder():
    embedder = create_embedder("openai", api_key="test-key")
    assert isinstance(embedder, OpenAIEmbedder)


def test_create_bedrock_embedder():
    embedder = create_embedder("bedrock", region="us-west-2")
    assert isinstance(embedder, BedrockEmbedder)


def test_create_local_embedder():
    embedder = create_embedder("local")
    assert isinstance(embedder, LocalEmbedder)


def test_create_unknown_embedder():
    with pytest.raises(ValueError, match="Unknown embedding provider"):
        create_embedder("unknown")


def test_create_openai_llm():
    client = create_llm_client("openai", api_key="test-key")
    assert isinstance(client, OpenAILLMClient)


def test_create_anthropic_llm():
    client = create_llm_client("anthropic", api_key="test-key")
    assert isinstance(client, AnthropicLLMClient)


def test_create_bedrock_llm():
    client = create_llm_client("bedrock", region="us-west-2")
    assert isinstance(client, BedrockLLMClient)


def test_create_ollama_llm():
    client = create_llm_client("ollama")
    assert isinstance(client, OllamaLLMClient)


def test_create_unknown_llm():
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        create_llm_client("unknown")

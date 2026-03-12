"""Embedding provider implementations.

Each class implements graphiti-core's EmbedderClient interface:
  async create(input_data: str | list[str]) -> list[float]
  async create_batch(input_data_list: list[str]) -> list[list[float]]  (optional)
"""

from __future__ import annotations

from graphiti_core.embedder import EmbedderClient


class OpenAIEmbedder(EmbedderClient):
    """OpenAI embeddings (text-embedding-3-small)."""

    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        self._model = model
        import openai

        self._client = openai.AsyncOpenAI(api_key=api_key)

    async def create(self, input_data: str | list[str]) -> list[float]:
        text = input_data if isinstance(input_data, str) else input_data[0]
        response = await self._client.embeddings.create(
            input=text,
            model=self._model,
        )
        return response.data[0].embedding

    async def create_batch(self, input_data_list: list[str]) -> list[list[float]]:
        response = await self._client.embeddings.create(
            input=input_data_list,
            model=self._model,
        )
        return [item.embedding for item in response.data]


class BedrockEmbedder(EmbedderClient):
    """AWS Bedrock embeddings (Amazon Titan Embeddings v2)."""

    def __init__(self, region: str = "us-east-1", model: str = "amazon.titan-embed-text-v2:0"):
        self._model = model
        self._region = region

    def _get_client(self):
        import boto3

        return boto3.client("bedrock-runtime", region_name=self._region)

    async def create(self, input_data: str | list[str]) -> list[float]:
        import asyncio
        import json

        text = input_data if isinstance(input_data, str) else input_data[0]
        client = self._get_client()

        body = json.dumps({"inputText": text})
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: client.invoke_model(
                modelId=self._model,
                body=body,
                contentType="application/json",
                accept="application/json",
            ),
        )
        result = json.loads(response["body"].read())
        return result["embedding"]

    async def create_batch(self, input_data_list: list[str]) -> list[list[float]]:
        results = []
        for text in input_data_list:
            embedding = await self.create(text)
            results.append(embedding)
        return results


class LocalEmbedder(EmbedderClient):
    """Local embeddings using sentence-transformers. No API key needed."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self._model_name = model_name
        self._model = None

    def _load_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self._model_name)
        return self._model

    async def create(self, input_data: str | list[str]) -> list[float]:
        import asyncio

        text = input_data if isinstance(input_data, str) else input_data[0]
        model = self._load_model()
        embedding = await asyncio.get_event_loop().run_in_executor(
            None, lambda: model.encode(text)
        )
        return embedding.tolist()

    async def create_batch(self, input_data_list: list[str]) -> list[list[float]]:
        import asyncio

        model = self._load_model()
        embeddings = await asyncio.get_event_loop().run_in_executor(
            None, lambda: model.encode(input_data_list)
        )
        return [e.tolist() for e in embeddings]


def create_embedder(provider: str, **kwargs) -> EmbedderClient:
    """Factory function to create an embedder by provider name."""
    if provider == "openai":
        return OpenAIEmbedder(
            api_key=kwargs.get("api_key", ""),
            model=kwargs.get("model", "text-embedding-3-small"),
        )
    elif provider == "bedrock":
        return BedrockEmbedder(
            region=kwargs.get("region", "us-east-1"),
            model=kwargs.get("model", "amazon.titan-embed-text-v2:0"),
        )
    elif provider == "local":
        return LocalEmbedder(
            model_name=kwargs.get("model", "all-MiniLM-L6-v2"),
        )
    else:
        raise ValueError(f"Unknown embedding provider: {provider}")

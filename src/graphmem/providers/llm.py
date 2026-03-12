"""LLM provider implementations for entity extraction.

Each class implements graphiti-core's LLMClient interface:
  async _generate_response(messages, response_model, max_tokens, model_size) -> dict
"""

from __future__ import annotations

import typing

from pydantic import BaseModel

from graphiti_core.llm_client import LLMClient
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.llm_client.client import ModelSize

import re


def _extract_json(text: str) -> str:
    """Strip markdown code fences from LLM JSON responses."""
    m = re.search(r'```(?:json)?\s*\n?(.*?)```', text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return text.strip()


class OpenAILLMClient(LLMClient):
    """OpenAI LLM client (GPT-4o-mini / GPT-4o)."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        config = LLMConfig(model=model, small_model=model)
        super().__init__(config, cache=False)
        import openai

        self._client = openai.AsyncOpenAI(api_key=api_key)

    async def _generate_response(
        self,
        messages: list,
        response_model: type[BaseModel] | None = None,
        max_tokens: int = 4096,
        model_size: ModelSize = ModelSize.medium,
    ) -> dict[str, typing.Any]:
        openai_messages = [{"role": m.role, "content": m.content} for m in messages]
        model = self.model if model_size == ModelSize.medium else self.small_model

        if response_model is not None:
            response = await self._client.beta.chat.completions.parse(
                model=model,
                messages=openai_messages,
                max_tokens=max_tokens,
                temperature=self.temperature,
                response_format=response_model,
            )
            parsed = response.choices[0].message.parsed
            if parsed is not None:
                return parsed.model_dump()
            return {}
        else:
            response = await self._client.chat.completions.create(
                model=model,
                messages=openai_messages,
                max_tokens=max_tokens,
                temperature=self.temperature,
            )
            content = response.choices[0].message.content or ""
            return {"content": content}


class AnthropicLLMClient(LLMClient):
    """Anthropic Claude LLM client (direct API)."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        config = LLMConfig(model=model, small_model=model)
        super().__init__(config, cache=False)
        import anthropic

        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def _generate_response(
        self,
        messages: list,
        response_model: type[BaseModel] | None = None,
        max_tokens: int = 4096,
        model_size: ModelSize = ModelSize.medium,
    ) -> dict[str, typing.Any]:
        # Separate system message from conversation messages
        system_text = ""
        conversation = []
        for m in messages:
            if m.role == "system":
                system_text += m.content + "\n"
            else:
                conversation.append({"role": m.role, "content": m.content})

        model = self.model if model_size == ModelSize.medium else self.small_model

        kwargs: dict[str, typing.Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": conversation,
        }
        if system_text.strip():
            kwargs["system"] = system_text.strip()

        if response_model is not None:
            schema = response_model.model_json_schema()
            kwargs["messages"][-1]["content"] += (
                f"\n\nRespond with valid JSON matching this schema:\n{schema}"
            )

        response = await self._client.messages.create(**kwargs)
        content = response.content[0].text

        if response_model is not None:
            import json

            try:
                data = json.loads(_extract_json(content))
                return data
            except json.JSONDecodeError:
                return {"content": content}

        return {"content": content}


class BedrockLLMClient(LLMClient):
    """AWS Bedrock LLM client (Claude via Bedrock)."""

    def __init__(
        self,
        region: str = "us-east-1",
        model: str = "us.anthropic.claude-sonnet-4-20250514-v1:0",
    ):
        config = LLMConfig(model=model, small_model=model)
        super().__init__(config, cache=False)
        self._region = region

    def _get_client(self):
        import boto3

        return boto3.client("bedrock-runtime", region_name=self._region)

    async def _generate_response(
        self,
        messages: list,
        response_model: type[BaseModel] | None = None,
        max_tokens: int = 4096,
        model_size: ModelSize = ModelSize.medium,
    ) -> dict[str, typing.Any]:
        import asyncio
        import json

        system_text = ""
        conversation = []
        for m in messages:
            if m.role == "system":
                system_text += m.content + "\n"
            else:
                conversation.append({"role": m.role, "content": m.content})

        model = self.model if model_size == ModelSize.medium else self.small_model

        body: dict[str, typing.Any] = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "messages": conversation,
        }
        if system_text.strip():
            body["system"] = system_text.strip()

        if response_model is not None:
            schema = response_model.model_json_schema()
            body["messages"][-1]["content"] += (
                f"\n\nRespond with valid JSON matching this schema:\n{schema}"
            )

        client = self._get_client()
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: client.invoke_model(
                modelId=model,
                body=json.dumps(body),
                contentType="application/json",
                accept="application/json",
            ),
        )
        result = json.loads(response["body"].read())
        content = result["content"][0]["text"]

        if response_model is not None:
            try:
                data = json.loads(_extract_json(content))
                return data
            except json.JSONDecodeError:
                return {"content": content}

        return {"content": content}


class OllamaLLMClient(LLMClient):
    """Ollama local LLM client."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.2",
    ):
        config = LLMConfig(model=model, small_model=model)
        super().__init__(config, cache=False)
        self._base_url = base_url

    async def _generate_response(
        self,
        messages: list,
        response_model: type[BaseModel] | None = None,
        max_tokens: int = 4096,
        model_size: ModelSize = ModelSize.medium,
    ) -> dict[str, typing.Any]:
        import json

        import httpx

        model = self.model if model_size == ModelSize.medium else self.small_model
        ollama_messages = [{"role": m.role, "content": m.content} for m in messages]

        if response_model is not None:
            schema = response_model.model_json_schema()
            ollama_messages[-1]["content"] += (
                f"\n\nRespond with valid JSON matching this schema:\n{schema}"
            )

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self._base_url}/api/chat",
                json={
                    "model": model,
                    "messages": ollama_messages,
                    "stream": False,
                    "options": {"num_predict": max_tokens},
                },
                timeout=120.0,
            )
            response.raise_for_status()
            result = response.json()

        content = result["message"]["content"]

        if response_model is not None:
            try:
                data = json.loads(_extract_json(content))
                return data
            except json.JSONDecodeError:
                return {"content": content}

        return {"content": content}


def create_llm_client(provider: str, **kwargs) -> LLMClient:
    """Factory function to create an LLM client by provider name."""
    if provider == "openai":
        return OpenAILLMClient(
            api_key=kwargs.get("api_key", ""),
            model=kwargs.get("model", "gpt-4o-mini"),
        )
    elif provider == "anthropic":
        return AnthropicLLMClient(
            api_key=kwargs.get("api_key", ""),
            model=kwargs.get("model", "claude-sonnet-4-20250514"),
        )
    elif provider == "bedrock":
        return BedrockLLMClient(
            region=kwargs.get("region", "us-east-1"),
            model=kwargs.get("model", "us.anthropic.claude-sonnet-4-20250514-v1:0"),
        )
    elif provider == "ollama":
        return OllamaLLMClient(
            base_url=kwargs.get("base_url", "http://localhost:11434"),
            model=kwargs.get("model", "llama3.2"),
        )
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")

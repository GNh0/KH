import os

import requests

from src.orchestration.extension_registry import ExtensionRegistry


class LLMRouterError(RuntimeError):
    pass


class LLMRouter:
    """LLM router with built-in providers and registry-backed custom providers."""

    _provider_registry = ExtensionRegistry()

    def __init__(
        self,
        provider: str = "local",
        model: str = "llama3",
        base_url: str = "http://localhost:11434/v1",
        api_key: str = None,
    ):
        self.provider = provider.lower()
        self.model = model
        self.base_url = base_url
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")

    @classmethod
    def register_provider(cls, name: str, factory, overwrite: bool = False) -> None:
        cls._provider_registry.register("llm_provider", name, factory, overwrite=overwrite)

    @classmethod
    def reset_provider_registry_for_tests(cls) -> None:
        cls._provider_registry = ExtensionRegistry()

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        if self._provider_registry.has("llm_provider", self.provider):
            provider = self._provider_registry.create("llm_provider", self.provider, self)
            if hasattr(provider, "chat"):
                return provider.chat(system_prompt, user_prompt)
            if callable(provider):
                return provider(system_prompt, user_prompt)
            raise LLMRouterError(f"Registered LLM provider is not callable: {self.provider}")

        if self.provider in ["openai", "codex", "local"]:
            return self._call_openai_compatible(system_prompt, user_prompt)
        if self.provider == "claude":
            return self._call_anthropic(system_prompt, user_prompt)
        raise ValueError(f"Unknown LLM provider: {self.provider}")

    def _call_openai_compatible(self, system_prompt: str, user_prompt: str) -> str:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

        endpoint = f"{self.base_url}/chat/completions"
        if "api.openai.com" in self.base_url and not self.base_url.endswith("/v1"):
            endpoint = "https://api.openai.com/v1/chat/completions"

        try:
            response = requests.post(endpoint, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except Exception as exc:
            raise LLMRouterError(f"Error connecting to LLM API: {str(exc)}") from exc

    def _call_anthropic(self, system_prompt: str, user_prompt: str) -> str:
        headers = {
            "x-api-key": self.api_key or os.getenv("ANTHROPIC_API_KEY", ""),
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": self.model,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
            "max_tokens": 4096,
        }
        try:
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload,
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()
            return data["content"][0]["text"]
        except Exception as exc:
            raise LLMRouterError(f"Error connecting to Anthropic API: {str(exc)}") from exc

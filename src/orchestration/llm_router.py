import os
import requests


class LLMRouterError(RuntimeError):
    pass


class LLMRouter:
    """다중 LLM 통신을 지원하는 범용 라우터 (OpenAI, Claude, Local 호환)"""
    def __init__(self, provider: str = "local", model: str = "llama3", base_url: str = "http://localhost:11434/v1", api_key: str = None):
        self.provider = provider.lower()
        self.model = model
        self.base_url = base_url
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        if self.provider in ["openai", "codex", "local"]:
            return self._call_openai_compatible(system_prompt, user_prompt)
        elif self.provider == "claude":
            return self._call_anthropic(system_prompt, user_prompt)
        else:
            raise ValueError(f"Unknown LLM provider: {self.provider}")

    def _call_openai_compatible(self, system_prompt: str, user_prompt: str) -> str:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        }
        
        endpoint = f"{self.base_url}/chat/completions"
        if "api.openai.com" in self.base_url and not self.base_url.endswith("/v1"):
            endpoint = "https://api.openai.com/v1/chat/completions"
            
        try:
            response = requests.post(endpoint, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            raise LLMRouterError(f"Error connecting to LLM API: {str(e)}") from e
        
    def _call_anthropic(self, system_prompt: str, user_prompt: str) -> str:
        headers = {
            "x-api-key": self.api_key or os.getenv("ANTHROPIC_API_KEY", ""),
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        payload = {
            "model": self.model,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
            "max_tokens": 4096
        }
        try:
            response = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()
            return data["content"][0]["text"]
        except Exception as e:
            raise LLMRouterError(f"Error connecting to Anthropic API: {str(e)}") from e

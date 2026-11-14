"""LLM providers: a real one over HTTP and a replay one for offline runs.

Both speak the same small interface, so the orchestrator never knows which it
has. With no API key set, `make_provider` returns the replay one (D-005).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Protocol

import httpx
from pydantic import BaseModel, Field, SecretStr, field_validator


class ProviderError(Exception):
    """Anything that went wrong talking to a model. The message never holds secrets."""


class NoToolSupport(ProviderError):
    """The chosen model or endpoint cannot do tool calls."""


class ToolCall(BaseModel):
    id: str = "call_0"
    name: str
    arguments: str = "{}"  # raw JSON text, exactly as models send it

    @field_validator("arguments", mode="before")
    @classmethod
    def _dict_to_json(cls, v: Any) -> Any:
        return json.dumps(v) if isinstance(v, dict) else v


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0


class ProviderResponse(BaseModel):
    text: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    usage: Usage = Field(default_factory=Usage)


class LlmProvider(Protocol):
    def complete(
        self, messages: list[dict], tools: list[dict], *, case_id: str,
        temperature: float = 0.0, timeout: float | None = None,
    ) -> ProviderResponse: ...


class ReplayProvider:
    """Serves recorded responses from `<fixture_dir>/<case_id>.json`, in order."""

    def __init__(self, fixture_dir: Path):
        self.dir = Path(fixture_dir)
        self._next: dict[str, int] = {}

    def complete(self, messages, tools, *, case_id, temperature=0.0, timeout=None):
        path = self.dir / f"{case_id}.json"
        if not path.exists():
            raise ProviderError(f"no recorded response for case {case_id}")
        responses = json.loads(path.read_text(encoding="utf-8"))["responses"]
        i = self._next.get(case_id, 0)
        if i >= len(responses):
            raise ProviderError(f"recording for {case_id} ran out of responses")
        self._next[case_id] = i + 1
        return ProviderResponse.model_validate(responses[i])


class OpenAICompatibleProvider:
    """Any server speaking the OpenAI chat-completions format. OpenRouter by default."""

    def __init__(self, api_key: SecretStr, model: str, base_url: str = "https://openrouter.ai/api/v1",
                 client: httpx.Client | None = None):
        self._api_key = api_key  # SecretStr prints as asterisks, never the key
        self.model, self.base_url = model, base_url.rstrip("/")
        self._client = client or httpx.Client()

    def __repr__(self) -> str:  # no key, ever
        return f"OpenAICompatibleProvider(model={self.model!r}, base_url={self.base_url!r})"

    def complete(self, messages, tools, *, case_id, temperature=0.0, timeout=None):
        body = {"model": self.model, "messages": messages, "tools": tools, "temperature": temperature}
        headers = {"Authorization": f"Bearer {self._api_key.get_secret_value()}"}
        try:
            r = self._client.post(f"{self.base_url}/chat/completions", json=body, headers=headers, timeout=timeout)
        except httpx.TimeoutException as e:
            raise ProviderError("request timed out") from e
        except httpx.HTTPError as e:
            raise ProviderError(f"network error: {type(e).__name__}") from e
        if r.status_code in (400, 404) and "tool" in r.text.lower():
            raise NoToolSupport("model or endpoint does not support tool calls")
        if r.status_code != 200:
            raise ProviderError(f"provider returned HTTP {r.status_code}")
        try:
            data = r.json()
            msg = data["choices"][0]["message"]
            calls = [ToolCall(id=c["id"], name=c["function"]["name"], arguments=c["function"]["arguments"])
                     for c in msg.get("tool_calls") or []]
            u = data.get("usage") or {}
            return ProviderResponse(text=msg.get("content"), tool_calls=calls,
                                    usage=Usage(prompt_tokens=u.get("prompt_tokens", 0),
                                                completion_tokens=u.get("completion_tokens", 0)))
        except (KeyError, IndexError, ValueError, TypeError) as e:
            raise ProviderError("unreadable provider response") from e


def make_provider(fixture_dir: Path, env: dict[str, str] | None = None) -> LlmProvider:
    """Real provider only if a key is in the environment; otherwise replay."""
    env = os.environ if env is None else env
    # OPENROUTER_API_KEY is the name in .env.example; LLM_API_KEY serves any other provider.
    key = (env.get("OPENROUTER_API_KEY") or env.get("LLM_API_KEY") or "").strip()
    if not key:
        return ReplayProvider(fixture_dir)
    return OpenAICompatibleProvider(
        SecretStr(key), model=env.get("LLM_MODEL", "openai/gpt-4o-mini"),
        base_url=env.get("LLM_BASE_URL", "https://openrouter.ai/api/v1"),
    )

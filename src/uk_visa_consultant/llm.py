"""LLM provider abstraction — the only way a model is called.

Contract (docs/STABILITY.md): `complete(prompt, schema) -> LLMResult`. A response
is parsed + validated against an optional pydantic schema; schema failures are
retried once, then the boundary fails closed (schema_errors populated, parsed=None).

Two implementations:
- StubLLMClient  — deterministic canned responses (pre-API-key dev + tests).
- DeepSeekLLMClient — DeepSeek via its OpenAI-compatible endpoint.
"""
from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field, ValidationError


class LLMResult(BaseModel):
    raw: str
    parsed: Any | None = None
    schema_errors: list[str] = Field(default_factory=list)
    model: str | None = None


class LLMClient:
    name: str = "base"

    def complete(self, prompt: str, schema: type[BaseModel] | None = None) -> LLMResult:
        raise NotImplementedError


class StubLLMClient(LLMClient):
    """Deterministic canned responses keyed by a substring of the prompt.

    StubLLMClient({"bank_statement": '{"closing_balance": 18420.55}'})
    The first key found as a substring of the prompt wins; dict values are
    JSON-encoded. Unmatched prompts return "{}".
    """

    name = "stub"

    def __init__(self, responses: dict[str, Any] | None = None):
        self._responses = responses or {}

    def complete(self, prompt: str, schema: type[BaseModel] | None = None) -> LLMResult:
        raw = "{}"
        for key, value in self._responses.items():
            if key in prompt:
                raw = json.dumps(value) if not isinstance(value, str) else value
                break
        return _validate(raw, schema, model=self.name)


class DeepSeekLLMClient(LLMClient):
    name = "deepseek"

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-chat",
    ):
        from openai import OpenAI  # lazy import: stub dev needs no API dep
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model

    def complete(self, prompt: str, schema: type[BaseModel] | None = None) -> LLMResult:
        raw = self._call(prompt)
        result = _validate(raw, schema, model=self._model)
        if schema is not None and result.schema_errors:
            # retry once with focused feedback, then fail closed
            hint = prompt + "\n\nYour previous response failed schema validation: " \
                + "; ".join(result.schema_errors) \
                + "\nReturn valid JSON matching the requested schema only."
            result = _validate(self._call(hint), schema, model=self._model)
        return result

    def _call(self, prompt: str) -> str:
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        return resp.choices[0].message.content or "{}"


def _json_payload(raw: str) -> str:
    """Normalize one optional Markdown JSON fence; reject surrounding prose."""
    text = raw.strip()
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if len(lines) < 3 or lines[-1].strip() != "```":
        return text
    opener = lines[0].strip().lower()
    if opener not in {"```", "```json"}:
        return text
    return "\n".join(lines[1:-1]).strip()


def _validate(raw: str, schema: type[BaseModel] | None, model: str | None) -> LLMResult:
    if schema is None:
        return LLMResult(raw=raw, parsed=None, model=model)
    try:
        data = json.loads(_json_payload(raw))
    except json.JSONDecodeError as e:
        return LLMResult(raw=raw, schema_errors=[f"invalid JSON: {e}"], model=model)
    try:
        return LLMResult(raw=raw, parsed=schema.model_validate(data), model=model)
    except ValidationError as e:
        return LLMResult(raw=raw, schema_errors=[str(e)], model=model)


def get_llm() -> LLMClient:
    """Return a DeepSeek client when DEEPSEEK_API_KEY is set, else the stub.

    The single factory the rest of the system uses: a real key switches field
    extraction (and long-tail intent) from the deterministic fallback to DeepSeek
    with no code changes.
    """
    import os
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if key:
        return DeepSeekLLMClient(
            api_key=key,
            base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            model=os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
        )
    return StubLLMClient()

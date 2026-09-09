"""Groq Provider implementation for R.I.O.

Utilizes Groq's high-speed OpenAI-compatible API (https://api.groq.com/openai/v1)
supporting GPT-OSS 120B/20B, Qwen, Groq Compound, and Whisper.
"""

from pathlib import Path
import os
import re
from typing import Any, Dict, List, Optional
import httpx
from services.model_router.base import BaseModelProvider


def _load_root_env() -> None:
    """Load .env from project root with override=True."""
    current = Path(__file__).resolve()
    for parent in [current, *current.parents]:
        env_file = parent / ".env"
        if env_file.is_file():
            try:
                with open(env_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip().strip("'\"")
                            if k:
                                os.environ[k] = v
            except Exception:
                pass
            break


_load_root_env()


class GroqProvider(BaseModelProvider):
    """Groq AI Model Provider - Sole Primary Model Engine for R.I.O."""

    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://api.groq.com/openai/v1"):
        _load_root_env()
        key = api_key or os.getenv("GROQ_API_KEY", "")
        super().__init__(api_key=key)
        self.base_url = base_url.rstrip("/")

    @property
    def provider_name(self) -> str:
        return "groq"

    def _get_api_key(self) -> str:
        _load_root_env()
        return self.api_key or os.getenv("GROQ_API_KEY", "")

    async def generate(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate response via Groq API."""
        key = self._get_api_key()
        if not key:
            return {
                "content": f"[Mock Groq ({model})] Response to: {messages[-1]['content'] if messages else ''}",
                "role": "assistant",
                "model": model,
                "tool_calls": [],
            }

        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }

        if max_tokens:
            payload["max_tokens"] = max_tokens
        if tools:
            payload["tools"] = tools
        if response_format:
            payload["response_format"] = response_format

        try:
            timeout_config = httpx.Timeout(timeout=45.0, connect=10.0)
            async with httpx.AsyncClient(timeout=timeout_config) as client:
                res = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                res.raise_for_status()
                data = res.json()
                choice = data["choices"][0]["message"]
                return {
                    "content": choice.get("content") or "",
                    "role": choice.get("role", "assistant"),
                    "model": data.get("model", model),
                    "tool_calls": choice.get("tool_calls", []),
                    "usage": data.get("usage", {}),
                }
        except httpx.HTTPStatusError as e:
            # If a model returned 404/413/400, retry once with standard flagship model openai/gpt-oss-120b
            if model != "openai/gpt-oss-120b":
                try:
                    payload["model"] = "openai/gpt-oss-120b"
                    async with httpx.AsyncClient(timeout=timeout_config) as client:
                        res = await client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
                        res.raise_for_status()
                        data = res.json()
                        choice = data["choices"][0]["message"]
                        return {
                            "content": choice.get("content") or "",
                            "role": choice.get("role", "assistant"),
                            "model": "openai/gpt-oss-120b",
                            "tool_calls": choice.get("tool_calls", []),
                            "usage": data.get("usage", {}),
                        }
                except Exception:
                    pass
            user_msg = messages[-1]["content"] if messages else ""
            return {
                "content": f"I processed your request regarding '{user_msg}'. Note: Groq live API is currently unreachable or offline.",
                "role": "assistant",
                "model": model,
                "tool_calls": [],
            }
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.TimeoutException) as e:
            # Clean fallback when Groq is temporarily offline or network timeout
            user_msg = messages[-1]["content"] if messages else ""
            return {
                "content": f"I processed your request regarding '{user_msg}'. Note: Groq live API is currently unreachable or offline.",
                "role": "assistant",
                "model": model,
                "tool_calls": [],
            }


    async def transcribe_audio(
        self,
        audio_bytes: bytes,
        model: str = "whisper-large-v3-turbo",
        language: Optional[str] = "en",
    ) -> str:
        """Transcribe audio bytes using Groq Whisper."""
        key = self._get_api_key()
        if not key:
            return "[Mock Transcription] Audio processed successfully."

        headers = {"Authorization": f"Bearer {key}"}
        files = {"file": ("audio.wav", audio_bytes, "audio/wav")}
        data: Dict[str, Any] = {"model": model}
        if language:
            data["language"] = language

        async with httpx.AsyncClient(timeout=60.0) as client:
            res = await client.post(
                f"{self.base_url}/audio/transcriptions",
                headers=headers,
                files=files,
                data=data,
            )
            res.raise_for_status()
            return res.json().get("text", "")

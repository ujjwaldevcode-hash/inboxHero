import json
import time
import urllib.error
import urllib.request
from typing import Any

from config import (
    GEMINI_API_KEY,
    LLM_MODEL,
    LLM_PROVIDER,
    OFFLINE_MODE,
    OLLAMA_BASE_URL,
    validate_llm_config,
)


class LLMClient:
    """Provider boundary: application code talks to this class, not a model SDK."""

    def __init__(self, model: str | None = None):
        self.model = model or LLM_MODEL
        self._client = None
        self.call_count = 0
        self.total_latency = 0.0
        self.min_latency = None
        self.max_latency = None
        self.last_latency = None
        self.provider = LLM_PROVIDER
        if not OFFLINE_MODE:
            validate_llm_config()
            if LLM_PROVIDER == "gemini":
                from google import genai
                self._client = genai.Client(api_key=GEMINI_API_KEY)

    def _record_latency(self, elapsed: float) -> None:
        self.call_count += 1
        self.total_latency += elapsed
        self.last_latency = elapsed
        self.min_latency = elapsed if self.min_latency is None else min(self.min_latency, elapsed)
        self.max_latency = elapsed if self.max_latency is None else max(self.max_latency, elapsed)

    def _ollama(self, system: str, user: str, json_mode: bool = False) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {"temperature": 0.1},
        }
        # gpt-oss uses its reasoning channel to produce the final JSON content;
        # forcing think=false can leave the content empty or truncated.
        if not self.model.startswith("gpt-oss"):
            payload["think"] = False
        if json_mode:
            payload["format"] = "json"

        url = OLLAMA_BASE_URL.rstrip("/") + "/api/chat"
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Could not reach Ollama at {OLLAMA_BASE_URL}. Is Ollama running?"
            ) from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError("Ollama returned invalid HTTP JSON.") from exc
        finally:
            self._record_latency(time.perf_counter() - started)

        text = body.get("message", {}).get("content", "")
        if not text:
            raise RuntimeError(f"Ollama returned an empty response: {body}")
        return text.strip()

    def text(self, system: str, user: str) -> str:
        if OFFLINE_MODE:
            raise RuntimeError("LLM text() is unavailable in offline mode.")

        if LLM_PROVIDER == "ollama":
            return self._ollama(system, user, json_mode=False)

        from google.genai import types
        started = time.perf_counter()
        try:
            response = self._client.models.generate_content(
                model=self.model,
                contents=user,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    temperature=0.1,
                ),
            )
        finally:
            self._record_latency(time.perf_counter() - started)
        if not response.text:
            raise RuntimeError("Gemini returned an empty response.")
        return response.text.strip()

    def json_value(self, system: str, user: str) -> Any:
        """Return a JSON object or array from the configured provider."""
        if OFFLINE_MODE:
            raise RuntimeError("LLM json() is unavailable in offline mode.")

        if LLM_PROVIDER == "ollama":
            text = self._ollama(system, user, json_mode=True)
        else:
            from google.genai import types
            started = time.perf_counter()
            try:
                response = self._client.models.generate_content(
                    model=self.model,
                    contents=user,
                    config=types.GenerateContentConfig(
                        system_instruction=system,
                        response_mime_type="application/json",
                        temperature=0.1,
                    ),
                )
            finally:
                self._record_latency(time.perf_counter() - started)
            text = (response.text or "").strip()

        try:
            result = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"{LLM_PROVIDER} returned invalid JSON: {text[:500]}") from exc
        return result

    def json(self, system: str, user: str) -> dict[str, Any]:
        result = self.json_value(system, user)
        if not isinstance(result, dict):
            raise RuntimeError(f"{LLM_PROVIDER} JSON response must be an object.")
        return result

from __future__ import annotations

import json
import re
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


_THINK_RE = re.compile(r"<think>.*?</think>", flags=re.DOTALL | re.IGNORECASE)
_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", flags=re.DOTALL | re.IGNORECASE)


@dataclass(frozen=True)
class OllamaClient:
    base_url: str = "http://localhost:11434"
    model: str = "qwen3:4b"
    temperature: float = 0.2
    num_ctx: int = 16384
    timeout_seconds: int = 600
    num_predict: int = 1024
    stream: bool = True

    def generate(self, prompt: str) -> str:
        url = self.base_url.rstrip("/") + "/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": self.stream,
            "options": {
                "temperature": self.temperature,
                "num_ctx": self.num_ctx,
                "num_predict": self.num_predict,
            },
        }
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                if self.stream:
                    return _read_streaming_response(response)
                raw = response.read().decode("utf-8", errors="replace")
                result = json.loads(raw)
                return str(result.get("response", ""))
        except (TimeoutError, socket.timeout) as exc:
            raise RuntimeError(
                f"Ollama timed out after {self.timeout_seconds}s at {url}. "
                "Try --ollama-timeout 900, --chunk-seconds 240, or a smaller model."
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Cannot call Ollama at {url}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid JSON response from Ollama at {url}: {exc}") from exc


def _read_streaming_response(response: Any) -> str:
    """Read Ollama stream=true NDJSON and concatenate response fragments."""
    parts: list[str] = []
    for raw_line in response:
        line = raw_line.decode("utf-8", errors="replace").strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "response" in event:
            parts.append(str(event.get("response") or ""))
        if event.get("done"):
            break
    return "".join(parts)


def strip_model_noise(text: str) -> str:
    text = _THINK_RE.sub("", text).strip()
    fence = _FENCE_RE.search(text)
    if fence:
        return fence.group(1).strip()
    return text


def parse_json_loose(text: str) -> Any:
    """Extract the first JSON object/array from a model response."""
    cleaned = strip_model_noise(text)
    decoder = json.JSONDecoder()
    for start, char in enumerate(cleaned):
        if char not in "[{":
            continue
        try:
            obj, _ = decoder.raw_decode(cleaned[start:])
            return obj
        except json.JSONDecodeError:
            continue
    raise ValueError("No valid JSON found in model response")

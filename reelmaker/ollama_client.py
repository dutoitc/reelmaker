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
    think: bool = False

    def generate(self, prompt: str, *, json_schema: dict[str, Any] | str | None = None) -> str:
        """Generate text locally with Ollama.

        JSON-schema requests deliberately disable streaming and thinking. Ollama's
        structured-output mode is substantially more reliable than asking a model
        to imitate JSON in plain text, especially for Qwen 3 where thinking is
        enabled by default at API level.
        """
        url = self.base_url.rstrip("/") + "/api/generate"
        structured = json_schema is not None
        effective_stream = self.stream and not structured
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": effective_stream,
            "think": self.think,
            "options": {
                "temperature": 0.0 if structured else self.temperature,
                "num_ctx": self.num_ctx,
                "num_predict": self.num_predict,
            },
        }
        if structured:
            payload["format"] = json_schema

        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                if effective_stream:
                    text = _read_streaming_response(response)
                else:
                    raw = response.read().decode("utf-8", errors="replace")
                    result = json.loads(raw)
                    if result.get("error"):
                        raise RuntimeError(f"Ollama generation failed: {result['error']}")
                    text = str(result.get("response", ""))
                    done_reason = str(result.get("done_reason") or "").strip()
                    if not text.strip():
                        suffix = f" (done_reason={done_reason})" if done_reason else ""
                        raise RuntimeError(f"Ollama returned an empty response{suffix}")
                    if done_reason == "length":
                        raise RuntimeError(
                            "Ollama response reached --ollama-num-predict before completion. "
                            "Increase --ollama-num-predict."
                        )
                return text
        except (TimeoutError, socket.timeout) as exc:
            raise RuntimeError(
                f"Ollama timed out after {self.timeout_seconds}s at {url}. "
                "Try --ollama-timeout 900, --chunk-seconds 240, or a smaller model."
            ) from exc
        except urllib.error.HTTPError as exc:
            try:
                body = exc.read().decode("utf-8", errors="replace").strip()
            except Exception:
                body = ""
            detail = f": {body}" if body else ""
            raise RuntimeError(
                f"Ollama HTTP {exc.code} at {url}{detail}. "
                "Update Ollama if the server rejects structured output or the think option."
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Cannot call Ollama at {url}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid JSON response envelope from Ollama at {url}: {exc}") from exc


def _read_streaming_response(response: Any) -> str:
    """Read Ollama stream=true NDJSON and concatenate response fragments."""
    parts: list[str] = []
    done_reason = ""
    for raw_line in response:
        line = raw_line.decode("utf-8", errors="replace").strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("error"):
            raise RuntimeError(f"Ollama streaming generation failed: {event['error']}")
        if "response" in event:
            parts.append(str(event.get("response") or ""))
        if event.get("done"):
            done_reason = str(event.get("done_reason") or "")
            break
    text = "".join(parts)
    if not text.strip():
        suffix = f" (done_reason={done_reason})" if done_reason else ""
        raise RuntimeError(f"Ollama returned an empty streaming response{suffix}")
    if done_reason == "length":
        raise RuntimeError(
            "Ollama response reached --ollama-num-predict before completion. "
            "Increase --ollama-num-predict."
        )
    return text


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

import io
import json
from unittest.mock import patch

import pytest

from reelmaker.ollama_client import OllamaClient, _read_streaming_response, parse_json_loose


class FakeResponse:
    def __iter__(self):
        yield b'{"response":"{\\"ok\\":", "done": false}\n'
        yield b'{"response":"true}", "done": false}\n'
        yield b'{"done": true, "done_reason": "stop"}\n'


class FakeNonStreamingResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_read_streaming_response_concatenates_fragments():
    assert _read_streaming_response(FakeResponse()) == '{"ok":true}'


def test_read_streaming_response_reports_stream_error():
    response = [b'{"error":"GPU failure"}\n']
    with pytest.raises(RuntimeError, match="GPU failure"):
        _read_streaming_response(response)


def test_parse_json_loose_ignores_think_and_fences():
    text = '<think>draft</think>```json\n{"selected": []}\n```'
    assert parse_json_loose(text) == {"selected": []}


def test_structured_generation_disables_thinking_and_streaming():
    captured: dict = {}

    def fake_urlopen(request, timeout):
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeNonStreamingResponse({"response": '{"ok":true}', "done": True, "done_reason": "stop"})

    client = OllamaClient(stream=True, temperature=0.7, think=False)
    schema = {
        "type": "object",
        "properties": {"ok": {"type": "boolean"}},
        "required": ["ok"],
    }
    with patch("reelmaker.ollama_client.urllib.request.urlopen", fake_urlopen):
        result = client.generate("Return JSON", json_schema=schema)

    assert result == '{"ok":true}'
    assert captured["payload"]["format"] == schema
    assert captured["payload"]["think"] is False
    assert captured["payload"]["stream"] is False
    assert captured["payload"]["options"]["temperature"] == 0.0
    assert captured["timeout"] == 600


def test_ollama_client_defaults_match_cli_strategy():
    client = OllamaClient()
    assert client.model == "qwen3:4b"
    assert client.num_ctx == 16384
    assert client.num_predict == 1024
    assert client.think is False

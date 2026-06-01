from reelmaker.ollama_client import _read_streaming_response, parse_json_loose


class FakeResponse:
    def __iter__(self):
        yield b'{"response":"{\\\"ok\\\":", "done": false}\n'
        yield b'{"response":"true}", "done": false}\n'
        yield b'{"done": true}\n'


def test_read_streaming_response_concatenates_fragments():
    assert _read_streaming_response(FakeResponse()) == '{"ok":true}'


def test_parse_json_loose_ignores_think_and_fences():
    text = '<think>draft</think>```json\n{"selected": []}\n```'
    assert parse_json_loose(text) == {"selected": []}

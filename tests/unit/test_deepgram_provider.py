import json

from voxforge.infrastructure.providers.stt.deepgram import DeepgramSTTProvider


class TestDeepgramParseMessage:
    def setup_method(self):
        self.provider = DeepgramSTTProvider("test-key")

    def test_parse_final_transcript(self):
        raw = json.dumps({
            "type": "Results",
            "is_final": True,
            "channel": {
                "alternatives": [{"transcript": "hello world", "confidence": 0.95}]
            },
        })
        event = self.provider._parse_message(raw)
        assert event is not None
        assert event.text == "hello world"
        assert event.is_partial is False
        assert event.confidence == 0.95

    def test_parse_partial_transcript(self):
        raw = json.dumps({
            "type": "Results",
            "is_final": False,
            "channel": {
                "alternatives": [{"transcript": "hel", "confidence": 0.8}]
            },
        })
        event = self.provider._parse_message(raw)
        assert event is not None
        assert event.is_partial is True

    def test_parse_empty_transcript(self):
        raw = json.dumps({
            "type": "Results",
            "is_final": True,
            "channel": {"alternatives": [{"transcript": "", "confidence": 0}]},
        })
        assert self.provider._parse_message(raw) is None

    def test_parse_non_results(self):
        raw = json.dumps({"type": "Metadata"})
        assert self.provider._parse_message(raw) is None

    def test_parse_invalid_json(self):
        assert self.provider._parse_message("not json") is None

from voxforge.infrastructure.providers.tts.cartesia import SentenceBuffer


class TestSentenceBuffer:
    def test_single_sentence(self):
        buf = SentenceBuffer()
        assert buf.add("Hello world.") == "Hello world."

    def test_partial_no_flush(self):
        buf = SentenceBuffer()
        assert buf.add("Hello") is None
        assert buf.add(" world") is None

    def test_multiple_sentences(self):
        buf = SentenceBuffer()
        assert buf.add("First. Second") == "First."
        assert buf.add(".") == "Second."

    def test_flush_remaining(self):
        buf = SentenceBuffer()
        buf.add("No ending")
        assert buf.flush() == "No ending"

    def test_empty_flush(self):
        buf = SentenceBuffer()
        assert buf.flush() is None

    def test_exclamation(self):
        buf = SentenceBuffer()
        assert buf.add("Wow!") == "Wow!"

    def test_question(self):
        buf = SentenceBuffer()
        assert buf.add("Really?") == "Really?"

"""Unit tests for memory conversation summarizer."""

from unittest.mock import MagicMock

import pytest

from voxforge.modules.memory.application.summarizer import Summarizer


@pytest.mark.asyncio
async def test_summarize_streams_llm_tokens():
    async def fake_stream(messages, model):
        _ = messages, model
        yield MagicMock(text="User wants ")
        yield MagicMock(text="refund help.")

    llm = MagicMock()
    llm.generate_stream = fake_stream
    summarizer = Summarizer(llm, model="gpt-test")
    result = await summarizer.summarize("user: I need a refund\nassistant: Sure")
    assert result == "User wants refund help."


@pytest.mark.asyncio
async def test_summarize_falls_back_to_truncated_input():
    async def empty_stream(messages, model):
        _ = messages, model
        return
        yield  # pragma: no cover

    llm = MagicMock()
    llm.generate_stream = empty_stream
    summarizer = Summarizer(llm, model="gpt-test")
    long_text = "a" * 600
    result = await summarizer.summarize(long_text)
    assert result == long_text[:500]


@pytest.mark.asyncio
async def test_summarize_ignores_empty_token_events():
    async def sparse_stream(messages, model):
        _ = messages, model
        yield MagicMock(text=None)
        yield MagicMock(text="done")

    llm = MagicMock()
    llm.generate_stream = sparse_stream
    summarizer = Summarizer(llm, model="gpt-test")
    result = await summarizer.summarize("conversation")
    assert result == "done"

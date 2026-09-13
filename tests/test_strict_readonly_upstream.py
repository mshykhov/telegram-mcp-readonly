from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from telegram_mcp import transcription
from telegram_mcp.tools import messages


@pytest.mark.asyncio
@pytest.mark.parametrize("exposure", [None, "strict-read-only"])
@pytest.mark.parametrize("mode", ["auto", "on-demand"])
async def test_strict_reads_never_transcribe_or_create_cache(
    monkeypatch, tmp_path, exposure, mode
):
    if exposure is None:
        monkeypatch.delenv("TELEGRAM_EXPOSED_TOOLS", raising=False)
    else:
        monkeypatch.setenv("TELEGRAM_EXPOSED_TOOLS", exposure)
    monkeypatch.setenv("TELEGRAM_TRANSCRIBE", mode)
    cache = tmp_path / "transcripts"
    monkeypatch.setenv("TELEGRAM_TRANSCRIPT_CACHE_DIR", str(cache))
    transcribe = AsyncMock()
    monkeypatch.setattr(transcription, "transcribe_cached", transcribe)
    get_client = Mock(side_effect=AssertionError("Strict transcription must not connect"))
    monkeypatch.setattr(messages, "get_client", get_client)
    voice = SimpleNamespace(
        id=1,
        message=None,
        voice=True,
        video_note=None,
        file=SimpleNamespace(duration=5),
    )

    await transcription.prefetch_transcripts(object(), object(), 1, [voice])
    info = transcription.voice_attachment_info(voice, 1)
    result = await messages.transcribe_voice(chat_id=1, message_id=1)

    transcribe.assert_not_awaited()
    get_client.assert_not_called()
    assert info["transcript_status"] is None
    assert "transcription_disabled" in result
    assert not cache.exists()

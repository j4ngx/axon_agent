"""Tests for the ``TTSClient`` (ElevenLabs text-to-speech)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from helix.exceptions import LLMError
from helix.llm.tts import _MAX_TEXT_LENGTH, TTSClient


class TestTTSClient:
    """Unit tests for ``TTSClient``."""

    def setup_method(self) -> None:
        self.client = TTSClient(
            api_key="fake-key",
            voice_id="test-voice",
            model_id="eleven_multilingual_v2",
            output_format="mp3_44100_128",
        )

    async def test_when_synthesizing_expect_api_called_with_correct_params(self) -> None:
        # Arrange
        fake_audio = b"\xff\xfb\x90\x00" * 100  # fake MP3 bytes
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = fake_audio
        mock_response.raise_for_status = MagicMock()

        self.client._client = AsyncMock()
        self.client._client.post = AsyncMock(return_value=mock_response)

        # Act
        result = await self.client.synthesize("Hello world")

        # Assert
        self.client._client.post.assert_called_once()
        call_kwargs = self.client._client.post.call_args
        assert "test-voice" in call_kwargs.args[0]
        assert call_kwargs.kwargs["json"]["text"] == "Hello world"
        assert call_kwargs.kwargs["json"]["model_id"] == "eleven_multilingual_v2"
        assert call_kwargs.kwargs["params"] == {"output_format": "mp3_44100_128"}
        assert result == fake_audio

    async def test_when_synthesizing_expect_audio_bytes_returned(self) -> None:
        # Arrange
        fake_audio = b"audio-data-bytes"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = fake_audio
        mock_response.raise_for_status = MagicMock()

        self.client._client = AsyncMock()
        self.client._client.post = AsyncMock(return_value=mock_response)

        # Act
        result = await self.client.synthesize("Test text")

        # Assert
        assert isinstance(result, bytes)
        assert result == fake_audio

    async def test_when_api_error_expect_llm_error_raised(self) -> None:
        # Arrange
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        self.client._client = AsyncMock()
        self.client._client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "401 Unauthorized",
                request=MagicMock(),
                response=mock_response,
            )
        )

        # Act & Assert
        with pytest.raises(LLMError, match="TTS API error"):
            await self.client.synthesize("Test text")

    async def test_when_network_error_expect_llm_error_raised(self) -> None:
        # Arrange
        self.client._client = AsyncMock()
        self.client._client.post = AsyncMock(side_effect=httpx.ConnectError("connection refused"))

        # Act & Assert
        with pytest.raises(LLMError, match="TTS request failed"):
            await self.client.synthesize("Test text")

    async def test_when_text_too_long_expect_truncated(self) -> None:
        # Arrange
        long_text = "a" * (_MAX_TEXT_LENGTH + 500)
        fake_audio = b"audio"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = fake_audio
        mock_response.raise_for_status = MagicMock()

        self.client._client = AsyncMock()
        self.client._client.post = AsyncMock(return_value=mock_response)

        # Act
        await self.client.synthesize(long_text)

        # Assert — the text sent to the API should be truncated.
        call_kwargs = self.client._client.post.call_args
        sent_text = call_kwargs.kwargs["json"]["text"]
        assert len(sent_text) == _MAX_TEXT_LENGTH

    async def test_when_empty_text_expect_error(self) -> None:
        # Act & Assert
        with pytest.raises(LLMError, match="Cannot synthesise empty text"):
            await self.client.synthesize("")

    async def test_when_whitespace_only_expect_error(self) -> None:
        # Act & Assert
        with pytest.raises(LLMError, match="Cannot synthesise empty text"):
            await self.client.synthesize("   ")

    async def test_when_closing_expect_client_closed(self) -> None:
        # Arrange
        self.client._client = AsyncMock()
        self.client._client.aclose = AsyncMock()

        # Act
        await self.client.close()

        # Assert
        self.client._client.aclose.assert_called_once()

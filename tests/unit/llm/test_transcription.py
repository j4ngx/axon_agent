"""Tests for the ``TranscriptionClient``."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from axon.exceptions import LLMError
from axon.llm.transcription import TranscriptionClient


class TestTranscriptionClient:
    """Unit tests for ``TranscriptionClient``."""

    def setup_method(self) -> None:
        self.client = TranscriptionClient(api_key="fake-key")

    async def test_when_transcribe_success_expect_text_returned(self) -> None:
        # Arrange
        audio_bytes = b"fake-audio-data"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = audio_bytes
        mock_response.raise_for_status = MagicMock()

        self.client._http = AsyncMock()
        self.client._http.get = AsyncMock(return_value=mock_response)
        self.client._client = AsyncMock()
        self.client._client.audio.transcriptions.create = AsyncMock(return_value="Hello world")

        # Act
        result = await self.client.transcribe_from_url(
            file_url="https://example.com/audio.ogg",
            file_name="voice.ogg",
        )

        # Assert
        assert result == "Hello world"
        self.client._http.get.assert_called_once_with("https://example.com/audio.ogg")
        self.client._client.audio.transcriptions.create.assert_called_once_with(
            file=("voice.ogg", audio_bytes),
            model=self.client._model,
            response_format="text",
        )

    async def test_when_download_fails_expect_llm_error(self) -> None:
        # Arrange
        self.client._http = AsyncMock()
        self.client._http.get = AsyncMock(side_effect=httpx.HTTPError("download failed"))

        # Act & Assert
        with pytest.raises(LLMError, match="Failed to download audio"):
            await self.client.transcribe_from_url(
                file_url="https://example.com/audio.ogg",
            )

    async def test_when_groq_api_error_expect_llm_error(self) -> None:
        # Arrange
        from groq import APIError

        audio_bytes = b"fake-audio"
        mock_response = MagicMock()
        mock_response.content = audio_bytes
        mock_response.raise_for_status = MagicMock()

        self.client._http = AsyncMock()
        self.client._http.get = AsyncMock(return_value=mock_response)
        self.client._client = AsyncMock()

        mock_err = APIError(
            message="quota exceeded",
            request=MagicMock(),
            body=None,
        )
        self.client._client.audio.transcriptions.create = AsyncMock(
            side_effect=mock_err,
        )

        # Act & Assert
        with pytest.raises(LLMError, match="Transcription error"):
            await self.client.transcribe_from_url(
                file_url="https://example.com/audio.ogg",
            )

    async def test_when_transcription_returns_object_expect_text_extracted(self) -> None:
        # Arrange — some Groq SDK versions return an object with .text
        audio_bytes = b"fake-audio"
        mock_response = MagicMock()
        mock_response.content = audio_bytes
        mock_response.raise_for_status = MagicMock()

        self.client._http = AsyncMock()
        self.client._http.get = AsyncMock(return_value=mock_response)

        transcript_obj = MagicMock()
        transcript_obj.text = "  transcribed text  "
        self.client._client = AsyncMock()
        self.client._client.audio.transcriptions.create = AsyncMock(
            return_value=transcript_obj,
        )

        # Act
        result = await self.client.transcribe_from_url(
            file_url="https://example.com/audio.ogg",
        )

        # Assert
        assert result == "transcribed text"

    async def test_when_close_expect_http_client_closed(self) -> None:
        # Arrange
        self.client._http = AsyncMock()

        # Act
        await self.client.close()

        # Assert
        self.client._http.aclose.assert_called_once()

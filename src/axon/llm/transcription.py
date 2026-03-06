"""Groq Whisper transcription client.

Downloads a Telegram voice/audio file and transcribes it using the
Groq Whisper API — the same API key already used for chat completions.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

import httpx
from groq import APIError, AsyncGroq

from axon.exceptions import LLMError

logger = logging.getLogger(__name__)

# Groq's current best Whisper model
_WHISPER_MODEL = "whisper-large-v3-turbo"


class TranscriptionClient:
    """Transcribes voice messages using Groq's Whisper API.

    Args:
        api_key: Groq API key (same one used for chat completions).
        model: Whisper model identifier.
        timeout: Request timeout in seconds.
    """

    def __init__(
        self,
        api_key: str,
        model: str = _WHISPER_MODEL,
        timeout: float = 60.0,
    ) -> None:
        self._client = AsyncGroq(api_key=api_key, timeout=timeout)
        self._model = model
        self._http = httpx.AsyncClient(timeout=timeout)

    async def transcribe_from_url(self, file_url: str, file_name: str = "audio.ogg") -> str:
        """Download a Telegram file and return its transcription.

        Args:
            file_url: The full HTTPS URL to download the audio from Telegram.
            file_name: A filename hint so Groq can detect the codec (e.g. ``audio.ogg``).

        Returns:
            The transcribed text.

        Raises:
            LLMError: If the download or transcription fails.
        """
        logger.info("Downloading voice file for transcription", extra={"url": file_url})

        try:
            response = await self._http.get(file_url)
            response.raise_for_status()
            audio_bytes = response.content
        except httpx.HTTPError as exc:
            raise LLMError(f"Failed to download audio file: {exc}") from exc

        return await self._transcribe_bytes(audio_bytes, file_name)

    async def _transcribe_bytes(self, audio_bytes: bytes, file_name: str) -> str:
        """Transcribe raw audio bytes via Groq Whisper.

        Args:
            audio_bytes: Raw audio data.
            file_name: Filename with extension (used for codec detection).

        Returns:
            The transcribed text.

        Raises:
            LLMError: If the Groq API returns an error.
        """
        # Groq's SDK expects a file-like tuple: (filename, bytes, mime_type)
        with tempfile.NamedTemporaryFile(suffix=Path(file_name).suffix, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        logger.info(
            "Sending audio to Groq Whisper", extra={"model": self._model, "bytes": len(audio_bytes)}
        )

        try:
            with open(tmp_path, "rb") as f:
                transcription = await self._client.audio.transcriptions.create(
                    file=(file_name, f.read()),
                    model=self._model,
                    response_format="text",
                )
        except APIError as exc:
            logger.error("Groq Whisper API error", extra={"error": str(exc)})
            raise LLMError(f"Transcription error: {exc}") from exc
        except Exception as exc:
            logger.error("Unexpected transcription error", extra={"error": str(exc)})
            raise LLMError(f"Transcription error: {exc}") from exc
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        text = transcription if isinstance(transcription, str) else transcription.text
        logger.info("Transcription complete", extra={"chars": len(text)})
        return text.strip()

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._http.aclose()

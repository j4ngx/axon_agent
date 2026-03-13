"""ElevenLabs text-to-speech client.

Uses the ElevenLabs REST API via ``httpx`` to synthesise speech from text.
Returns raw MP3 audio bytes that can be sent as a Telegram audio message.
"""

from __future__ import annotations

import logging

import httpx

from helix.exceptions import LLMError

logger = logging.getLogger(__name__)

_MAX_TEXT_LENGTH = 5000
_BASE_URL = "https://api.elevenlabs.io/v1/text-to-speech"


class TTSClient:
    """Synthesise speech from text using ElevenLabs.

    Args:
        api_key: ElevenLabs API key.
        voice_id: Voice identifier for synthesis.
        model_id: ElevenLabs model to use.
        output_format: Audio output format (e.g. ``mp3_44100_128``).
        timeout: Request timeout in seconds.
    """

    def __init__(
        self,
        api_key: str,
        voice_id: str = "Ir1QNHvhaJXbAGhT50w3",
        model_id: str = "eleven_multilingual_v2",
        output_format: str = "mp3_44100_128",
        timeout: float = 30.0,
    ) -> None:
        self._api_key = api_key
        self._voice_id = voice_id
        self._model_id = model_id
        self._output_format = output_format
        self._client = httpx.AsyncClient(timeout=timeout)

    async def synthesize(self, text: str) -> bytes:
        """Convert *text* to MP3 audio bytes.

        Args:
            text: The text to synthesise.  Truncated to 5 000 characters
                if longer (ElevenLabs limit).

        Returns:
            Raw MP3 audio bytes.

        Raises:
            LLMError: If the text is empty or the API call fails.
        """
        if not text or not text.strip():
            raise LLMError("Cannot synthesise empty text")

        if len(text) > _MAX_TEXT_LENGTH:
            logger.warning(
                "TTS text truncated",
                extra={"original_length": len(text), "max_length": _MAX_TEXT_LENGTH},
            )
            text = text[:_MAX_TEXT_LENGTH]

        url = f"{_BASE_URL}/{self._voice_id}"
        headers = {
            "xi-api-key": self._api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        payload = {
            "text": text,
            "model_id": self._model_id,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
            },
        }

        logger.info(
            "TTS request",
            extra={"voice_id": self._voice_id, "text_length": len(text)},
        )

        try:
            response = await self._client.post(
                url,
                headers=headers,
                json=payload,
                params={"output_format": self._output_format},
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "TTS API error",
                extra={"status": exc.response.status_code, "detail": exc.response.text[:200]},
            )
            raise LLMError(f"TTS API error ({exc.response.status_code})") from exc
        except httpx.HTTPError as exc:
            logger.error("TTS request failed", extra={"error": str(exc)})
            raise LLMError(f"TTS request failed: {exc}") from exc

        audio_bytes = response.content
        logger.info("TTS response", extra={"audio_bytes": len(audio_bytes)})
        return audio_bytes

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

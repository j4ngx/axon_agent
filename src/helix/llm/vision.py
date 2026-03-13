"""Groq Vision client for image description.

Uses the Groq SDK's chat completions with multimodal messages
to describe images sent via Telegram.
"""

from __future__ import annotations

import base64
import logging

from groq import APIError, AsyncGroq

from helix.exceptions import LLMError

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"


class VisionClient:
    """Describe images using Groq's vision-capable models.

    Args:
        api_key: Groq API key.
        model: Vision model identifier.
        timeout: Request timeout in seconds.
    """

    def __init__(
        self,
        api_key: str,
        model: str = _DEFAULT_MODEL,
        timeout: float = 60.0,
    ) -> None:
        self._client = AsyncGroq(api_key=api_key, timeout=timeout)
        self._model = model

    async def describe_image(
        self,
        image_bytes: bytes,
        mime_type: str = "image/jpeg",
        prompt: str = "Describe this image in detail. Be concise but thorough.",
    ) -> str:
        """Send an image to the vision model and return a description.

        Args:
            image_bytes: Raw image data.
            mime_type: MIME type (e.g. ``image/jpeg``, ``image/png``).
            prompt: Text prompt to accompany the image.

        Returns:
            The model's description of the image.

        Raises:
            LLMError: If the API call fails.
        """
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        data_url = f"data:{mime_type};base64,{b64}"

        logger.info(
            "Vision request",
            extra={"model": self._model, "image_bytes": len(image_bytes)},
        )

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": data_url},
                            },
                        ],
                    }
                ],
                max_tokens=1024,
            )
        except APIError as exc:
            logger.error("Vision API error", extra={"error": str(exc)})
            raise LLMError(f"Vision API error: {exc}") from exc
        except Exception as exc:
            logger.error("Unexpected vision error", extra={"error": str(exc)})
            raise LLMError(f"Vision error: {exc}") from exc

        text = response.choices[0].message.content or ""
        logger.info("Vision response", extra={"chars": len(text)})
        return text.strip()

    async def close(self) -> None:
        """Close the underlying client."""
        await self._client.close()

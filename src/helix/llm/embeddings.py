"""Embedding clients for document QA.

Provides a Protocol-based abstraction with two implementations:

- ``GroqEmbeddingClient`` — uses Groq's embedding API.
- ``TfIdfEmbeddingClient`` — pure-Python TF-IDF fallback (zero extra deps).
"""

from __future__ import annotations

import logging
import math
from collections import Counter
from typing import Protocol

from groq import APIError, AsyncGroq

from helix.exceptions import LLMError

logger = logging.getLogger(__name__)

_DEFAULT_EMBEDDING_MODEL = "nomic-embed-text-v1_5"


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class EmbeddingClient(Protocol):
    """Contract for embedding providers."""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts into float vectors."""
        ...


# ---------------------------------------------------------------------------
# Groq implementation
# ---------------------------------------------------------------------------


class GroqEmbeddingClient:
    """Embed text using Groq's embedding API.

    Args:
        api_key: Groq API key.
        model: Embedding model identifier.
        timeout: Request timeout in seconds.
    """

    def __init__(
        self,
        api_key: str,
        model: str = _DEFAULT_EMBEDDING_MODEL,
        timeout: float = 30.0,
    ) -> None:
        self._client = AsyncGroq(api_key=api_key, timeout=timeout)
        self._model = model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts via Groq API.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors.

        Raises:
            LLMError: If the API call fails.
        """
        if not texts:
            return []

        logger.info(
            "Groq embedding request",
            extra={"model": self._model, "count": len(texts)},
        )

        try:
            response = await self._client.embeddings.create(
                model=self._model,
                input=texts,
            )
        except APIError as exc:
            logger.error("Groq embedding API error", extra={"error": str(exc)})
            raise LLMError(f"Embedding API error: {exc}") from exc
        except Exception as exc:
            logger.error("Unexpected embedding error", extra={"error": str(exc)})
            raise LLMError(f"Embedding error: {exc}") from exc

        return [item.embedding for item in response.data]

    async def close(self) -> None:
        """Close the underlying client."""
        await self._client.close()


# ---------------------------------------------------------------------------
# TF-IDF fallback (pure Python)
# ---------------------------------------------------------------------------


class TfIdfEmbeddingClient:
    """Simple TF-IDF embedding fallback that requires no external APIs.

    Builds a vocabulary from the provided texts and returns sparse-ish
    TF-IDF vectors.  Useful when the Groq embedding API is unavailable.
    """

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Compute TF-IDF vectors for a batch of texts."""
        if not texts:
            return []

        # Tokenise
        tokenised = [self._tokenise(t) for t in texts]

        # Build vocabulary from all texts
        vocab: dict[str, int] = {}
        for tokens in tokenised:
            for token in set(tokens):
                if token not in vocab:
                    vocab[token] = len(vocab)

        n_docs = len(texts)
        # Document frequency
        df: Counter[str] = Counter()
        for tokens in tokenised:
            for token in set(tokens):
                df[token] += 1

        # Build TF-IDF vectors
        vectors: list[list[float]] = []
        for tokens in tokenised:
            tf: Counter[str] = Counter(tokens)
            vec = [0.0] * len(vocab)
            for token, count in tf.items():
                idx = vocab[token]
                idf = math.log((n_docs + 1) / (df[token] + 1)) + 1
                vec[idx] = count * idf
            # L2 normalise
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            vectors.append([v / norm for v in vec])

        return vectors

    @staticmethod
    def _tokenise(text: str) -> list[str]:
        """Lowercase split tokenisation."""
        return [w for w in text.lower().split() if len(w) > 1]


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = math.sqrt(sum(x * x for x in a)) or 1.0
    norm_b = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (norm_a * norm_b)


def find_relevant_chunks(
    query_embedding: list[float],
    chunk_embeddings: list[tuple[str, list[float]]],
    top_k: int = 3,
) -> list[tuple[str, float]]:
    """Find the most relevant chunks by cosine similarity.

    Args:
        query_embedding: The query's embedding vector.
        chunk_embeddings: List of ``(chunk_text, embedding)`` tuples.
        top_k: Number of top results to return.

    Returns:
        List of ``(chunk_text, score)`` tuples, sorted by descending score.
    """
    scored = [
        (text, cosine_similarity(query_embedding, emb))
        for text, emb in chunk_embeddings
        if emb is not None
    ]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]

"""Repository layer for document and document-chunk persistence.

Firestore data model
--------------------
``users/{user_id}/documents/{doc_id}``
``users/{user_id}/document_chunks/{chunk_id}``
"""

from __future__ import annotations

import logging
from typing import Any

from google.cloud.firestore import AsyncClient

from helix.memory.models import Document, DocumentChunk

logger = logging.getLogger(__name__)


class DocumentRepository:
    """Read/write access to documents and their chunks in Firestore.

    Args:
        client: An async Firestore client.
    """

    def __init__(self, client: AsyncClient) -> None:
        self._client = client

    def _docs_ref(self, user_id: int) -> Any:
        """Return the ``documents`` sub-collection for *user_id*."""
        return self._client.collection("users").document(str(user_id)).collection("documents")

    def _chunks_ref(self, user_id: int) -> Any:
        """Return the ``document_chunks`` sub-collection for *user_id*."""
        return self._client.collection("users").document(str(user_id)).collection("document_chunks")

    # -- Document CRUD --------------------------------------------------

    async def create_document(self, doc: Document) -> str:
        """Persist document metadata and return its Firestore ID."""
        doc_ref = self._docs_ref(doc.user_id).document()
        await doc_ref.set(doc.to_dict())
        logger.info(
            "Document created",
            extra={"user_id": doc.user_id, "doc_id": doc_ref.id, "filename": doc.filename},
        )
        return doc_ref.id

    async def get_documents(self, user_id: int) -> list[Document]:
        """List all documents for a user, newest first."""
        query = self._docs_ref(user_id).order_by("created_at", direction="DESCENDING")
        docs = await query.get()
        return [Document.from_dict(d.to_dict(), d.id) for d in docs]

    async def delete_document(self, user_id: int, document_id: str) -> bool:
        """Delete a document and all its chunks. Returns ``True`` if it existed."""
        doc_ref = self._docs_ref(user_id).document(document_id)
        doc = await doc_ref.get()
        if not doc.exists:
            return False

        # Cascade-delete chunks
        chunks_query = self._chunks_ref(user_id).where("document_id", "==", document_id)
        chunk_docs = await chunks_query.get()
        for chunk_doc in chunk_docs:
            await chunk_doc.reference.delete()

        await doc_ref.delete()
        logger.info(
            "Document deleted (cascade)",
            extra={"user_id": user_id, "document_id": document_id, "chunks": len(chunk_docs)},
        )
        return True

    # -- Chunk CRUD -----------------------------------------------------

    async def save_chunks(self, chunks: list[DocumentChunk]) -> int:
        """Persist a batch of document chunks.

        Returns:
            The number of chunks saved.
        """
        for chunk in chunks:
            doc_ref = self._chunks_ref(chunk.user_id).document()
            await doc_ref.set(chunk.to_dict())
        logger.info("Chunks saved", extra={"count": len(chunks)})
        return len(chunks)

    async def get_chunks_for_document(self, user_id: int, document_id: str) -> list[DocumentChunk]:
        """Return all chunks for a specific document, ordered by index."""
        query = (
            self._chunks_ref(user_id)
            .where("document_id", "==", document_id)
            .order_by("chunk_index")
        )
        docs = await query.get()
        return [DocumentChunk.from_dict(d.to_dict(), d.id) for d in docs]

    async def get_all_chunks(self, user_id: int) -> list[DocumentChunk]:
        """Return all document chunks for a user."""
        docs = await self._chunks_ref(user_id).get()
        return [DocumentChunk.from_dict(d.to_dict(), d.id) for d in docs]

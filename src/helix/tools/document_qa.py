"""Built-in tool: document_qa — ask questions about uploaded documents.

Uses embedding-based retrieval to find relevant chunks and returns
them as context for the LLM.  Document ingestion happens in the
Telegram handler (photo/document upload); this tool handles querying.
"""

from __future__ import annotations

import logging
from typing import Any

from helix.llm.embeddings import EmbeddingClient, find_relevant_chunks
from helix.memory.document_repository import DocumentRepository
from helix.tools.base import Tool

logger = logging.getLogger(__name__)


class DocumentQATool(Tool):
    """Query uploaded documents using semantic search."""

    def __init__(
        self,
        document_repo: DocumentRepository,
        embedding_client: EmbeddingClient,
    ) -> None:
        self._repo = document_repo
        self._embeddings = embedding_client

    @property
    def name(self) -> str:
        return "document_qa"

    @property
    def description(self) -> str:
        return (
            "Query your uploaded documents. "
            "Commands: 'list' (show all documents), "
            "'ask' (ask a question — finds relevant passages), "
            "'delete' (remove a document and its chunks)."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "enum": ["list", "ask", "delete"],
                    "description": "The action to perform.",
                },
                "question": {
                    "type": "string",
                    "description": "The question to ask (required for 'ask').",
                },
                "document_id": {
                    "type": "string",
                    "description": "Document ID (required for 'delete').",
                },
            },
            "required": ["command"],
        }

    async def run(self, **kwargs: Any) -> str:
        """Dispatch to the appropriate sub-command."""
        command = kwargs.get("command", "")
        user_id: int = kwargs.get("_user_id", 0)

        if not user_id:
            return "Error: could not determine user identity."

        if command == "list":
            return await self._list(user_id)
        if command == "ask":
            return await self._ask(user_id, kwargs)
        if command == "delete":
            return await self._delete(user_id, kwargs)

        return f"Error: unknown command '{command}'. Use 'list', 'ask', or 'delete'."

    async def _list(self, user_id: int) -> str:
        """List all uploaded documents."""
        docs = await self._repo.get_documents(user_id)
        if not docs:
            return "No documents uploaded yet. Send me a PDF, DOCX, or TXT file to get started."

        lines = ["📚 **Your Documents**:"]
        for d in docs:
            lines.append(
                f"  📄 `{d.id}` — {d.filename} ({d.chunk_count} chunks, {d.page_count} pages)"
            )
        return "\n".join(lines)

    async def _ask(self, user_id: int, kwargs: dict[str, Any]) -> str:
        """Embed the question, find relevant chunks, return context."""
        question = kwargs.get("question", "").strip()
        if not question:
            return "Error: 'question' is required for the 'ask' command."

        # Get all chunks with embeddings
        all_chunks = await self._repo.get_all_chunks(user_id)
        if not all_chunks:
            return "No document chunks available. Upload a document first."

        chunk_pairs = [(c.text, c.embedding) for c in all_chunks if c.embedding]
        if not chunk_pairs:
            return "Documents exist but have no embeddings. Try re-uploading."

        # Embed the question
        try:
            query_embeddings = await self._embeddings.embed([question])
            query_vec = query_embeddings[0]
        except Exception:
            logger.exception("Failed to embed question")
            return "Error: could not generate embedding for the question."

        # Find relevant chunks
        relevant = find_relevant_chunks(query_vec, chunk_pairs, top_k=3)
        if not relevant:
            return "No relevant passages found for your question."

        lines = [f"📖 **Relevant passages for:** _{question}_\n"]
        for i, (text, score) in enumerate(relevant, 1):
            # Truncate long chunks for readability
            preview = text[:500] + "…" if len(text) > 500 else text
            lines.append(f"**{i}.** (score: {score:.2f})\n{preview}\n")

        return "\n".join(lines)

    async def _delete(self, user_id: int, kwargs: dict[str, Any]) -> str:
        """Delete a document and its chunks."""
        doc_id = kwargs.get("document_id", "").strip()
        if not doc_id:
            return "Error: 'document_id' is required. Use 'list' to see your documents."

        deleted = await self._repo.delete_document(user_id, doc_id)
        if not deleted:
            return f"Document `{doc_id}` not found."
        return f"✅ Document `{doc_id}` and all its chunks deleted."

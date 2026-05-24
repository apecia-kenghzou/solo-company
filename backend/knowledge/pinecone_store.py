"""Pinecone vector store integration for the Solo Agent OS knowledge base."""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Optional

from pinecone import Pinecone, ServerlessSpec

from backend.config.settings import settings
from backend.knowledge.embeddings import embed_text, embed_batch

logger = logging.getLogger(__name__)

# Embedding dimension for text-embedding-3-large
EMBEDDING_DIM = 3072


@lru_cache(maxsize=1)
def _get_pinecone_client() -> Pinecone:
    """Return a cached Pinecone client instance."""
    return Pinecone(api_key=settings.pinecone_api_key)


def _get_index():
    """Return the Pinecone index, creating it if it does not exist."""
    pc = _get_pinecone_client()
    index_name = settings.pinecone_index_name

    existing_indexes = [idx.name for idx in pc.list_indexes()]
    if index_name not in existing_indexes:
        logger.info("Creating Pinecone index '%s'", index_name)
        pc.create_index(
            name=index_name,
            dimension=EMBEDDING_DIM,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )

    return pc.Index(index_name)


class PineconeStore:
    """Namespace-scoped Pinecone operations (one namespace per user_id)."""

    def __init__(self, namespace: str) -> None:
        self.namespace = namespace
        self._index = None

    @property
    def index(self):
        if self._index is None:
            self._index = _get_index()
        return self._index

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def upsert(self, doc_id: str, text: str, metadata: dict) -> None:
        """Embed text and upsert a single vector with metadata."""
        try:
            vector = await embed_text(text)
            meta = {**metadata, "text": text}
            self.index.upsert(
                vectors=[{"id": doc_id, "values": vector, "metadata": meta}],
                namespace=self.namespace,
            )
            logger.debug("Upserted doc '%s' into namespace '%s'", doc_id, self.namespace)
        except Exception as exc:
            logger.error("Failed to upsert doc '%s': %s", doc_id, exc)
            raise

    async def upsert_batch(self, docs: list[dict]) -> None:
        """Batch upsert for efficiency.

        Each doc in `docs` must have keys: id, text, metadata.
        """
        if not docs:
            return
        try:
            texts = [d["text"] for d in docs]
            vectors = await embed_batch(texts)
            records = [
                {
                    "id": d["id"],
                    "values": vec,
                    "metadata": {**d.get("metadata", {}), "text": d["text"]},
                }
                for d, vec in zip(docs, vectors)
            ]
            # Pinecone recommends batches of up to 100 vectors
            batch_size = 100
            for i in range(0, len(records), batch_size):
                self.index.upsert(
                    vectors=records[i : i + batch_size],
                    namespace=self.namespace,
                )
            logger.debug(
                "Batch upserted %d docs into namespace '%s'", len(docs), self.namespace
            )
        except Exception as exc:
            logger.error("Failed to batch upsert: %s", exc)
            raise

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def query(
        self,
        query_text: str,
        top_k: int = 5,
        filter: Optional[dict] = None,
    ) -> list[dict]:
        """Embed query_text, search Pinecone, return list of result dicts.

        Each result: {id, score, text, metadata}
        """
        try:
            query_vector = await embed_text(query_text)
            kwargs = dict(
                vector=query_vector,
                top_k=top_k,
                namespace=self.namespace,
                include_metadata=True,
            )
            if filter:
                kwargs["filter"] = filter

            response = self.index.query(**kwargs)
            results = []
            for match in response.matches:
                meta = match.metadata or {}
                text = meta.pop("text", "")
                results.append(
                    {
                        "id": match.id,
                        "score": match.score,
                        "text": text,
                        "metadata": meta,
                    }
                )
            return results
        except Exception as exc:
            logger.error("Query failed: %s", exc)
            raise

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    async def delete(self, doc_id: str) -> None:
        """Delete a single vector by id."""
        try:
            self.index.delete(ids=[doc_id], namespace=self.namespace)
            logger.debug("Deleted doc '%s' from namespace '%s'", doc_id, self.namespace)
        except Exception as exc:
            logger.error("Failed to delete doc '%s': %s", doc_id, exc)
            raise

    async def delete_namespace(self) -> None:
        """Delete all vectors in this namespace."""
        try:
            self.index.delete(delete_all=True, namespace=self.namespace)
            logger.info("Deleted all vectors in namespace '%s'", self.namespace)
        except Exception as exc:
            logger.error("Failed to delete namespace '%s': %s", self.namespace, exc)
            raise

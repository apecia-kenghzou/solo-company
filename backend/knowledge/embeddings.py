"""Embedding utilities using OpenAI text-embedding-3-large."""
from openai import AsyncOpenAI
from backend.config.settings import settings

client = AsyncOpenAI(api_key=settings.openai_api_key)


async def embed_text(text: str) -> list[float]:
    """Embed a single piece of text."""
    response = await client.embeddings.create(
        model="text-embedding-3-large",
        input=text,
    )
    return response.data[0].embedding


async def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts."""
    response = await client.embeddings.create(
        model="text-embedding-3-large",
        input=texts,
    )
    return [item.embedding for item in response.data]

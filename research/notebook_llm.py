from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, TextLoader

from config import cfg
from memory.qdrant_memory import QdrantMemory


class NotebookLLM:
    """Ingests PDF/MD/TXT files and answers questions via Qdrant-backed RAG."""

    def __init__(self, collection: str = "notebook_llm") -> None:
        self._splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        self._store = QdrantMemory(collection=collection)
        self._ingested: list[str] = []

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    def ingest(self, file_path: str | Path) -> int:
        """Load and chunk a file, embed via Qdrant. Returns number of chunks stored."""
        path = Path(file_path)
        if path.suffix.lower() == ".pdf":
            loader = PyPDFLoader(str(path))
        else:
            loader = TextLoader(str(path), encoding="utf-8")

        docs = loader.load()
        chunks = self._splitter.split_documents(docs)

        for chunk in chunks:
            self._store.upsert(
                chunk.page_content,
                metadata={"source": str(path), "source_name": path.name},
            )

        self._ingested.append(str(path))
        return len(chunks)

    def ingest_text(self, text: str, source_name: str = "inline") -> int:
        """Ingest raw text directly (useful for programmatic ingestion)."""
        chunks = self._splitter.split_text(text)
        for chunk in chunks:
            self._store.upsert(chunk, metadata={"source": source_name, "source_name": source_name})
        return len(chunks)

    # ------------------------------------------------------------------
    # Retrieval + generation
    # ------------------------------------------------------------------

    def query(self, question: str, k: int = 5) -> str:
        hits = self._store.search(question, k=k)
        if not hits:
            return "No relevant content found. Please ingest documents first."

        context = "\n\n".join(
            f"[source: {h.get('source_name', 'unknown')}]\n{h['text']}" for h in hits
        )

        from anthropic import Anthropic
        client = Anthropic(api_key=cfg.claude_api_key)
        msg = client.messages.create(
            model=cfg.claude_model,
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": (
                    f"Answer the question using only the provided context. "
                    f"Cite sources where possible.\n\n"
                    f"Context:\n{context}\n\n"
                    f"Question: {question}"
                ),
            }],
        )
        return msg.content[0].text

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    @property
    def ingested_sources(self) -> list[str]:
        return list(self._ingested)

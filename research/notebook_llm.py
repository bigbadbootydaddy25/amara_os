from __future__ import annotations

from pathlib import Path

from core.llm_client import llm
from memory.qdrant_memory import QdrantMemory


def _make_splitter() -> object:
    try:
        from langchain.text_splitter import RecursiveCharacterTextSplitter
    except ImportError:
        from langchain_text_splitters import RecursiveCharacterTextSplitter  # type: ignore[no-redef]
    return RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)


def _load_docs(path: Path) -> list:
    try:
        if path.suffix.lower() == ".pdf":
            from langchain_community.document_loaders import PyPDFLoader
            return PyPDFLoader(str(path)).load()
        else:
            from langchain_community.document_loaders import TextLoader
            return TextLoader(str(path), encoding="utf-8").load()
    except ImportError:
        # Fallback: read plain text
        return [type("Doc", (), {"page_content": path.read_text(encoding="utf-8", errors="ignore")})()]


class NotebookLLM:
    """Ingests PDF/MD/TXT files and answers questions via Qdrant-backed RAG."""

    def __init__(self, collection: str = "notebook_llm") -> None:
        self._splitter = _make_splitter()
        self._store = QdrantMemory(collection=collection)
        self._ingested: list[str] = []

    def ingest(self, file_path: str | Path) -> int:
        path = Path(file_path)
        docs = _load_docs(path)
        chunks = self._splitter.split_documents(docs)
        for chunk in chunks:
            self._store.upsert(
                chunk.page_content,
                metadata={"source": str(path), "source_name": path.name},
            )
        self._ingested.append(str(path))
        return len(chunks)

    def ingest_text(self, text: str, source_name: str = "inline") -> int:
        chunks = self._splitter.split_text(text)
        for chunk in chunks:
            self._store.upsert(chunk, metadata={"source": source_name, "source_name": source_name})
        return len(chunks)

    def query(self, question: str, k: int = 5) -> str:
        hits = self._store.search(question, k=k)
        if not hits:
            return "No relevant content found. Please ingest documents first."

        context = "\n\n".join(
            f"[source: {h.get('source_name', 'unknown')}]\n{h['text']}" for h in hits
        )
        prompt = (
            f"Answer the question using only the provided context. "
            f"Cite sources where possible.\n\n"
            f"Context:\n{context}\n\n"
            f"Question: {question}"
        )
        return llm.chat(prompt)

    @property
    def ingested_sources(self) -> list[str]:
        return list(self._ingested)

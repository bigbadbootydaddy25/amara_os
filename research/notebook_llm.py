from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.vectorstores import FAISS

from config import cfg


class NotebookLLM:
    """Ingests PDF/MD/TXT files and answers questions via RAG."""

    def __init__(self) -> None:
        self._embeddings = OllamaEmbeddings(
            base_url=cfg.ollama_base_url,
            model="nomic-embed-text",
        )
        self._splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        self._store: FAISS | None = None

    def ingest(self, file_path: str | Path) -> None:
        path = Path(file_path)
        if path.suffix.lower() == ".pdf":
            loader = PyPDFLoader(str(path))
        else:
            loader = TextLoader(str(path), encoding="utf-8")

        docs = loader.load()
        chunks = self._splitter.split_documents(docs)

        if self._store is None:
            self._store = FAISS.from_documents(chunks, self._embeddings)
        else:
            self._store.add_documents(chunks)

    def query(self, question: str, k: int = 4) -> str:
        if self._store is None:
            return "No documents ingested yet."

        docs = self._store.similarity_search(question, k=k)
        context = "\n\n".join(d.page_content for d in docs)

        from anthropic import Anthropic
        client = Anthropic(api_key=cfg.claude_api_key)
        msg = client.messages.create(
            model=cfg.claude_model,
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": f"Context:\n{context}\n\nQuestion: {question}",
                }
            ],
        )
        return msg.content[0].text

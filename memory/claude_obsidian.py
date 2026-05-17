from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from anthropic import Anthropic

from config import cfg


class ClaudeObsidian:
    """Claude-powered Obsidian vault integration.

    Adds AI-driven note creation with auto-wiki-links, smart semantic search,
    vault summarisation, and backlink suggestions — on top of the raw filesystem
    operations in memory.vault.Vault.
    """

    def __init__(self) -> None:
        self._vault = Path(os.path.expanduser(cfg.obsidian_vault_path))
        self._claude = Anthropic(api_key=cfg.claude_api_key)

    # ------------------------------------------------------------------
    # Smart search
    # ------------------------------------------------------------------

    def smart_search(self, query: str, limit: int = 8) -> list[dict[str, Any]]:
        """Use Claude to reformulate the query, then full-text search the vault."""
        refined = self._refine_query(query)
        results: list[dict[str, Any]] = []
        if not self._vault.exists():
            return results

        refined_lower = refined.lower()
        for md_file in self._vault.rglob("*.md"):
            content = md_file.read_text(encoding="utf-8", errors="ignore")
            if refined_lower in content.lower() or query.lower() in content.lower():
                results.append({
                    "title": md_file.stem,
                    "path": str(md_file),
                    "excerpt": content[:400],
                    "refined_query": refined,
                })
            if len(results) >= limit:
                break
        return results

    # ------------------------------------------------------------------
    # Intelligent note creation
    # ------------------------------------------------------------------

    def create_linked_note(self, title: str, context: str) -> Path:
        """Ask Claude to draft a note and auto-insert [[wiki-links]] to existing notes."""
        existing_titles = self._list_note_titles()
        content = self._draft_note(title, context, existing_titles)
        return self._write_note(title, content)

    def append_to_note(self, title: str, new_content: str) -> Path:
        """Claude-summarises new_content and appends it as a new section."""
        note_path = self._vault / f"{title}.md"
        existing = note_path.read_text(encoding="utf-8") if note_path.exists() else ""
        summary = self._summarise_for_append(new_content)
        updated = existing + f"\n\n## Added\n{summary}"
        note_path.write_text(updated, encoding="utf-8")
        return note_path

    # ------------------------------------------------------------------
    # Vault analysis
    # ------------------------------------------------------------------

    def analyze_vault(self) -> dict[str, Any]:
        """Return a high-level map of the vault (titles, link graph, topic clusters)."""
        notes = self._load_all_notes()
        if not notes:
            return {"note_count": 0, "topics": [], "link_graph": {}}

        titles = [n["title"] for n in notes]
        link_graph = {n["title"]: self._extract_wikilinks(n["content"]) for n in notes}
        topics = self._cluster_topics(notes)
        return {"note_count": len(notes), "topics": topics, "link_graph": link_graph}

    def suggest_connections(self, note_title: str) -> list[str]:
        """Ask Claude which existing notes are most related to the given note."""
        note_path = self._vault / f"{note_title}.md"
        if not note_path.exists():
            return []

        content = note_path.read_text(encoding="utf-8", errors="ignore")
        candidates = self._list_note_titles()
        candidates = [t for t in candidates if t != note_title]
        if not candidates:
            return []

        prompt = (
            f"Here is a note titled '{note_title}':\n\n{content[:1500]}\n\n"
            f"From this list of existing notes, which 5 are most closely related?\n"
            f"{chr(10).join(f'- {t}' for t in candidates[:80])}\n\n"
            "Return only the note titles, one per line."
        )
        msg = self._claude.messages.create(
            model=cfg.claude_model,
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        lines = msg.content[0].text.strip().splitlines()
        return [l.strip("- ").strip() for l in lines if l.strip()]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _refine_query(self, query: str) -> str:
        prompt = (
            f"Rewrite this search query to maximise recall in an Obsidian markdown vault. "
            f"Return only the rewritten query, nothing else.\n\nQuery: {query}"
        )
        msg = self._claude.messages.create(
            model=cfg.claude_model,
            max_tokens=64,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()

    def _draft_note(self, title: str, context: str, existing_titles: list[str]) -> str:
        titles_sample = "\n".join(f"- {t}" for t in existing_titles[:60])
        prompt = (
            f"Write an Obsidian markdown note titled '{title}'.\n"
            f"Use the following context:\n{context}\n\n"
            f"Where relevant, insert [[wiki-links]] to these existing notes:\n{titles_sample}\n\n"
            "Format: frontmatter (tags, date), then headers and content. "
            "Be concise and factual."
        )
        msg = self._claude.messages.create(
            model=cfg.claude_model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()

    def _summarise_for_append(self, text: str) -> str:
        msg = self._claude.messages.create(
            model=cfg.claude_model,
            max_tokens=512,
            messages=[{
                "role": "user",
                "content": f"Summarise the following for an Obsidian note section:\n\n{text}",
            }],
        )
        return msg.content[0].text.strip()

    def _cluster_topics(self, notes: list[dict[str, Any]]) -> list[str]:
        combined = "\n".join(f"- {n['title']}: {n['content'][:200]}" for n in notes[:30])
        prompt = (
            f"Given these Obsidian notes, identify the 5-8 main topic clusters present. "
            f"Return one topic per line.\n\n{combined}"
        )
        msg = self._claude.messages.create(
            model=cfg.claude_model,
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        return [l.strip("- ").strip() for l in msg.content[0].text.strip().splitlines() if l.strip()]

    def _list_note_titles(self) -> list[str]:
        if not self._vault.exists():
            return []
        return [p.stem for p in self._vault.rglob("*.md")]

    def _load_all_notes(self) -> list[dict[str, Any]]:
        if not self._vault.exists():
            return []
        notes = []
        for p in self._vault.rglob("*.md"):
            notes.append({
                "title": p.stem,
                "path": str(p),
                "content": p.read_text(encoding="utf-8", errors="ignore"),
            })
        return notes

    def _write_note(self, title: str, content: str) -> Path:
        self._vault.mkdir(parents=True, exist_ok=True)
        path = self._vault / f"{title}.md"
        path.write_text(content, encoding="utf-8")
        return path

    @staticmethod
    def _extract_wikilinks(content: str) -> list[str]:
        return re.findall(r"\[\[([^\]]+)\]\]", content)

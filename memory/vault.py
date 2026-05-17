from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from config import cfg


class Vault:
    def __init__(self) -> None:
        self._vault_path = Path(os.path.expanduser(cfg.obsidian_vault_path))

    def search_notes(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        if not self._vault_path.exists():
            return results

        query_lower = query.lower()
        for md_file in self._vault_path.rglob("*.md"):
            content = md_file.read_text(encoding="utf-8", errors="ignore")
            if query_lower in content.lower():
                results.append({"title": md_file.stem, "path": str(md_file), "excerpt": content[:300]})
            if len(results) >= limit:
                break

        return results

    def create_note(self, title: str, content: str) -> Path:
        self._vault_path.mkdir(parents=True, exist_ok=True)
        note_path = self._vault_path / f"{title}.md"
        note_path.write_text(content, encoding="utf-8")
        return note_path

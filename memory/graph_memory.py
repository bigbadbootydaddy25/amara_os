from __future__ import annotations

from typing import Any

from neo4j import GraphDatabase

from config import cfg


class GraphMemory:
    def __init__(self) -> None:
        self._driver = GraphDatabase.driver(
            cfg.neo4j_uri,
            auth=(cfg.neo4j_user, cfg.neo4j_password),
        )

    def upsert(self, prompt: str, response: str) -> None:
        keywords = self._extract_keywords(prompt)
        with self._driver.session() as session:
            session.execute_write(self._merge_nodes, prompt, response, keywords)

    def retrieve(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        keywords = self._extract_keywords(query)
        with self._driver.session() as session:
            result = session.execute_read(self._match_nodes, keywords, limit)
        return result

    def close(self) -> None:
        self._driver.close()

    @staticmethod
    def _merge_nodes(tx: Any, prompt: str, response: str, keywords: list[str]) -> None:
        tx.run(
            """
            MERGE (p:Prompt {text: $prompt})
            MERGE (r:Response {text: $response})
            MERGE (p)-[:ANSWERED_BY]->(r)
            SET p.keywords = $keywords
            """,
            prompt=prompt,
            response=response,
            keywords=keywords,
        )

    @staticmethod
    def _match_nodes(tx: Any, keywords: list[str], limit: int) -> list[dict[str, Any]]:
        result = tx.run(
            """
            MATCH (p:Prompt)-[:ANSWERED_BY]->(r:Response)
            WHERE ANY(kw IN $keywords WHERE kw IN p.keywords)
            RETURN p.text AS prompt, r.text AS response
            LIMIT $limit
            """,
            keywords=keywords,
            limit=limit,
        )
        return [{"prompt": rec["prompt"], "response": rec["response"]} for rec in result]

    @staticmethod
    def _extract_keywords(text: str) -> list[str]:
        stop_words = {"a", "an", "the", "is", "in", "it", "of", "to", "and", "or", "for"}
        return [w.lower() for w in text.split() if w.lower() not in stop_words][:10]

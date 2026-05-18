from __future__ import annotations

import logging
from typing import Any

from langchain_core.prompts import PromptTemplate

from core.llm_client import llm
from memory.episodic import EpisodicMemory
from memory.graph_memory import GraphMemory

logger = logging.getLogger(__name__)


def _make_tools(episodic: EpisodicMemory, graph: GraphMemory) -> list[Any]:
    try:
        from langchain.tools import tool
    except ImportError:
        from langchain_core.tools import tool  # type: ignore[no-redef]

    @tool
    def recall_memory(query: str) -> str:
        """Recall relevant memories for the given query."""
        try:
            results = episodic.recall(query)
            return "\n".join(r.get("content", "") for r in results) or "No memories found."
        except Exception as exc:
            return f"Memory unavailable: {exc}"

    @tool
    def query_knowledge_graph(query: str) -> str:
        """Query the knowledge graph for related prompt/response pairs."""
        try:
            results = graph.retrieve(query)
            return "\n".join(f"{r['prompt']} → {r['response']}" for r in results) or "No results."
        except Exception as exc:
            return f"Graph unavailable: {exc}"

    @tool
    def semantic_search(query: str) -> str:
        """Search the Qdrant vector store for semantically similar past interactions."""
        try:
            from memory.qdrant_memory import QdrantMemory
            qm = QdrantMemory()
            hits = qm.search(query)
            return "\n".join(f"[{h['score']:.2f}] {h['text']}" for h in hits) or "No results."
        except Exception as exc:
            return f"Vector search unavailable: {exc}"

    @tool
    def search_obsidian(query: str) -> str:
        """Search the Obsidian vault for notes matching the query."""
        try:
            from memory.claude_obsidian import ClaudeObsidian
            co = ClaudeObsidian()
            results = co.smart_search(query, limit=4)
            return "\n\n".join(f"{r['title']}: {r['excerpt']}" for r in results) or "No notes found."
        except Exception as exc:
            return f"Obsidian unavailable: {exc}"

    @tool
    def create_obsidian_note(title_and_context: str) -> str:
        """Create a new Obsidian note. Input format: 'Title|context text'."""
        try:
            from memory.claude_obsidian import ClaudeObsidian
            if "|" in title_and_context:
                title, context = title_and_context.split("|", 1)
            else:
                title, context = title_and_context, title_and_context
            co = ClaudeObsidian()
            path = co.create_linked_note(title.strip(), context.strip())
            return f"Note created: {path}"
        except Exception as exc:
            return f"Note creation failed: {exc}"

    @tool
    def query_documents(question: str) -> str:
        """Query ingested PDF/MD/TXT documents via the NotebookLLM RAG pipeline."""
        try:
            from research.notebook_llm import NotebookLLM
            nb = NotebookLLM()
            return nb.query(question)
        except Exception as exc:
            return f"Document query unavailable: {exc}"

    @tool
    def run_orchestrator(prompt: str) -> str:
        """Run the main orchestrator with the given prompt."""
        import asyncio
        from core.orchestrator import Orchestrator
        orch = Orchestrator()
        return asyncio.run(orch.run(prompt))

    return [
        recall_memory,
        query_knowledge_graph,
        semantic_search,
        search_obsidian,
        create_obsidian_note,
        query_documents,
        run_orchestrator,
    ]


_REACT_TEMPLATE = """Answer the following questions as best you can. You have access to the following tools:

{tools}

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Begin!

Question: {input}
Thought:{agent_scratchpad}"""


class AegisAgent:
    def __init__(self) -> None:
        self._episodic = _safe_init(
            lambda: EpisodicMemory(), "EpisodicMemory"
        )
        self._graph = _safe_init(
            lambda: GraphMemory(), "GraphMemory"
        )
        self._executor = self._build_executor()

    def _build_executor(self) -> Any:
        try:
            from langchain.agents import AgentExecutor, create_react_agent
        except ImportError:
            from langchain_classic.agents import AgentExecutor, create_react_agent  # type: ignore[no-redef]

        tools = _make_tools(self._episodic, self._graph)
        lc_llm = llm.langchain_llm
        prompt = PromptTemplate.from_template(_REACT_TEMPLATE)
        agent = create_react_agent(lc_llm, tools, prompt)
        return AgentExecutor(agent=agent, tools=tools, verbose=False, handle_parsing_errors=True)

    def run(self, prompt: str) -> str:
        result = self._executor.invoke({"input": prompt})
        return result.get("output", "")


def _safe_init(factory: Any, name: str) -> Any:
    try:
        return factory()
    except Exception as exc:
        logger.warning("%s init failed: %s", name, exc)

        class _Stub:
            def recall(self, *a: Any, **kw: Any) -> list:
                return []
            def retrieve(self, *a: Any, **kw: Any) -> list:
                return []
            def store(self, *a: Any, **kw: Any) -> None:
                pass
            def upsert(self, *a: Any, **kw: Any) -> None:
                pass

        return _Stub()

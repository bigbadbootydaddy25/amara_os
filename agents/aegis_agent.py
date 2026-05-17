from __future__ import annotations

from typing import Any

from langchain.agents import AgentExecutor, create_react_agent
from langchain.tools import tool
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import PromptTemplate

from config import cfg
from memory.episodic import EpisodicMemory
from memory.graph_memory import GraphMemory


def _make_tools(episodic: EpisodicMemory, graph: GraphMemory) -> list[Any]:
    @tool
    def recall_memory(query: str) -> str:
        """Recall relevant memories for the given query."""
        results = episodic.recall(query)
        return "\n".join(r.get("content", "") for r in results) or "No memories found."

    @tool
    def query_knowledge_graph(query: str) -> str:
        """Query the knowledge graph for related prompt/response pairs."""
        results = graph.retrieve(query)
        return "\n".join(f"{r['prompt']} → {r['response']}" for r in results) or "No results."

    @tool
    def semantic_search(query: str) -> str:
        """Search the Qdrant vector store for semantically similar past interactions."""
        from memory.qdrant_memory import QdrantMemory
        qm = QdrantMemory()
        hits = qm.search(query)
        return "\n".join(f"[{h['score']:.2f}] {h['text']}" for h in hits) or "No results."

    @tool
    def search_obsidian(query: str) -> str:
        """Search the Obsidian vault for notes matching the query."""
        from memory.claude_obsidian import ClaudeObsidian
        co = ClaudeObsidian()
        results = co.smart_search(query, limit=4)
        return "\n\n".join(f"{r['title']}: {r['excerpt']}" for r in results) or "No notes found."

    @tool
    def create_obsidian_note(title_and_context: str) -> str:
        """Create a new Obsidian note. Input format: 'Title|context text'."""
        from memory.claude_obsidian import ClaudeObsidian
        if "|" in title_and_context:
            title, context = title_and_context.split("|", 1)
        else:
            title, context = title_and_context, title_and_context
        co = ClaudeObsidian()
        path = co.create_linked_note(title.strip(), context.strip())
        return f"Note created: {path}"

    @tool
    def query_documents(question: str) -> str:
        """Query ingested PDF/MD/TXT documents via the NotebookLLM RAG pipeline."""
        from research.notebook_llm import NotebookLLM
        nb = NotebookLLM()
        return nb.query(question)

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
        self._episodic = EpisodicMemory()
        self._graph = GraphMemory()
        self._llm = ChatAnthropic(
            model=cfg.claude_model,
            api_key=cfg.claude_api_key,
        )
        tools = _make_tools(self._episodic, self._graph)
        prompt = PromptTemplate.from_template(_REACT_TEMPLATE)
        agent = create_react_agent(self._llm, tools, prompt)
        self._executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

    def run(self, prompt: str) -> str:
        result = self._executor.invoke({"input": prompt})
        return result.get("output", "")

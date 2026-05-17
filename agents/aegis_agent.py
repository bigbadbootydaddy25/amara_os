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
    def run_orchestrator(prompt: str) -> str:
        """Run the main orchestrator with the given prompt."""
        import asyncio
        from core.orchestrator import Orchestrator
        orch = Orchestrator()
        return asyncio.run(orch.run(prompt))

    return [recall_memory, query_knowledge_graph, run_orchestrator]


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

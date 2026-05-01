import { ChatAnthropic } from '@langchain/anthropic';
import { HumanMessage, SystemMessage } from '@langchain/core/messages';
import { runQuery } from '@/lib/neural-graph/neo4j-client';

export interface AgentConfig {
  market: string;
  strategy: string;
  dataTarget: string;
}

export interface AgentFinding {
  type: string;
  data: unknown;
  summary: string;
}

export interface AgentRunResult {
  market: string;
  strategy: string;
  status: 'SUCCESS' | 'PARTIAL' | 'FAILED';
  findings: AgentFinding[];
  errors: string[];
  reasoning?: string;
}

// Shared models per AMARA spec
export const reasoningModel = new ChatAnthropic({
  apiKey: process.env.ANTHROPIC_API_KEY,
  model: 'claude-sonnet-4-6',
  maxTokens: 4096,
  streaming: true,
});

export const analysisModel = new ChatAnthropic({
  apiKey: process.env.ANTHROPIC_API_KEY,
  model: 'claude-opus-4-7',
  maxTokens: 8192,
});

export const fastModel = new ChatAnthropic({
  apiKey: process.env.ANTHROPIC_API_KEY,
  model: 'claude-haiku-4-5-20251001',
  maxTokens: 2048,
});

export abstract class HermesAgent {
  protected config: AgentConfig;

  constructor(config: AgentConfig) {
    this.config = config;
  }

  protected async think(prompt: string, systemPrompt?: string): Promise<string> {
    const messages = [
      new SystemMessage(
        systemPrompt ??
          `You are a Hermes market intelligence agent scanning ${this.config.market} for ${this.config.strategy} opportunities. Be concise and factual.`,
      ),
      new HumanMessage(prompt),
    ];

    let output = '';
    const stream = await reasoningModel.stream(messages);
    for await (const chunk of stream) {
      output += typeof chunk.content === 'string' ? chunk.content : '';
    }
    return output.trim();
  }

  protected async logToNeo4j(agentName: string, market: string, status: string): Promise<void> {
    try {
      await runQuery(
        `MERGE (a:Agent {name: $agentName})
         MERGE (m:Market {name: $market})
         MERGE (a)-[:ACTIVE_IN]->(m)
         SET a.lastRun = datetime(), a.lastStatus = $status`,
        { agentName, market, status },
      );
    } catch {
      // Neo4j optional — don't crash agent if DB is down
    }
  }

  // Stub for LangFuse tracing — wire real client when LANGFUSE_PUBLIC_KEY is set
  protected trace(event: string, data?: unknown): void {
    if (process.env.LANGFUSE_PUBLIC_KEY) {
      // TODO: initialise LangFuse client and emit trace
    }
    if (process.env.NODE_ENV !== 'production') {
      console.debug(`[HERMES:${this.config.market}] ${event}`, data ?? '');
    }
  }

  abstract run(): Promise<AgentRunResult>;
}

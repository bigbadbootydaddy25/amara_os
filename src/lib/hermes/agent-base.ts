import { ChatAnthropic } from '@langchain/anthropic';
import { HumanMessage, SystemMessage } from '@langchain/core/messages';
import { runQuery } from '@/lib/neural-graph/neo4j-client';
import { getLangfuse, writeLocalTrace } from '@/lib/observability/langfuse-client';
import { recordUsage } from '@/lib/observability/cost-tracker';

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

  protected trace(event: string, data?: unknown): void {
    const lf = getLangfuse();
    if (lf) {
      lf.event({
        traceId: `${this.config.market}_${this.config.strategy}_${Date.now()}`,
        name: event,
        input: data,
        metadata: { market: this.config.market, strategy: this.config.strategy },
      });
    }
    // Always write local fallback
    writeLocalTrace({
      agentName: `${this.config.strategy}@${this.config.market}`,
      market: this.config.market,
      event,
      data,
      timestamp: new Date().toISOString(),
    });
  }

  protected recordTokenUsage(model: string, inputTokens: number, outputTokens: number): void {
    recordUsage({
      model,
      inputTokens,
      outputTokens,
      agentName: this.config.strategy,
      market: this.config.market,
      timestamp: new Date().toISOString(),
    });
  }

  abstract run(): Promise<AgentRunResult>;
}

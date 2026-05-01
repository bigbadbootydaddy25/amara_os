import { runQuery } from '@/lib/neural-graph/neo4j-client';
import { HermesAgent, AgentRunResult } from './agent-base';

export class BuyerAgent extends HermesAgent {
  async run(): Promise<AgentRunResult> {
    this.trace('start');
    const result: AgentRunResult = {
      market: this.config.market,
      strategy: this.config.strategy,
      status: 'SUCCESS',
      findings: [],
      errors: [],
    };

    // Pull buyers active in this market from Neo4j
    let buyers: Array<Record<string, unknown>> = [];
    try {
      buyers = await runQuery<Record<string, unknown>>(
        `MATCH (b:Buyer)-[:ACTIVE_IN]->(m:Market {name: $market})
         OPTIONAL MATCH (b)-[r:LIKELY_TO_BUY]->(d:Deal)
         RETURN b.name AS name, b.priceMin AS priceMin, b.priceMax AS priceMax,
                b.isRepeat AS isRepeat, b.isWhale AS isWhale,
                count(r) AS matchCount, max(r.score) AS topScore
         ORDER BY topScore DESC`,
        { market: this.config.market.toUpperCase() },
      );
    } catch (err) {
      result.errors.push(`Neo4j query failed: ${err}`);
      result.status = 'PARTIAL';
    }

    if (buyers.length === 0) {
      result.findings.push({
        type: 'NO_BUYERS',
        data: null,
        summary: `No buyers found in Neo4j for market ${this.config.market}`,
      });
      this.trace('no_buyers');
    } else {
      const buyerSummary = buyers
        .slice(0, 10)
        .map(
          (b) =>
            `${b.name}: $${b.priceMin ?? '?'}–$${b.priceMax ?? '?'}, repeat=${b.isRepeat}, whale=${b.isWhale}, matches=${b.matchCount}`,
        )
        .join('\n');

      const reasoning = await this.think(
        `Market: ${this.config.market}\nTop buyers:\n${buyerSummary}\n\nWhich buyers should Scott call first this week and why?`,
      ).catch((err) => {
        result.errors.push(`Reasoning failed: ${err}`);
        return '';
      });

      result.findings.push({
        type: 'BUYER_ANALYSIS',
        data: buyers,
        summary: reasoning || `${buyers.length} buyers active in ${this.config.market}`,
      });
      result.reasoning = reasoning;
      this.trace('analysis_complete', { buyerCount: buyers.length });
    }

    await this.logToNeo4j('BuyerAgent', this.config.market, result.status);
    return result;
  }
}

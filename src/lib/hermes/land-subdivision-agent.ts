import { runQuery } from '@/lib/neural-graph/neo4j-client';
import { HermesAgent, analysisModel, AgentRunResult } from './agent-base';
import { HumanMessage, SystemMessage } from '@langchain/core/messages';

export class LandSubdivisionAgent extends HermesAgent {
  async run(): Promise<AgentRunResult> {
    this.trace('start');
    const result: AgentRunResult = {
      market: this.config.market,
      strategy: this.config.strategy,
      status: 'SUCCESS',
      findings: [],
      errors: [],
    };

    let deals: Array<Record<string, unknown>> = [];
    try {
      deals = await runQuery<Record<string, unknown>>(
        `MATCH (d:Deal)-[:LOCATED_IN]->(m:Market {name: $market})
         WHERE d.propertyType = 'LAND' OR d.lane = 'WHALE_SUBDIVISION'
         OPTIONAL MATCH (b:Buyer)-[r:LIKELY_TO_BUY]->(d)
         RETURN d.address AS address, d.price AS price, d.arv AS arv,
                d.description AS description, d.lane AS lane,
                count(b) AS interestedBuyers, max(r.score) AS topBuyerScore
         ORDER BY topBuyerScore DESC
         LIMIT 20`,
        { market: this.config.market.toUpperCase() },
      );
    } catch (err) {
      result.errors.push(`Neo4j query failed: ${err}`);
      result.status = 'PARTIAL';
    }

    if (deals.length === 0) {
      result.findings.push({
        type: 'NO_LAND_DEALS',
        data: null,
        summary: `No land/subdivision deals in Neo4j for ${this.config.market}`,
      });
    } else {
      const dealSummary = deals
        .slice(0, 10)
        .map(
          (d) =>
            `${d.address}: $${d.price ?? '?'} (ARV $${d.arv ?? '?'}), buyers: ${d.interestedBuyers}, top score: ${d.topBuyerScore ?? 0}`,
        )
        .join('\n');

      // Use analysis model for deep MAO/subdivision reasoning
      let reasoning = '';
      try {
        const response = await analysisModel.invoke([
          new SystemMessage(
            'You are AMARA\'s deal analysis engine. You calculate MAO and ghost subdivision opportunities with precision. Be decisive and specific.',
          ),
          new HumanMessage(
            `Market: ${this.config.market}\nLand/Subdivision deals:\n${dealSummary}\n\nCalculate MAO estimates (70% ARV minus repairs), rank by opportunity, identify ghost subdivision plays.`,
          ),
        ]);
        reasoning = typeof response.content === 'string' ? response.content : '';
      } catch (err) {
        result.errors.push(`Analysis model failed: ${err}`);
      }

      result.findings.push({
        type: 'LAND_SUBDIVISION_ANALYSIS',
        data: deals,
        summary: reasoning || `${deals.length} land/subdivision deals in ${this.config.market}`,
      });
      result.reasoning = reasoning;
    }

    await this.logToNeo4j('LandSubdivisionAgent', this.config.market, result.status);
    return result;
  }
}

import { runQuery } from '@/lib/neural-graph/neo4j-client';
import { HermesAgent, AgentRunResult } from './agent-base';

export class SfrDomAgent extends HermesAgent {
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
         WHERE d.dom >= 90 AND (d.propertyType = 'SFR' OR d.lane = 'SFR_INFILL')
         OPTIONAL MATCH (d)-[:HAS_SIGNAL]->(s:Signal)
         RETURN d.address AS address, d.price AS price, d.dom AS dom,
                d.beds AS beds, d.baths AS baths, d.sqft AS sqft,
                collect(s.reason) AS signals
         ORDER BY d.dom DESC
         LIMIT 20`,
        { market: this.config.market.toUpperCase() },
      );
    } catch (err) {
      result.errors.push(`Neo4j query failed: ${err}`);
      result.status = 'PARTIAL';
    }

    if (deals.length === 0) {
      result.findings.push({
        type: 'NO_SFR_DOM',
        data: null,
        summary: `No SFR 90+ DOM deals found in Neo4j for ${this.config.market}`,
      });
    } else {
      const dealSummary = deals
        .slice(0, 10)
        .map(
          (d) =>
            `${d.address}: $${d.price ?? '?'}, ${d.dom} DOM, signals: ${(d.signals as string[]).join(', ') || 'none'}`,
        )
        .join('\n');

      const reasoning = await this.think(
        `Market: ${this.config.market}\nSFR 90+ DOM properties:\n${dealSummary}\n\nWhich properties show the strongest distress signals and best MAO opportunity?`,
      ).catch((err) => {
        result.errors.push(`Reasoning failed: ${err}`);
        return '';
      });

      result.findings.push({
        type: 'SFR_DOM_ANALYSIS',
        data: deals,
        summary: reasoning || `${deals.length} SFR 90+ DOM deals found in ${this.config.market}`,
      });
      result.reasoning = reasoning;
    }

    await this.logToNeo4j('SfrDomAgent', this.config.market, result.status);
    return result;
  }
}

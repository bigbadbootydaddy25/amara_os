import { runQuery } from '@/lib/neural-graph/neo4j-client';
import { HermesAgent, fastModel, AgentRunResult } from './agent-base';
import { HumanMessage } from '@langchain/core/messages';

// OSINT signal sources — expand with real scrapers (Playwright/Puppeteer) when ready
const SIGNAL_SOURCES = ['COUNTY_CLERK', 'TAX_OFFICE', 'CODE_ENFORCEMENT', 'PLANNING_ZONING'];

export class OsintAgent extends HermesAgent {
  async run(): Promise<AgentRunResult> {
    this.trace('start');
    const result: AgentRunResult = {
      market: this.config.market,
      strategy: this.config.strategy,
      status: 'SUCCESS',
      findings: [],
      errors: [],
    };

    // Check which sources are accessible for this market
    let accessibleSources: string[] = [];
    try {
      const rows = await runQuery<{ source: string; accessible: boolean }>(
        `MATCH (m:Market {name: $market})
         RETURN m.accessibleSources AS sources`,
        { market: this.config.market.toUpperCase() },
      );
      const rawSources = rows[0]?.source;
      accessibleSources = Array.isArray(rawSources) ? (rawSources as string[]) : [];
    } catch {
      // Market node may not exist yet — treat all sources as pending
    }

    const unavailable = SIGNAL_SOURCES.filter((s) => !accessibleSources.includes(s));

    // Tag market as SOURCE_NOT_ACCESSIBLE if nothing is wired up
    if (accessibleSources.length === 0) {
      try {
        await runQuery(
          `MERGE (m:Market {name: $market})
           SET m.sourceStatus = 'SOURCE_NOT_ACCESSIBLE', m.checkedAt = datetime()`,
          { market: this.config.market.toUpperCase() },
        );
      } catch (err) {
        result.errors.push(`Neo4j market tag failed: ${err}`);
      }

      result.findings.push({
        type: 'SOURCE_NOT_ACCESSIBLE',
        data: { unavailable },
        summary: `No OSINT sources connected for ${this.config.market}. Needs: ${unavailable.join(', ')}`,
      });
      result.status = 'PARTIAL';
      this.trace('source_not_accessible');
      return result;
    }

    // Use fast model to classify/tag any raw OSINT text passed in dataTarget
    if (this.config.dataTarget) {
      try {
        const tagResponse = await fastModel.invoke([
          new HumanMessage(
            `Extract distress signals from this OSINT data for ${this.config.market}. Return JSON array of {signal, severity, address}. Data: ${this.config.dataTarget}`,
          ),
        ]);
        const tagText = typeof tagResponse.content === 'string' ? tagResponse.content : '';

        result.findings.push({
          type: 'OSINT_TAGS',
          data: tagText,
          summary: `OSINT data classified for ${this.config.market}`,
        });
      } catch (err) {
        result.errors.push(`OSINT classification failed: ${err}`);
        result.status = 'PARTIAL';
      }
    }

    await this.logToNeo4j('OsintAgent', this.config.market, result.status);
    return result;
  }
}

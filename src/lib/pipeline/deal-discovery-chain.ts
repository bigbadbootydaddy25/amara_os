import { RunnableSequence, RunnableLambda } from '@langchain/core/runnables';
import { StringOutputParser } from '@langchain/core/output_parsers';
import { ChatPromptTemplate } from '@langchain/core/prompts';
import { reasoningModel } from '@/lib/hermes/agent-base';
import { ingestSignals } from '@/lib/neural-graph/ingest-signals';
import { runQuery } from '@/lib/neural-graph/neo4j-client';
import { writeMarketMemory } from '@/lib/memory/memory-writer';

export interface DealDiscoveryInput {
  market: string;
  rawOsintData?: string;
}

export interface DealDiscoveryOutput {
  market: string;
  distressDealsFound: number;
  signalsSaved: number;
  analysis: string;
  errors: string[];
}

const scorePrompt = ChatPromptTemplate.fromMessages([
  ['system', 'You are AMARA\'s deal discovery engine. Analyse distress signals and identify the highest-value opportunities. Be concise — one paragraph max.'],
  ['human', 'Market: {market}\nDistress signals detected: {signalCount}\nTop distressed deals:\n{dealList}\n\nProvide a brief opportunity assessment.'],
]);

const scoreChain = scorePrompt.pipe(reasoningModel).pipe(new StringOutputParser());

export const dealDiscoveryChain = RunnableSequence.from([
  // Step 1: Apply distress signal scoring to all deals in the graph
  new RunnableLambda({
    func: async (input: DealDiscoveryInput): Promise<DealDiscoveryInput & { signalResult: { tagged: number; errors: string[] } }> => {
      const signalResult = await ingestSignals();
      return { ...input, signalResult };
    },
  }),

  // Step 2: Fetch distressed deals for this market
  new RunnableLambda({
    func: async (input: DealDiscoveryInput & { signalResult: { tagged: number; errors: string[] } }) => {
      const deals = await runQuery<{ address: string; dom: unknown; price: unknown; signals: string[] }>(
        `MATCH (d:Deal)-[:LOCATED_IN]->(m:Market {name: $market})
         MATCH (d)-[:HAS_SIGNAL]->(s:Signal)
         RETURN d.address AS address, d.dom AS dom, d.price AS price,
                collect(s.reason) AS signals
         ORDER BY d.dom DESC
         LIMIT 10`,
        { market: input.market.toUpperCase() },
      ).catch(() => []);

      const dealList = deals.length
        ? deals.map((d) => `${d.address}: DOM=${d.dom ?? '?'}, $${d.price ?? '?'}, signals=[${d.signals.join(', ')}]`).join('\n')
        : 'No distressed deals found in Neo4j for this market.';

      return { ...input, deals, dealList };
    },
  }),

  // Step 3: Claude reasoning — opportunity assessment
  new RunnableLambda({
    func: async (input: DealDiscoveryInput & { signalResult: { tagged: number; errors: string[] }; deals: unknown[]; dealList: string }): Promise<DealDiscoveryOutput> => {
      let analysis = '';
      try {
        analysis = await scoreChain.invoke({
          market: input.market,
          signalCount: input.signalResult.tagged,
          dealList: input.dealList,
        });
      } catch (err) {
        analysis = `Analysis unavailable: ${err}`;
      }

      // Write to memory
      await writeMarketMemory(input.market, analysis.slice(0, 300)).catch(() => {});

      return {
        market: input.market,
        distressDealsFound: input.deals.length,
        signalsSaved: input.signalResult.tagged,
        analysis,
        errors: input.signalResult.errors,
      };
    },
  }),
]);

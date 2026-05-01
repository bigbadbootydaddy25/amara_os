import { RunnableSequence, RunnableLambda } from '@langchain/core/runnables';
import { StringOutputParser } from '@langchain/core/output_parsers';
import { ChatPromptTemplate } from '@langchain/core/prompts';
import { reasoningModel } from '@/lib/hermes/agent-base';
import { buildRelationships } from '@/lib/neural-graph/build-relationships';
import { runQuery } from '@/lib/neural-graph/neo4j-client';
import { writeBuyerMemory } from '@/lib/memory/memory-writer';

export interface BuyerMatchInput {
  market?: string; // if omitted, match across all markets
  topN?: number;
}

export interface BuyerMatchOutput {
  matchesBuilt: number;
  topMatches: Array<{ buyer: string; deal: string; score: number }>;
  callList: string;
  analysis: string;
  errors: string[];
}

const matchPrompt = ChatPromptTemplate.fromMessages([
  ['system', 'You are AMARA\'s buyer intelligence engine. Produce a precise call list for Scott — who to call, in what order, and what to say. No fluff.'],
  ['human', 'Top buyer-deal matches:\n{matchList}\n\nProduce today\'s call list with a one-sentence pitch for each buyer.'],
]);

const matchChain = matchPrompt.pipe(reasoningModel).pipe(new StringOutputParser());

export const buyerMatchChain = RunnableSequence.from([
  // Step 1: Rebuild all LIKELY_TO_BUY scores in the graph
  new RunnableLambda({
    func: async (input: BuyerMatchInput) => {
      const relResult = await buildRelationships();
      return { ...input, relResult };
    },
  }),

  // Step 2: Fetch top matches (optionally filtered by market)
  new RunnableLambda({
    func: async (input: BuyerMatchInput & { relResult: Awaited<ReturnType<typeof buildRelationships>> }) => {
      const marketFilter = input.market ? 'AND (d)-[:LOCATED_IN]->(:Market {name: $market})' : '';
      const topMatches = await runQuery<{ buyer: string; deal: string; score: { low: number }; priceMax: unknown; isWhale: boolean }>(
        `MATCH (b:Buyer)-[r:LIKELY_TO_BUY]->(d:Deal)
         WHERE r.score IS NOT NULL ${marketFilter}
         RETURN b.name AS buyer, d.address AS deal,
                r.score AS score, b.priceMax AS priceMax, b.isWhale AS isWhale
         ORDER BY r.score DESC
         LIMIT $limit`,
        { market: input.market?.toUpperCase() ?? '', limit: input.topN ?? 10 },
      ).catch(() => []);

      return { ...input, topMatches };
    },
  }),

  // Step 3: Claude produces the call list
  new RunnableLambda({
    func: async (
      input: BuyerMatchInput & {
        relResult: Awaited<ReturnType<typeof buildRelationships>>;
        topMatches: Array<{ buyer: string; deal: string; score: { low: number }; priceMax: unknown; isWhale: boolean }>;
      },
    ): Promise<BuyerMatchOutput> => {
      const matchList = input.topMatches.length
        ? input.topMatches.map((m) => `${m.buyer}${m.isWhale ? ' [WHALE]' : ''} → ${m.deal} (score: ${m.score?.low ?? 0}, max: $${m.priceMax ?? '?'})`).join('\n')
        : 'No buyer-deal matches in graph yet.';

      let callList = '';
      try {
        callList = await matchChain.invoke({ matchList });
      } catch (err) {
        callList = `Call list unavailable: ${err}`;
      }

      // Write whale buyers to memory
      for (const m of input.topMatches.filter((x) => x.isWhale).slice(0, 3)) {
        await writeBuyerMemory(m.buyer, `matched to ${m.deal} with score ${m.score?.low ?? 0}`).catch(() => {});
      }

      return {
        matchesBuilt: input.relResult.matchesBuilt,
        topMatches: input.topMatches.map((m) => ({ buyer: m.buyer, deal: m.deal, score: m.score?.low ?? 0 })),
        callList,
        analysis: matchList,
        errors: input.relResult.errors,
      };
    },
  }),
]);

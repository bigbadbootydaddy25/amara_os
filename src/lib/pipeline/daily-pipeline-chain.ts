import { RunnableSequence, RunnableLambda } from '@langchain/core/runnables';
import { dealDiscoveryChain, DealDiscoveryOutput } from './deal-discovery-chain';
import { buyerMatchChain, BuyerMatchOutput } from './buyer-match-chain';
import { generateMorningBriefing, BriefingResult } from '@/lib/memory/morning-briefing';
import { writePipelineStatus } from '@/lib/memory/memory-writer';
import fs from 'fs';
import path from 'path';

export interface DailyPipelineInput {
  markets: string[];
  skipBriefing?: boolean;
}

export interface DailyPipelineOutput {
  date: string;
  markets: string[];
  discovery: DealDiscoveryOutput[];
  buyerMatch: BuyerMatchOutput;
  briefing: BriefingResult | null;
  totalDealsFound: number;
  totalMatchesBuilt: number;
  errors: string[];
}

function writeReport(content: string, filePath: string): void {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, content, 'utf-8');
}

export const dailyPipelineChain = RunnableSequence.from([
  // Chain 1: Deal Discovery across all markets (parallel)
  new RunnableLambda({
    func: async (input: DailyPipelineInput) => {
      const discoveryResults = await Promise.all(
        input.markets.map((market) =>
          dealDiscoveryChain.invoke({ market }).catch((err): DealDiscoveryOutput => ({
            market,
            distressDealsFound: 0,
            signalsSaved: 0,
            analysis: '',
            errors: [String(err)],
          })),
        ),
      );
      return { ...input, discoveryResults };
    },
  }),

  // Chain 2: Buyer Match (global — all markets)
  new RunnableLambda({
    func: async (input: DailyPipelineInput & { discoveryResults: DealDiscoveryOutput[] }) => {
      const buyerMatchResult = await buyerMatchChain
        .invoke({ topN: 20 })
        .catch((err): BuyerMatchOutput => ({
          matchesBuilt: 0,
          topMatches: [],
          callList: '',
          analysis: String(err),
          errors: [String(err)],
        }));
      return { ...input, buyerMatchResult };
    },
  }),

  // Chain 3: Morning Briefing synthesis
  new RunnableLambda({
    func: async (
      input: DailyPipelineInput & {
        discoveryResults: DealDiscoveryOutput[];
        buyerMatchResult: BuyerMatchOutput;
      },
    ): Promise<DailyPipelineOutput> => {
      const date = new Date().toISOString().slice(0, 10);
      const errors: string[] = [
        ...input.discoveryResults.flatMap((d) => d.errors),
        ...input.buyerMatchResult.errors,
      ];

      const totalDealsFound = input.discoveryResults.reduce((sum, d) => sum + d.distressDealsFound, 0);
      const totalMatchesBuilt = input.buyerMatchResult.matchesBuilt;

      // Write pipeline status to memory
      await writePipelineStatus('DISCOVERY', totalDealsFound, `${input.markets.length} markets scanned`).catch(() => {});
      await writePipelineStatus('MATCHED', totalMatchesBuilt).catch(() => {});

      let briefing: BriefingResult | null = null;
      if (!input.skipBriefing) {
        briefing = await generateMorningBriefing().catch((err) => {
          errors.push(`Briefing failed: ${err}`);
          return null;
        });
      }

      const masterReport = `# DAILY PIPELINE — ${date}

## Summary
| Metric | Value |
|--------|-------|
| Markets scanned | ${input.markets.length} |
| Distress deals found | ${totalDealsFound} |
| Buyer matches built | ${totalMatchesBuilt} |
| Errors | ${errors.length} |

## Call List
${input.buyerMatchResult.callList || '_No matches yet_'}

## Market Discovery
${input.discoveryResults.map((d) => `### ${d.market}\n${d.analysis || '_No distress deals found_'}`).join('\n\n')}

## Errors
${errors.length ? errors.map((e) => `- ${e}`).join('\n') : '_None_'}
`;

      writeReport(masterReport, path.resolve(process.cwd(), `reports/DAILY_PIPELINE_${date}.md`));

      return {
        date,
        markets: input.markets,
        discovery: input.discoveryResults,
        buyerMatch: input.buyerMatchResult,
        briefing,
        totalDealsFound,
        totalMatchesBuilt,
        errors,
      };
    },
  }),
]);

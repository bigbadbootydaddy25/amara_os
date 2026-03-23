/**
 * AMARA OS — Autonomous AI Agent
 * Claude Opus 4.6 with adaptive thinking + tool use.
 * Analyzes deals, enriches data, surfaces qualified opportunities.
 * AMARA runs this. Zero user intervention.
 */

import Anthropic from "@anthropic-ai/sdk";
import { AMARA_SYSTEM_PROMPT, DEAL_ENRICHMENT_PROMPT, MARKET_SCAN_PROMPT } from "./prompts/dealAnalyst";
import { distressToolDefinition, runDistressTool } from "./tools/distressTool";
import { buyerToolDefinition, runBuyerTool } from "./tools/buyerTool";
import { underwriteToolDefinition, runUnderwriteTool } from "./tools/underwriteTool";
import { CanonicalDeal } from "@/core/schema/canonical";
import { ZillowRawListing } from "@/adapters/zillow/types";

const client = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY,
});

const AMARA_TOOLS = [
  distressToolDefinition,
  buyerToolDefinition,
  underwriteToolDefinition,
] as Anthropic.Tool[];

// ─────────────────────────────────────────────────────────────────────────────
// TOOL EXECUTOR
// ─────────────────────────────────────────────────────────────────────────────
async function executeTool(name: string, input: Record<string, unknown>): Promise<string> {
  switch (name) {
    case "analyze_distress":
      return runDistressTool(input as Parameters<typeof runDistressTool>[0]);
    case "match_buyer_lane":
      return runBuyerTool(input as Parameters<typeof runBuyerTool>[0]);
    case "underwrite_deal":
      return runUnderwriteTool(input as Parameters<typeof runUnderwriteTool>[0]);
    default:
      return JSON.stringify({ error: `Unknown tool: ${name}` });
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// AGENTIC LOOP
// ─────────────────────────────────────────────────────────────────────────────
async function runAgenticLoop(userMessage: string): Promise<string> {
  const messages: Anthropic.MessageParam[] = [
    { role: "user", content: userMessage },
  ];

  let finalText = "";

  while (true) {
    const response = await client.messages.create({
      model: "claude-opus-4-6",
      max_tokens: 16000,
      thinking: { type: "adaptive" },
      system: AMARA_SYSTEM_PROMPT,
      tools: AMARA_TOOLS,
      messages,
    });

    // Collect text output
    for (const block of response.content) {
      if (block.type === "text") {
        finalText = block.text;
      }
    }

    if (response.stop_reason === "end_turn") {
      break;
    }

    if (response.stop_reason === "tool_use") {
      // Append assistant turn
      messages.push({ role: "assistant", content: response.content });

      // Execute all tool calls
      const toolResults: Anthropic.ToolResultBlockParam[] = [];
      for (const block of response.content) {
        if (block.type === "tool_use") {
          console.log(`[AMARA:Agent] → ${block.name}(${JSON.stringify(block.input).slice(0, 100)})`);
          const result = await executeTool(block.name, block.input as Record<string, unknown>);
          toolResults.push({
            type: "tool_result",
            tool_use_id: block.id,
            content: result,
          });
        }
      }

      messages.push({ role: "user", content: toolResults });
      continue;
    }

    // Any other stop reason — bail
    break;
  }

  return finalText;
}

// ─────────────────────────────────────────────────────────────────────────────
// PUBLIC API
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Enrich a single deal with AI analysis.
 * Claude reasons about distress, exit buyers, and deal math.
 */
export async function enrichDealWithAI(
  deal: Partial<CanonicalDeal>
): Promise<{ verdict: "QUALIFIED" | "REJECTED"; analysis: string; enrichedData: Record<string, unknown> }> {
  const summary = `
Address: ${deal.address}, ${deal.city}, ${deal.state} ${deal.zip}
Market: ${deal.market}
List Price: $${deal.listPrice?.toLocaleString() ?? "unknown"}
Original Price: $${deal.originalListPrice?.toLocaleString() ?? "unknown"}
Price Reductions: ${deal.priceHistory?.filter(p => p.event === "REDUCED").length ?? 0}
Days on Market: ${deal.dom ?? "unknown"}
Beds/Baths: ${deal.beds}bd / ${deal.baths}ba
Sqft: ${deal.livingAreaSqft?.toLocaleString() ?? "unknown"}
Year Built: ${deal.yearBuilt ?? "unknown"}
Remarks: ${deal.remarks ?? "No remarks"}
Zestimate/AVM: $${deal.valuation?.avm?.toLocaleString() ?? "unknown"}
Property Type: ${deal.propertyType}
  `.trim();

  const prompt = DEAL_ENRICHMENT_PROMPT(summary);

  try {
    const analysis = await runAgenticLoop(prompt);

    const isQualified = analysis.toUpperCase().includes("QUALIFIED") &&
      !analysis.toUpperCase().includes("REJECTED");

    return {
      verdict: isQualified ? "QUALIFIED" : "REJECTED",
      analysis,
      enrichedData: {},
    };
  } catch (err) {
    console.error("[AMARA:Agent] Error enriching deal:", err);
    return {
      verdict: "REJECTED",
      analysis: `AI analysis failed: ${(err as Error).message}`,
      enrichedData: {},
    };
  }
}

/**
 * Scan a batch of raw Zillow listings and identify deal candidates.
 * Returns the top prospects for deep pipeline processing.
 */
export async function screenMarketListings(
  market: string,
  listings: ZillowRawListing[]
): Promise<{ prospects: ZillowRawListing[]; report: string }> {
  if (!listings.length) {
    return { prospects: [], report: "No listings to analyze." };
  }

  const listingsSummary = listings
    .slice(0, 20) // Claude context window limit — batch in 20s
    .map((l, i) => `
[${i + 1}] ${l.address}
  Price: ${l.price} | DOM: ${l.dom} | Price Reduced: ${l.priceReduced}
  Details: ${l.details ?? "N/A"}
  Remarks: ${l.remarks ?? "No remarks"}
  Status: ${l.status}
    `.trim())
    .join("\n\n");

  const prompt = MARKET_SCAN_PROMPT(market, listingsSummary);

  try {
    const report = await runAgenticLoop(prompt);

    // Extract indices of flagged prospects from the report
    const flaggedIndices: number[] = [];
    const matches = report.matchAll(/\[(\d+)\]/g);
    for (const match of matches) {
      const idx = parseInt(match[1]) - 1;
      if (idx >= 0 && idx < listings.length) {
        flaggedIndices.push(idx);
      }
    }

    // Unique indices, max 5 prospects
    const uniqueIndices = [...new Set(flaggedIndices)].slice(0, 5);
    const prospects = uniqueIndices.length > 0
      ? uniqueIndices.map(i => listings[i])
      : listings.filter(l => l.priceReduced || (parseInt(l.dom ?? "0") > 45)).slice(0, 5);

    return { prospects, report };
  } catch (err) {
    console.error("[AMARA:Agent] Error screening listings:", err);
    // Fallback: return price-reduced or high-DOM listings
    const fallback = listings
      .filter(l => l.priceReduced || (parseInt(l.dom ?? "0") > 45))
      .slice(0, 5);
    return { prospects: fallback, report: `Screening error: ${(err as Error).message}` };
  }
}

/**
 * Generate a market intelligence report for Mission Control.
 */
export async function generateMarketReport(
  marketId: string,
  scanData: { listingsFound: number; dealsQualified: number; topDeals: Partial<CanonicalDeal>[] }
): Promise<string> {
  const prompt = `
Generate a brief Mission Control intelligence report for market: ${marketId}

Scan Results:
- Listings scanned: ${scanData.listingsFound}
- Deals qualified: ${scanData.dealsQualified}
- Top deals this scan:
${scanData.topDeals.map(d => `  • ${d.address} | MAO: $${d.underwriting?.mao?.toLocaleString() ?? 'N/A'} | Fee: $${d.underwriting?.assignmentFee?.toLocaleString() ?? 'N/A'}`).join('\n')}

Keep it tight. 3-4 sentences max. Operator tone — direct, confident.`;

  try {
    return await runAgenticLoop(prompt);
  } catch {
    return `${marketId.toUpperCase()} scan complete. ${scanData.dealsQualified} deal(s) qualified from ${scanData.listingsFound} listings processed.`;
  }
}

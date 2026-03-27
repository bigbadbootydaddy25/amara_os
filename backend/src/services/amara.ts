import type { LandParcel } from "../db/schema";

// ─────────────────────────────────────────────────────────────────────────────
// Amara OS AI Adapter
//
// Each function has a clear contract. Swap the stub implementations for real
// AI provider calls (Perplexity, Claude, OpenAI) without touching callers.
//
// To wire in a real provider:
//   1. Set AMARA_AI_PROVIDER=perplexity | openai | claude in .env
//   2. Set the corresponding API key
//   3. Replace the stub body in each function below
// ─────────────────────────────────────────────────────────────────────────────

export type AmaraDecision = "APPROVED" | "REJECTED" | "NEEDS_MORE_INFO";

export interface AmaraReviewResult {
  decision: AmaraDecision;
  confidenceScore: number;  // 0–100
  reasoning: string;        // Amara's full chain-of-thought
}

export interface AmaraDocuments {
  loiText?: string;
  ownerOutreachText?: string;
  negotiationStrategy?: string;
}

// ─── System prompt injected into every Amara call ────────────────────────────
const AMARA_SYSTEM_PROMPT = `
You are Amara, an autonomous AI real-estate investment agent specializing in
land acquisition for residential development. You think like a seasoned developer:
you balance risk, upside, entitlement complexity, and market timing.
You are direct, analytical, and decisive. You never hedge unnecessarily.
Your goal is to find undervalued land parcels with strong subdivision or
development potential and move on them fast before the market reprices.
`.trim();

// ─── Build rich parcel context for Amara ─────────────────────────────────────
export function buildAmaraParcelContext(p: LandParcel): string {
  const fmt = (v: unknown, prefix = "", suffix = "") =>
    v != null ? `${prefix}${v}${suffix}` : "Unknown";

  const ratio =
    p.estimatedLandValuePerPotentialLot && p.nearbyNewBuildPricePerUnit
      ? ((Number(p.estimatedLandValuePerPotentialLot) /
          Number(p.nearbyNewBuildPricePerUnit)) * 100).toFixed(1) + "%"
      : "N/A";

  return `
=== PARCEL BRIEF ===
APN: ${fmt(p.apn)}
Address: ${[p.addressLine1, p.city, p.state, p.zip].filter(Boolean).join(", ")}
County: ${fmt(p.county)} | Jurisdiction: ${fmt(p.jurisdiction)}

=== SIZE & ZONING ===
Area: ${fmt(p.areaAcres, "", " acres")} (${fmt(p.areaSqft, "", " sqft")})
Zoning: ${fmt(p.zoningCode)} — ${fmt(p.zoningDescription)}
Allowed Use: ${fmt(p.allowedUseCategory)}
Est. Max Lots: ${fmt(p.estMaxLotCount)} | Est. Max Units: ${fmt(p.estMaxUnitCount)}
Min Lot Size: ${fmt(p.minLotSizeSqft, "", " sqft")} | Max Units/Acre: ${fmt(p.maxUnitsPerAcre)}
FAR: ${fmt(p.floorAreaRatio)} | Max Height: ${fmt(p.maxHeightFt, "", " ft")}
Setbacks (F/S/R): ${fmt(p.frontSetbackFt, "", "'")} / ${fmt(p.sideSetbackFt, "", "'")} / ${fmt(p.rearSetbackFt, "", "'")}

=== PHYSICAL ===
Topography: ${fmt(p.topographyClass)} | Flood Zone: ${fmt(p.floodZoneCode)}
Environmental Flag: ${p.hasEnvironmentalFlag ? "YES ⚠️" : "No"}
Access: ${fmt(p.accessType)} | Existing Structure: ${p.hasExistingStructure ? "Yes" : "No"}
Existing Use: ${fmt(p.existingUseType)} | Existing Bldg: ${fmt(p.existingBuildingSqft, "", " sqft")}

=== UTILITIES ===
Water: ${p.hasWater ? "✓" : "✗"} | Sewer: ${p.hasSewer ? "✓" : "✗"} | Power: ${p.hasPower ? "✓" : "✗"} | Gas: ${p.hasGas ? "✓" : "✗"}
School District: ${fmt(p.schoolDistrict)} (Score: ${fmt(p.schoolScoreBucket)})

=== OWNERSHIP ===
Owner: ${fmt(p.ownerName)}
Years Owned: ${fmt(p.yearsOwned)}
Last Sale: ${fmt(p.lastSaleDate)} at ${fmt(p.lastSalePrice, "$")}
Assessed Land Value: ${fmt(p.assessedLandValue, "$")} | Total: ${fmt(p.assessedTotalValue, "$")}

=== MARKET ===
Nearby New Build $/Unit: ${fmt(p.nearbyNewBuildPricePerUnit, "$")}
Nearby Resale $/sqft: ${fmt(p.nearbyResalePricePerSqft, "$")}
Est. Land Value Total: ${fmt(p.estimatedLandValueTotal, "$")}
Est. Value/Acre: ${fmt(p.estimatedLandValuePerAcre, "$")}
Est. Value/Potential Lot: ${fmt(p.estimatedLandValuePerPotentialLot, "$")}
Land-to-Retail Ratio: ${ratio}

=== DISTRESS SIGNALS ===
Tax Delinquent: ${p.isTaxDelinquent ? `YES — $${p.taxDelinquentAmount}` : "No"}
Code Violations: ${p.hasCodeViolations ? `YES — ${p.codeViolationCount} violations` : "No"}
Preforeclosure: ${p.hasPreforeclosureFlag ? "YES ⚠️" : "No"}
Vacant Land: ${p.isVacantLand ? "Yes" : "No"} | Vacant Structure: ${p.isVacantStructure ? "Yes" : "No"}

=== PROPVISION SCORE ===
Feasibility Score: ${fmt(p.feasibilityScore, "", "/100")}
Recommendation: ${fmt(p.recommendation)}
Target Product: ${fmt(p.targetProductType)}
Notes: ${fmt(p.notes)}
`.trim();
}

// ─── AI Provider call (swap this) ────────────────────────────────────────────
async function callAI(systemPrompt: string, userPrompt: string): Promise<string> {
  const provider = process.env.AMARA_AI_PROVIDER ?? "stub";

  if (provider === "openai") {
    // TODO: wire in OpenAI
    // const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
    // const res = await openai.chat.completions.create({
    //   model: "gpt-4o",
    //   messages: [{ role: "system", content: systemPrompt }, { role: "user", content: userPrompt }],
    //   temperature: 0.3,
    // });
    // return res.choices[0].message.content ?? "";
    throw new Error("OpenAI not wired in yet. Set AMARA_AI_PROVIDER=stub or wire in key.");
  }

  if (provider === "perplexity") {
    // TODO: wire in Perplexity
    // const res = await fetch("https://api.perplexity.ai/chat/completions", {
    //   method: "POST",
    //   headers: { Authorization: `Bearer ${process.env.PERPLEXITY_API_KEY}`, "Content-Type": "application/json" },
    //   body: JSON.stringify({
    //     model: "llama-3.1-sonar-large-128k-online",
    //     messages: [{ role: "system", content: systemPrompt }, { role: "user", content: userPrompt }],
    //   }),
    // });
    // const data = await res.json();
    // return data.choices[0].message.content;
    throw new Error("Perplexity not wired in yet. Set AMARA_AI_PROVIDER=stub or wire in key.");
  }

  if (provider === "claude") {
    // TODO: wire in Anthropic Claude
    // const anthropic = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });
    // const msg = await anthropic.messages.create({
    //   model: "claude-opus-4-6",
    //   max_tokens: 2048,
    //   system: systemPrompt,
    //   messages: [{ role: "user", content: userPrompt }],
    // });
    // return (msg.content[0] as any).text;
    throw new Error("Claude not wired in yet. Set AMARA_AI_PROVIDER=stub or wire in key.");
  }

  // ── Stub (default) ──────────────────────────────────────────────────────────
  return `[AMARA STUB — set AMARA_AI_PROVIDER=openai|perplexity|claude to enable real AI]\n\n${userPrompt.slice(0, 200)}…`;
}

// ─── Public interface ─────────────────────────────────────────────────────────

/**
 * Amara reviews a parcel and returns her decision + reasoning.
 */
export async function amaraReviewDeal(parcel: LandParcel): Promise<AmaraReviewResult> {
  const context = buildAmaraParcelContext(parcel);

  const prompt = `
${context}

---
Based on this parcel brief, provide your investment review as Amara.

Respond in exactly this JSON format (no markdown fences):
{
  "decision": "APPROVED" | "REJECTED" | "NEEDS_MORE_INFO",
  "confidenceScore": <number 0-100>,
  "reasoning": "<your full chain-of-thought reasoning, 3-6 paragraphs>"
}

Consider:
1. Is the feasibility score and land-to-retail ratio attractive?
2. Are the distress signals genuine acquisition opportunities?
3. Are there physical/environmental/zoning red flags that kill the deal?
4. Is the ownership profile (years owned, tax delinquency) indicating motivation to sell?
5. What is the development upside (lots × market price) vs. acquisition cost?
6. What is your overall conviction level?
`.trim();

  const raw = await callAI(AMARA_SYSTEM_PROMPT, prompt);

  // Parse JSON — fall back to stub values if AI returns malformed response
  try {
    const parsed = JSON.parse(raw);
    return {
      decision: parsed.decision as AmaraDecision,
      confidenceScore: Number(parsed.confidenceScore),
      reasoning: parsed.reasoning,
    };
  } catch {
    // Stub fallback
    const score = parcel.feasibilityScore ?? 50;
    const decision: AmaraDecision =
      score >= 75 ? "APPROVED" : score >= 55 ? "NEEDS_MORE_INFO" : "REJECTED";
    return {
      decision,
      confidenceScore: score,
      reasoning: raw,
    };
  }
}

/**
 * Amara generates a Letter of Intent for an approved parcel.
 */
export async function amaraGenerateLOI(
  parcel: LandParcel,
  offerPrice: number,
  buyerEntity: string
): Promise<string> {
  const context = buildAmaraParcelContext(parcel);

  const prompt = `
${context}

---
Generate a professional Letter of Intent (LOI) for this land acquisition.

Buyer Entity: ${buyerEntity}
Offer Price: $${offerPrice.toLocaleString()}
Date: ${new Date().toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" })}

Write a complete, professional LOI with:
- Proper heading and date
- Buyer and seller identification (use owner name from brief)
- Property description (APN, address, size)
- Proposed purchase price and terms
- Due diligence period (suggest 45-60 days)
- Earnest money deposit suggestion (1-2% of offer)
- Closing timeline
- Key contingencies (entitlement, financing, environmental)
- Non-binding disclaimer
- Signature blocks

Write in formal legal letter format. Be specific and professional.
`.trim();

  return callAI(AMARA_SYSTEM_PROMPT, prompt);
}

/**
 * Amara generates a personalized owner outreach letter.
 */
export async function amaraGenerateOwnerOutreach(parcel: LandParcel): Promise<string> {
  const context = buildAmaraParcelContext(parcel);

  const prompt = `
${context}

---
Write a personalized, compelling owner outreach letter for this property.

The goal: get the owner to respond and consider selling.

Guidelines:
- Address the owner by name if available
- Reference the specific property (address/APN)
- Be warm, direct, and human — not corporate
- Mention your development experience and local focus
- Do NOT mention the distress signals (tax delinquency, violations) directly —
  but let them know you work with owners in complex situations
- If the owner has held long (${parcel.yearsOwned} years), acknowledge that legacy
- Create urgency without pressure
- Include a clear call to action (phone + email)
- Keep it to 3-4 paragraphs, conversational tone
- End with a handwritten-style sign-off

Sender name placeholder: [YOUR NAME]
Sender company: [YOUR COMPANY]
Phone: [YOUR PHONE]
Email: [YOUR EMAIL]
`.trim();

  return callAI(AMARA_SYSTEM_PROMPT, prompt);
}

/**
 * Amara generates a negotiation strategy memo.
 */
export async function amaraGenerateNegotiationStrategy(parcel: LandParcel): Promise<string> {
  const context = buildAmaraParcelContext(parcel);

  const prompt = `
${context}

---
Write a negotiation strategy memo for acquiring this parcel.

Structure as a professional memo with these sections:

1. DEAL THESIS (2-3 sentences on why we want this)
2. SELLER MOTIVATION ANALYSIS (what's driving potential to sell, psychological levers)
3. OPENING OFFER STRATEGY (anchor price, justification, what we show vs. hide)
4. WALK-AWAY NUMBER (our hard ceiling with reasoning)
5. NEGOTIATION LEVERS (terms we can flex: earnest money, close timeline, as-is, leaseback, etc.)
6. RED FLAGS TO PROBE IN DILIGENCE (specific things to verify that could change our offer)
7. COMPETITIVE RISK (who else might be looking at this, how to move fast)
8. RECOMMENDED FIRST MOVE (exactly what to say/do first)

Be tactical, specific, and direct. Think like a seasoned acquisition director.
`.trim();

  return callAI(AMARA_SYSTEM_PROMPT, prompt);
}

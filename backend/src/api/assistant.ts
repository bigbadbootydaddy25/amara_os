import type { FastifyInstance } from "fastify";
import { eq } from "drizzle-orm";
import { z } from "zod";
import { db } from "../db/client";
import { landParcels } from "../db/schema";

// ─── AI Adapter (placeholder) ────────────────────────────────────────────────
// Replace `stubAIQuery` with a real provider call (e.g. Perplexity, OpenAI)
// when you have keys. The function signature must stay the same.
async function stubAIQuery(
  message: string,
  context: string
): Promise<string> {
  // TODO: swap for real AI call, e.g.:
  //   const response = await perplexityClient.chat({ model: "...", messages: [
  //     { role: "system", content: context },
  //     { role: "user", content: message },
  //   ]});
  //   return response.choices[0].message.content;
  return `[AI stub] You asked: "${message}"\n\nParcel context:\n${context}`;
}

function buildParcelContext(row: Record<string, unknown>): string {
  return [
    `APN: ${row.apn ?? "N/A"}`,
    `Address: ${row.addressLine1 ?? ""}, ${row.city ?? ""}, ${row.state ?? ""} ${row.zip ?? ""}`,
    `Area: ${row.areaAcres ?? "N/A"} acres`,
    `Zoning: ${row.zoningCode ?? "N/A"} — ${row.zoningDescription ?? ""}`,
    `Allowed use: ${row.allowedUseCategory ?? "N/A"}`,
    `Est. max lots: ${row.estMaxLotCount ?? "N/A"}`,
    `Est. max units: ${row.estMaxUnitCount ?? "N/A"}`,
    `Feasibility score: ${row.feasibilityScore ?? "N/A"}/100`,
    `Recommendation: ${row.recommendation ?? "N/A"}`,
    `Pipeline status: ${row.pipelineStatus ?? "N/A"}`,
    `Tax delinquent: ${row.isTaxDelinquent ? "Yes" : "No"}`,
    `Code violations: ${row.hasCodeViolations ? "Yes" : "No"}`,
    `Preforeclosure: ${row.hasPreforeclosureFlag ? "Yes" : "No"}`,
    `Vacant land: ${row.isVacantLand ? "Yes" : "No"}`,
    `Flood zone: ${row.floodZoneCode ?? "N/A"}`,
    `Topography: ${row.topographyClass ?? "N/A"}`,
    `Nearby new build $/unit: ${row.nearbyNewBuildPricePerUnit ?? "N/A"}`,
    `Est. land value/potential lot: ${row.estimatedLandValuePerPotentialLot ?? "N/A"}`,
    `Notes: ${row.notes ?? ""}`,
  ].join("\n");
}

const queryBodySchema = z.object({
  parcelId: z.coerce.number().int(),
  message:  z.string().min(1).max(2000),
});

export async function assistantRoutes(app: FastifyInstance) {
  app.post("/assistant/query", async (req, reply) => {
    const parsed = queryBodySchema.safeParse(req.body);
    if (!parsed.success) {
      return reply.status(400).send({ error: "Validation failed", details: parsed.error.flatten() });
    }

    const { parcelId, message } = parsed.data;

    const [row] = await db.select().from(landParcels).where(eq(landParcels.id, parcelId));
    if (!row) return reply.status(404).send({ error: "Parcel not found" });

    const context = buildParcelContext(row as unknown as Record<string, unknown>);
    const answer = await stubAIQuery(message, context);

    return reply.send({ answer, parcelId });
  });
}

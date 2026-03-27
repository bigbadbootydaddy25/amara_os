import type { FastifyInstance } from "fastify";
import { desc, eq } from "drizzle-orm";
import { db } from "../db/client";
import { deals, dealMatches, buyers } from "../db/dealsSchema";
import { generateFeasibilityPDF } from "../services/pdf";
import type { BuyBoxResult } from "../services/buybox";

export async function pdfRoutes(app: FastifyInstance) {
  // GET /deals/:id/pdf
  // Returns a PDF feasibility report as application/pdf
  app.get<{ Params: { id: string } }>("/deals/:id/pdf", async (req, reply) => {
    const id = Number(req.params.id);
    if (isNaN(id)) return reply.status(400).send({ error: "Invalid id" });

    const [deal] = await db.select().from(deals).where(eq(deals.id, id));
    if (!deal) return reply.status(404).send({ error: "Deal not found" });

    // Fetch buyer matches
    const matchRows = await db
      .select({
        buyerId:     dealMatches.buyerId,
        matchScore:  dealMatches.matchScore,
        matchReasons: dealMatches.matchReasons,
        buyerName:   buyers.name,
        buyerEmail:  buyers.email,
        buyerPhone:  buyers.phone,
      })
      .from(dealMatches)
      .leftJoin(buyers, eq(dealMatches.buyerId, buyers.id))
      .where(eq(dealMatches.dealId, id))
      .orderBy(desc(dealMatches.matchScore));

    const bedsStr  = deal.beds  != null ? `${deal.beds}`  : "?";
    const bathsStr = deal.baths != null ? `${Number(deal.baths)}` : "?";
    const priceStr = deal.askingPrice ? `$${Math.round(Number(deal.askingPrice) / 1000)}K` : "N/A";

    const matchesForPdf: (BuyBoxResult & { buyerEmail?: string | null; buyerPhone?: string | null })[] =
      matchRows.map((m) => ({
        buyerId:      m.buyerId ?? 0,
        buyerName:    m.buyerName ?? "Unknown",
        matchScore:   m.matchScore,
        matchReasons: Array.isArray(m.matchReasons) ? m.matchReasons as any : [],
        label:        `${m.buyerName ?? "Buyer"} → ${bedsStr}/${bathsStr} ${priceStr} (${m.matchScore}%)`,
        buyerEmail:   m.buyerEmail,
        buyerPhone:   m.buyerPhone,
      }));

    const pdfBuffer = await generateFeasibilityPDF(deal, matchesForPdf);

    const slug = (deal.address ?? `deal-${id}`).replace(/[^a-z0-9]/gi, "_").toLowerCase();
    reply.header("Content-Type", "application/pdf");
    reply.header("Content-Disposition", `attachment; filename="propvision_${slug}.pdf"`);
    reply.header("Content-Length", pdfBuffer.length);
    return reply.send(pdfBuffer);
  });
}

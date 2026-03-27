import type { FastifyInstance } from "fastify";
import { and, desc, eq, inArray, sql } from "drizzle-orm";
import { z } from "zod";
import { parse as csvParse } from "csv-parse/sync";
import { randomUUID } from "crypto";
import { db } from "../db/client";
import { buyers, deals, dealMatches, type NewDeal, type NewBuyer } from "../db/dealsSchema";
import { matchDealToBuyers, csvRowToDeal } from "../services/buybox";

// ── Zod schemas ───────────────────────────────────────────────────────────────
const buyerSchema = z.object({
  name:    z.string().min(1),
  email:   z.string().email().optional(),
  phone:   z.string().optional(),
  company: z.string().optional(),
  propertyTypes: z.array(z.string()).optional(),
  bedsMin:  z.number().int().optional(),
  bedsMax:  z.number().int().optional(),
  bathsMin: z.number().optional(),
  bathsMax: z.number().optional(),
  sqftMin:  z.number().int().optional(),
  sqftMax:  z.number().int().optional(),
  priceMin: z.number().optional(),
  priceMax: z.number().optional(),
  arvMin:   z.number().optional(),
  arvMax:   z.number().optional(),
  maxRehab: z.number().optional(),
  minRoiPct: z.number().optional(),
  zipCodes: z.array(z.string()).optional(),
  states:   z.array(z.string()).optional(),
  isActive: z.boolean().default(true),
  notes:    z.string().optional(),
});

export async function dealRoutes(app: FastifyInstance) {

  // ─── POST /deals/import-csv ──────────────────────────────────────────────
  // Body: { csv: "<raw csv string>" }  OR multipart form with file
  app.post("/deals/import-csv", async (req, reply) => {
    const body = req.body as { csv?: string };
    if (!body?.csv) return reply.status(400).send({ error: "Body must include { csv: '...' }" });

    let rows: Record<string, string>[];
    try {
      rows = csvParse(body.csv, {
        columns: true,
        skip_empty_lines: true,
        trim: true,
        relax_quotes: true,
      });
    } catch (err: any) {
      return reply.status(400).send({ error: "CSV parse failed", detail: err.message });
    }

    if (!rows.length) return reply.status(400).send({ error: "CSV has no data rows" });

    const batchId = `batch_${new Date().toISOString().slice(0, 10)}_${randomUUID().slice(0, 6)}`;

    const insertPayloads: NewDeal[] = rows.map((row) => csvRowToDeal(row, batchId) as unknown as NewDeal);

    const inserted = await db.insert(deals).values(insertPayloads).returning({
      id: deals.id, address: deals.address, beds: deals.beds, baths: deals.baths,
      askingPrice: deals.askingPrice, arv: deals.arv, roiPct: deals.roiPct,
    });

    // Auto-run buy-box matching for all inserted deals
    const allBuyers = await db.select().from(buyers).where(eq(buyers.isActive, true));
    let totalMatches = 0;

    if (allBuyers.length) {
      const fullDeals = await db
        .select()
        .from(deals)
        .where(eq(deals.importBatchId, batchId));

      for (const deal of fullDeals) {
        const results = matchDealToBuyers(deal, allBuyers);
        if (results.length) {
          await db.insert(dealMatches).values(
            results.map((r) => ({
              dealId: deal.id,
              buyerId: r.buyerId,
              matchScore: r.matchScore,
              matchReasons: r.matchReasons,
            }))
          ).onConflictDoNothing();
          totalMatches += results.length;
        }
      }
    }

    return reply.status(201).send({
      data: {
        batchId,
        imported: inserted.length,
        totalMatches,
        deals: inserted,
      },
    });
  });

  // ─── GET /deals ──────────────────────────────────────────────────────────
  app.get("/deals", async (req, reply) => {
    const q = req.query as { page?: string; limit?: string; batch?: string };
    const page  = Math.max(1, parseInt(q.page  ?? "1", 10));
    const limit = Math.min(200, parseInt(q.limit ?? "50", 10));
    const offset = (page - 1) * limit;

    const where = q.batch ? eq(deals.importBatchId, q.batch) : undefined;

    const rows = await db.select().from(deals).where(where)
      .orderBy(desc(deals.createdAt)).limit(limit).offset(offset);

    const [{ count }] = await db.select({ count: sql<number>`count(*)::int` })
      .from(deals).where(where);

    return reply.send({ data: rows, pagination: { page, limit, total: count } });
  });

  // ─── GET /deals/:id ──────────────────────────────────────────────────────
  app.get<{ Params: { id: string } }>("/deals/:id", async (req, reply) => {
    const id = Number(req.params.id);
    if (isNaN(id)) return reply.status(400).send({ error: "Invalid id" });
    const [row] = await db.select().from(deals).where(eq(deals.id, id));
    if (!row) return reply.status(404).send({ error: "Deal not found" });
    return reply.send({ data: row });
  });

  // ─── GET /deals/:id/matches ──────────────────────────────────────────────
  app.get<{ Params: { id: string } }>("/deals/:id/matches", async (req, reply) => {
    const dealId = Number(req.params.id);
    if (isNaN(dealId)) return reply.status(400).send({ error: "Invalid id" });

    const rows = await db
      .select({
        matchId:     dealMatches.id,
        buyerId:     dealMatches.buyerId,
        matchScore:  dealMatches.matchScore,
        matchReasons: dealMatches.matchReasons,
        isSent:      dealMatches.isSent,
        sentAt:      dealMatches.sentAt,
        buyerName:   buyers.name,
        buyerEmail:  buyers.email,
        buyerPhone:  buyers.phone,
        buyerCompany: buyers.company,
        // Deal snapshot for label
        dealBeds:    deals.beds,
        dealBaths:   deals.baths,
        dealPrice:   deals.askingPrice,
      })
      .from(dealMatches)
      .leftJoin(buyers, eq(dealMatches.buyerId, buyers.id))
      .leftJoin(deals, eq(dealMatches.dealId, deals.id))
      .where(eq(dealMatches.dealId, dealId))
      .orderBy(desc(dealMatches.matchScore));

    // Build "Buyer John → 3/2 $273K (92%)" labels
    const labeled = rows.map((r) => {
      const bedsStr  = r.dealBeds  != null ? `${r.dealBeds}`  : "?";
      const bathsStr = r.dealBaths != null ? `${Number(r.dealBaths)}` : "?";
      const priceStr = r.dealPrice ? `$${Math.round(Number(r.dealPrice) / 1000)}K` : "N/A";
      return {
        ...r,
        label: `${r.buyerName ?? "Buyer"} → ${bedsStr}/${bathsStr} ${priceStr} (${r.matchScore}%)`,
      };
    });

    return reply.send({ data: labeled });
  });

  // ─── POST /deals/:id/rematch ─────────────────────────────────────────────
  // Re-run buy-box matching for a single deal
  app.post<{ Params: { id: string } }>("/deals/:id/rematch", async (req, reply) => {
    const dealId = Number(req.params.id);
    if (isNaN(dealId)) return reply.status(400).send({ error: "Invalid id" });

    const [deal] = await db.select().from(deals).where(eq(deals.id, dealId));
    if (!deal) return reply.status(404).send({ error: "Deal not found" });

    const allBuyers = await db.select().from(buyers).where(eq(buyers.isActive, true));
    const results = matchDealToBuyers(deal, allBuyers);

    if (results.length) {
      await db.insert(dealMatches).values(
        results.map((r) => ({
          dealId: deal.id, buyerId: r.buyerId,
          matchScore: r.matchScore, matchReasons: r.matchReasons,
        }))
      ).onConflictDoUpdate({
        target: [dealMatches.dealId, dealMatches.buyerId],
        set: { matchScore: sql`excluded.match_score`, matchReasons: sql`excluded.match_reasons` },
      });
    }

    return reply.send({ data: { dealId, matches: results.length, results } });
  });

  // ─── BUYERS CRUD ─────────────────────────────────────────────────────────

  app.get("/buyers", async (_req, reply) => {
    const rows = await db.select().from(buyers).orderBy(buyers.name);
    return reply.send({ data: rows });
  });

  app.post("/buyers", async (req, reply) => {
    const parsed = buyerSchema.safeParse(req.body);
    if (!parsed.success) return reply.status(400).send({ error: "Validation failed", details: parsed.error.flatten() });
    const [row] = await db.insert(buyers).values(parsed.data as NewBuyer).returning();
    return reply.status(201).send({ data: row });
  });

  app.put<{ Params: { id: string } }>("/buyers/:id", async (req, reply) => {
    const id = Number(req.params.id);
    const parsed = buyerSchema.partial().safeParse(req.body);
    if (!parsed.success) return reply.status(400).send({ error: "Validation failed" });
    const [row] = await db.update(buyers).set(parsed.data as any).where(eq(buyers.id, id)).returning();
    if (!row) return reply.status(404).send({ error: "Buyer not found" });
    return reply.send({ data: row });
  });

  app.delete<{ Params: { id: string } }>("/buyers/:id", async (req, reply) => {
    const id = Number(req.params.id);
    await db.delete(buyers).where(eq(buyers.id, id));
    return reply.status(204).send();
  });

  // ─── GET /deals/stats ───────────────────────────────────────────────────
  app.get("/deals/stats", async (_req, reply) => {
    const [stats] = await db.select({
      totalDeals:   sql<number>`count(distinct ${deals.id})::int`,
      totalBuyers:  sql<number>`(select count(*) from buyers where is_active = true)::int`,
      totalMatches: sql<number>`count(distinct ${dealMatches.id})::int`,
      avgScore:     sql<number>`round(avg(${dealMatches.matchScore}))::int`,
      topMatches:   sql<number>`count(*) filter (where ${dealMatches.matchScore} >= 80)::int`,
    })
    .from(deals)
    .leftJoin(dealMatches, eq(dealMatches.dealId, deals.id));

    return reply.send({ data: stats });
  });
}

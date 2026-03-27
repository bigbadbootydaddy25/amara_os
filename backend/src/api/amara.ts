import type { FastifyInstance } from "fastify";
import { desc, eq, sql } from "drizzle-orm";
import { z } from "zod";
import { db } from "../db/client";
import { landParcels } from "../db/schema";
import { dealReviews, pipelineRuns } from "../db/reviewSchema";
import {
  amaraReviewDeal,
  amaraGenerateLOI,
  amaraGenerateOwnerOutreach,
  amaraGenerateNegotiationStrategy,
} from "../services/amara";
import { runDailyPipeline } from "../services/pipeline";

const overrideBodySchema = z.object({
  decision:  z.enum(["APPROVED", "REJECTED"]),
  note:      z.string().optional(),
  overriddenBy: z.string().optional(),
});

const loiBodySchema = z.object({
  offerPrice:   z.number().positive(),
  buyerEntity:  z.string().min(1),
});

export async function amaraRoutes(app: FastifyInstance) {
  // ─── POST /amara/review/:parcelId ──────────────────────────────────────────
  // Trigger Amara to review a specific parcel immediately (outside daily pipeline)
  app.post<{ Params: { parcelId: string } }>(
    "/amara/review/:parcelId",
    async (req, reply) => {
      const parcelId = Number(req.params.parcelId);
      if (isNaN(parcelId)) return reply.status(400).send({ error: "Invalid parcelId" });

      const [parcel] = await db.select().from(landParcels).where(eq(landParcels.id, parcelId));
      if (!parcel) return reply.status(404).send({ error: "Parcel not found" });

      // Upsert review row in PENDING state first
      await db
        .insert(dealReviews)
        .values({ parcelId, amaraDecision: "PENDING", lifecycleStatus: "UNDER_REVIEW" })
        .onConflictDoNothing();

      const result = await amaraReviewDeal(parcel);

      const [updated] = await db
        .update(dealReviews)
        .set({
          amaraDecision: result.decision,
          confidenceScore: result.confidenceScore.toString(),
          amaraReasoning: result.reasoning,
          reviewedAt: new Date().toISOString(),
          lifecycleStatus:
            result.decision === "APPROVED"
              ? "APPROVED"
              : result.decision === "NEEDS_MORE_INFO"
              ? "NEEDS_INFO"
              : "REJECTED",
        })
        .where(eq(dealReviews.parcelId, parcelId))
        .returning();

      // Sync pipeline_status on parcel
      await db
        .update(landParcels)
        .set({ pipelineStatus: `AMARA_${result.decision}` })
        .where(eq(landParcels.id, parcelId));

      return reply.send({ data: updated });
    }
  );

  // ─── GET /amara/reviews ───────────────────────────────────────────────────
  app.get("/amara/reviews", async (req, reply) => {
    const rows = await db
      .select({
        id:              dealReviews.id,
        parcelId:        dealReviews.parcelId,
        amaraDecision:   dealReviews.amaraDecision,
        confidenceScore: dealReviews.confidenceScore,
        lifecycleStatus: dealReviews.lifecycleStatus,
        humanOverride:   dealReviews.humanOverride,
        reviewedAt:      dealReviews.reviewedAt,
        surfacedAt:      dealReviews.surfacedAt,
        // Join key parcel fields
        apn:         landParcels.apn,
        city:        landParcels.city,
        state:       landParcels.state,
        areaAcres:   landParcels.areaAcres,
        zoningCode:  landParcels.zoningCode,
        feasibilityScore: landParcels.feasibilityScore,
        recommendation:   landParcels.recommendation,
      })
      .from(dealReviews)
      .leftJoin(landParcels, eq(dealReviews.parcelId, landParcels.id))
      .orderBy(desc(dealReviews.surfacedAt));

    return reply.send({ data: rows });
  });

  // ─── GET /amara/reviews/:parcelId ─────────────────────────────────────────
  app.get<{ Params: { parcelId: string } }>(
    "/amara/reviews/:parcelId",
    async (req, reply) => {
      const parcelId = Number(req.params.parcelId);
      if (isNaN(parcelId)) return reply.status(400).send({ error: "Invalid parcelId" });

      const [row] = await db
        .select()
        .from(dealReviews)
        .where(eq(dealReviews.parcelId, parcelId));

      if (!row) return reply.status(404).send({ error: "No review found for this parcel" });
      return reply.send({ data: row });
    }
  );

  // ─── POST /amara/generate-loi/:parcelId ───────────────────────────────────
  app.post<{ Params: { parcelId: string } }>(
    "/amara/generate-loi/:parcelId",
    async (req, reply) => {
      const parcelId = Number(req.params.parcelId);
      const parsed = loiBodySchema.safeParse(req.body);
      if (!parsed.success) return reply.status(400).send({ error: "Validation failed", details: parsed.error.flatten() });
      if (isNaN(parcelId)) return reply.status(400).send({ error: "Invalid parcelId" });

      const [parcel] = await db.select().from(landParcels).where(eq(landParcels.id, parcelId));
      if (!parcel) return reply.status(404).send({ error: "Parcel not found" });

      const loiText = await amaraGenerateLOI(parcel, parsed.data.offerPrice, parsed.data.buyerEntity);

      const [updated] = await db
        .update(dealReviews)
        .set({ loiText, loiGeneratedAt: new Date().toISOString() })
        .where(eq(dealReviews.parcelId, parcelId))
        .returning();

      return reply.send({ data: { loiText, review: updated } });
    }
  );

  // ─── POST /amara/generate-outreach/:parcelId ──────────────────────────────
  app.post<{ Params: { parcelId: string } }>(
    "/amara/generate-outreach/:parcelId",
    async (req, reply) => {
      const parcelId = Number(req.params.parcelId);
      if (isNaN(parcelId)) return reply.status(400).send({ error: "Invalid parcelId" });

      const [parcel] = await db.select().from(landParcels).where(eq(landParcels.id, parcelId));
      if (!parcel) return reply.status(404).send({ error: "Parcel not found" });

      const ownerOutreachText = await amaraGenerateOwnerOutreach(parcel);

      const [updated] = await db
        .update(dealReviews)
        .set({ ownerOutreachText, outreachGeneratedAt: new Date().toISOString() })
        .where(eq(dealReviews.parcelId, parcelId))
        .returning();

      return reply.send({ data: { ownerOutreachText, review: updated } });
    }
  );

  // ─── POST /amara/generate-negotiation/:parcelId ───────────────────────────
  app.post<{ Params: { parcelId: string } }>(
    "/amara/generate-negotiation/:parcelId",
    async (req, reply) => {
      const parcelId = Number(req.params.parcelId);
      if (isNaN(parcelId)) return reply.status(400).send({ error: "Invalid parcelId" });

      const [parcel] = await db.select().from(landParcels).where(eq(landParcels.id, parcelId));
      if (!parcel) return reply.status(404).send({ error: "Parcel not found" });

      const negotiationStrategy = await amaraGenerateNegotiationStrategy(parcel);

      const [updated] = await db
        .update(dealReviews)
        .set({ negotiationStrategy, negotiationGeneratedAt: new Date().toISOString() })
        .where(eq(dealReviews.parcelId, parcelId))
        .returning();

      return reply.send({ data: { negotiationStrategy, review: updated } });
    }
  );

  // ─── POST /amara/override/:parcelId ───────────────────────────────────────
  // Human can override Amara's decision
  app.post<{ Params: { parcelId: string } }>(
    "/amara/override/:parcelId",
    async (req, reply) => {
      const parcelId = Number(req.params.parcelId);
      const parsed = overrideBodySchema.safeParse(req.body);
      if (!parsed.success) return reply.status(400).send({ error: "Validation failed" });
      if (isNaN(parcelId)) return reply.status(400).send({ error: "Invalid parcelId" });

      const [updated] = await db
        .update(dealReviews)
        .set({
          humanOverride: parsed.data.decision,
          humanOverrideNote: parsed.data.note,
          overriddenBy: parsed.data.overriddenBy,
          overriddenAt: new Date().toISOString(),
          lifecycleStatus: parsed.data.decision === "APPROVED" ? "APPROVED" : "REJECTED",
        })
        .where(eq(dealReviews.parcelId, parcelId))
        .returning();

      if (!updated) return reply.status(404).send({ error: "No review found for this parcel" });
      return reply.send({ data: updated });
    }
  );

  // ─── POST /amara/lifecycle/:parcelId ──────────────────────────────────────
  // Advance deal lifecycle stage
  app.post<{ Params: { parcelId: string } }>(
    "/amara/lifecycle/:parcelId",
    async (req, reply) => {
      const parcelId = Number(req.params.parcelId);
      const { status } = req.body as { status: string };
      const validStatuses = [
        "UNDER_REVIEW", "APPROVED", "NEEDS_INFO", "REJECTED",
        "LOI_SENT", "IN_NEGOTIATION", "UNDER_CONTRACT", "CLOSED", "DEAD",
      ];
      if (!validStatuses.includes(status))
        return reply.status(400).send({ error: `Invalid status. Valid: ${validStatuses.join(", ")}` });

      const [updated] = await db
        .update(dealReviews)
        .set({ lifecycleStatus: status })
        .where(eq(dealReviews.parcelId, parcelId))
        .returning();

      if (!updated) return reply.status(404).send({ error: "No review found for this parcel" });

      // Mirror on parcel
      await db
        .update(landParcels)
        .set({ pipelineStatus: status })
        .where(eq(landParcels.id, parcelId));

      return reply.send({ data: updated });
    }
  );

  // ─── POST /pipeline/run ───────────────────────────────────────────────────
  // Manually trigger the daily pipeline
  app.post("/pipeline/run", async (_req, reply) => {
    const summary = await runDailyPipeline("MANUAL");
    return reply.send({ data: summary });
  });

  // ─── GET /pipeline/runs ───────────────────────────────────────────────────
  app.get("/pipeline/runs", async (_req, reply) => {
    const rows = await db
      .select()
      .from(pipelineRuns)
      .orderBy(desc(pipelineRuns.startedAt))
      .limit(30);
    return reply.send({ data: rows });
  });

  // ─── GET /pipeline/stats ──────────────────────────────────────────────────
  app.get("/pipeline/stats", async (_req, reply) => {
    const [stats] = await db
      .select({
        total:    sql<number>`count(*)::int`,
        approved: sql<number>`count(*) filter (where ${dealReviews.amaraDecision} = 'APPROVED')::int`,
        rejected: sql<number>`count(*) filter (where ${dealReviews.amaraDecision} = 'REJECTED')::int`,
        pending:  sql<number>`count(*) filter (where ${dealReviews.amaraDecision} = 'PENDING')::int`,
        needsInfo: sql<number>`count(*) filter (where ${dealReviews.amaraDecision} = 'NEEDS_MORE_INFO')::int`,
        loi_sent:       sql<number>`count(*) filter (where ${dealReviews.lifecycleStatus} = 'LOI_SENT')::int`,
        in_negotiation: sql<number>`count(*) filter (where ${dealReviews.lifecycleStatus} = 'IN_NEGOTIATION')::int`,
        under_contract: sql<number>`count(*) filter (where ${dealReviews.lifecycleStatus} = 'UNDER_CONTRACT')::int`,
        closed:         sql<number>`count(*) filter (where ${dealReviews.lifecycleStatus} = 'CLOSED')::int`,
      })
      .from(dealReviews);

    return reply.send({ data: stats });
  });
}

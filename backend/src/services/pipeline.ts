import { and, eq, gte, isNull, or, sql } from "drizzle-orm";
import { randomUUID } from "crypto";
import { db } from "../db/client";
import { landParcels } from "../db/schema";
import { dealReviews, pipelineRuns } from "../db/reviewSchema";
import { amaraReviewDeal } from "./amara";

export interface PipelineRunSummary {
  runId: string;
  triggeredBy: "CRON" | "MANUAL";
  parcelsFound: number;
  parcelsSentToAmara: number;
  amaraApproved: number;
  amaraRejected: number;
  startedAt: Date;
  completedAt?: Date;
  status: string;
  errorMessage?: string;
}

/**
 * Score threshold for sending parcels to Amara.
 * Only parcels with feasibilityScore >= this are surfaced.
 */
const MIN_SCORE_THRESHOLD = 60;

/**
 * Max parcels to send to Amara per daily run (cost + rate limit control).
 */
const MAX_PER_RUN = 20;

/**
 * Run the daily deal discovery pipeline:
 * 1. Find top-scoring parcels not yet reviewed by Amara
 * 2. Send each to Amara for autonomous review
 * 3. Save Amara's decisions back to deal_reviews
 * 4. Log the run summary
 */
export async function runDailyPipeline(
  triggeredBy: "CRON" | "MANUAL" = "CRON"
): Promise<PipelineRunSummary> {
  const runId = `run_${new Date().toISOString().slice(0, 10)}_${randomUUID().slice(0, 8)}`;
  const startedAt = new Date();

  // Create run record
  await db.insert(pipelineRuns).values({
    runId,
    triggeredBy,
    status: "RUNNING",
    startedAt: startedAt.toISOString(),
  });

  const summary: PipelineRunSummary = {
    runId,
    triggeredBy,
    parcelsFound: 0,
    parcelsSentToAmara: 0,
    amaraApproved: 0,
    amaraRejected: 0,
    startedAt,
    status: "RUNNING",
  };

  try {
    // ── Step 1: Find candidates ──────────────────────────────────────────────
    // Parcels with good score that don't already have a deal_review row
    const reviewed = db
      .select({ pid: dealReviews.parcelId })
      .from(dealReviews);

    const candidates = await db
      .select()
      .from(landParcels)
      .where(
        and(
          gte(landParcels.feasibilityScore, MIN_SCORE_THRESHOLD),
          sql`${landParcels.id} NOT IN (${reviewed})`
        )
      )
      .orderBy(sql`${landParcels.feasibilityScore} DESC`)
      .limit(MAX_PER_RUN);

    summary.parcelsFound = candidates.length;

    if (candidates.length === 0) {
      await completePipelineRun(runId, summary, "COMPLETED");
      return summary;
    }

    // ── Step 2: Send each candidate to Amara ────────────────────────────────
    for (const parcel of candidates) {
      try {
        // Insert placeholder review row (PENDING) immediately
        await db.insert(dealReviews).values({
          parcelId: parcel.id,
          amaraDecision: "PENDING",
          pipelineRunId: runId,
          surfacedAt: new Date().toISOString(),
          lifecycleStatus: "UNDER_REVIEW",
        }).onConflictDoNothing();

        summary.parcelsSentToAmara++;

        // Call Amara
        const result = await amaraReviewDeal(parcel);

        // Save result
        await db
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
          .where(eq(dealReviews.parcelId, parcel.id));

        // Also update the parcel pipeline_status
        await db
          .update(landParcels)
          .set({ pipelineStatus: `AMARA_${result.decision}` })
          .where(eq(landParcels.id, parcel.id));

        if (result.decision === "APPROVED") summary.amaraApproved++;
        else if (result.decision === "REJECTED") summary.amaraRejected++;
      } catch (parcelErr) {
        // Don't let one parcel failure kill the run
        console.error(`[Pipeline] Error reviewing parcel ${parcel.id}:`, parcelErr);
        await db
          .update(dealReviews)
          .set({ amaraDecision: "NEEDS_MORE_INFO", amaraReasoning: String(parcelErr) })
          .where(eq(dealReviews.parcelId, parcel.id));
      }
    }

    await completePipelineRun(runId, summary, "COMPLETED");
    return summary;
  } catch (err) {
    summary.errorMessage = String(err);
    summary.status = "FAILED";
    await completePipelineRun(runId, summary, "FAILED", String(err));
    throw err;
  }
}

async function completePipelineRun(
  runId: string,
  summary: PipelineRunSummary,
  status: "COMPLETED" | "FAILED",
  errorMessage?: string
) {
  const completedAt = new Date();
  summary.completedAt = completedAt;
  summary.status = status;

  await db
    .update(pipelineRuns)
    .set({
      status,
      parcelsFound: summary.parcelsFound,
      parcelsSentToAmara: summary.parcelsSentToAmara,
      amaraApproved: summary.amaraApproved,
      amaraRejected: summary.amaraRejected,
      errorMessage,
      completedAt: completedAt.toISOString(),
    })
    .where(eq(pipelineRuns.runId, runId));
}

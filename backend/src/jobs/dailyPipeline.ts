/**
 * Daily pipeline cron job.
 *
 * Runs every day at 6:00 AM server time by default (PIPELINE_CRON_SCHEDULE env).
 * Install node-cron: already in package.json dependencies.
 */

import cron from "node-cron";
import { runDailyPipeline } from "../services/pipeline";

const SCHEDULE = process.env.PIPELINE_CRON_SCHEDULE ?? "0 6 * * *"; // 6am daily

let isRunning = false;

export function startDailyPipelineJob() {
  console.log(`[Pipeline] Scheduling daily run: ${SCHEDULE}`);

  cron.schedule(SCHEDULE, async () => {
    if (isRunning) {
      console.warn("[Pipeline] Previous run still in progress — skipping this tick");
      return;
    }
    isRunning = true;
    console.log("[Pipeline] Starting daily run…");
    try {
      const summary = await runDailyPipeline("CRON");
      console.log(
        `[Pipeline] Completed. Found: ${summary.parcelsFound} | Sent: ${summary.parcelsSentToAmara} | Approved: ${summary.amaraApproved} | Rejected: ${summary.amaraRejected}`
      );
    } catch (err) {
      console.error("[Pipeline] Daily run failed:", err);
    } finally {
      isRunning = false;
    }
  });
}

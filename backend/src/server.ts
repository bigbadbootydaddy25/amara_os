import "dotenv/config";
import Fastify from "fastify";
import cors from "@fastify/cors";
import { parcelRoutes } from "./api/parcels";
import { assistantRoutes } from "./api/assistant";
import { amaraRoutes } from "./api/amara";
import { startDailyPipelineJob } from "./jobs/dailyPipeline";

const app = Fastify({
  logger: {
    level: process.env.NODE_ENV === "production" ? "warn" : "info",
    transport:
      process.env.NODE_ENV !== "production"
        ? { target: "pino-pretty", options: { colorize: true } }
        : undefined,
  },
});

// ─── Plugins ──────────────────────────────────────────────────────────────────
await app.register(cors, {
  origin: process.env.CORS_ORIGIN ?? "http://localhost:5173",
  methods: ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
});

// ─── Routes ───────────────────────────────────────────────────────────────────
await app.register(parcelRoutes);
await app.register(assistantRoutes);
await app.register(amaraRoutes);

// Health check
app.get("/health", async () => ({ status: "ok", timestamp: new Date().toISOString() }));

// ─── Start ────────────────────────────────────────────────────────────────────
const host = process.env.HOST ?? "0.0.0.0";
const port = Number(process.env.PORT ?? 3001);

try {
  await app.listen({ host, port });
  console.log(`PropVision API listening on http://${host}:${port}`);

  // Start Amara's daily deal discovery pipeline (cron)
  if (process.env.DISABLE_PIPELINE_CRON !== "true") {
    startDailyPipelineJob();
  }
} catch (err) {
  app.log.error(err);
  process.exit(1);
}

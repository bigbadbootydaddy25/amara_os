import {
  bigint,
  bigserial,
  integer,
  numeric,
  pgTable,
  text,
  timestamp,
  timestamptz,
  varchar,
} from "drizzle-orm/pg-core";
import { sql } from "drizzle-orm";
import { landParcels } from "./schema";

export const dealReviews = pgTable("deal_reviews", {
  id:           bigserial("id", { mode: "number" }).primaryKey(),
  parcelId:     bigint("parcel_id", { mode: "number" }).notNull().references(() => landParcels.id, { onDelete: "cascade" }),

  // Amara's decision
  amaraDecision:    varchar("amara_decision", { length: 32 }).notNull(),
  confidenceScore:  numeric("confidence_score", { precision: 5, scale: 2 }),
  amaraReasoning:   text("amara_reasoning"),

  // Generated documents
  loiText:              text("loi_text"),
  loiGeneratedAt:       timestamp("loi_generated_at", { withTimezone: true }),
  ownerOutreachText:    text("owner_outreach_text"),
  outreachGeneratedAt:  timestamp("outreach_generated_at", { withTimezone: true }),
  negotiationStrategy:  text("negotiation_strategy"),
  negotiationGeneratedAt: timestamp("negotiation_generated_at", { withTimezone: true }),

  // Lifecycle
  lifecycleStatus:  varchar("lifecycle_status", { length: 32 }).default("UNDER_REVIEW"),

  // Pipeline metadata
  pipelineRunId:  varchar("pipeline_run_id", { length: 64 }),
  surfacedAt:     timestamp("surfaced_at", { withTimezone: true }).default(sql`now()`),
  reviewedAt:     timestamp("reviewed_at", { withTimezone: true }),

  // Human override
  humanOverride:     varchar("human_override", { length: 16 }),
  humanOverrideNote: text("human_override_note"),
  overriddenAt:      timestamp("overridden_at", { withTimezone: true }),
  overriddenBy:      text("overridden_by"),

  createdAt: timestamp("created_at", { withTimezone: true }).default(sql`now()`),
  updatedAt: timestamp("updated_at", { withTimezone: true }).default(sql`now()`),
});

export const pipelineRuns = pgTable("pipeline_runs", {
  id:           bigserial("id", { mode: "number" }).primaryKey(),
  runId:        varchar("run_id", { length: 64 }).unique().notNull(),
  triggeredBy:  varchar("triggered_by", { length: 32 }).default("CRON"),
  status:       varchar("status", { length: 32 }).default("RUNNING"),
  parcelsFound:        integer("parcels_found").default(0),
  parcelsSentToAmara:  integer("parcels_sent_to_amara").default(0),
  amaraApproved:       integer("amara_approved").default(0),
  amaraRejected:       integer("amara_rejected").default(0),
  errorMessage:        text("error_message"),
  startedAt:    timestamp("started_at", { withTimezone: true }).default(sql`now()`),
  completedAt:  timestamp("completed_at", { withTimezone: true }),
});

export type DealReview = typeof dealReviews.$inferSelect;
export type NewDealReview = typeof dealReviews.$inferInsert;
export type PipelineRun = typeof pipelineRuns.$inferSelect;

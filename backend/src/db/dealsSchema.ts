import {
  bigint, bigserial, boolean, integer, jsonb, numeric,
  pgTable, text, timestamp, varchar,
} from "drizzle-orm/pg-core";
import { sql } from "drizzle-orm";

export const buyers = pgTable("buyers", {
  id:      bigserial("id", { mode: "number" }).primaryKey(),
  name:    text("name").notNull(),
  email:   text("email"),
  phone:   text("phone"),
  company: text("company"),

  propertyTypes: text("property_types").array(),
  bedsMin:    integer("beds_min"),
  bedsMax:    integer("beds_max"),
  bathsMin:   numeric("baths_min", { precision: 3, scale: 1 }),
  bathsMax:   numeric("baths_max", { precision: 3, scale: 1 }),
  sqftMin:    integer("sqft_min"),
  sqftMax:    integer("sqft_max"),
  priceMin:   numeric("price_min", { precision: 12, scale: 2 }),
  priceMax:   numeric("price_max", { precision: 12, scale: 2 }),
  arvMin:     numeric("arv_min",   { precision: 12, scale: 2 }),
  arvMax:     numeric("arv_max",   { precision: 12, scale: 2 }),
  maxRehab:   numeric("max_rehab", { precision: 12, scale: 2 }),
  minRoiPct:  numeric("min_roi_pct", { precision: 5, scale: 2 }),
  zipCodes:   text("zip_codes").array(),
  states:     text("states").array(),

  isActive:   boolean("is_active").default(true),
  notes:      text("notes"),
  createdAt:  timestamp("created_at", { withTimezone: true }).default(sql`now()`),
  updatedAt:  timestamp("updated_at", { withTimezone: true }).default(sql`now()`),
});

export const deals = pgTable("deals", {
  id:           bigserial("id", { mode: "number" }).primaryKey(),
  address:      text("address"),
  city:         text("city"),
  state:        varchar("state", { length: 2 }),
  zip:          varchar("zip", { length: 10 }),
  county:       text("county"),
  propertyType: varchar("property_type", { length: 32 }),
  beds:         integer("beds"),
  baths:        numeric("baths", { precision: 3, scale: 1 }),
  sqft:         integer("sqft"),
  lotSqft:      integer("lot_sqft"),
  yearBuilt:    integer("year_built"),

  askingPrice:        numeric("asking_price",         { precision: 12, scale: 2 }),
  arv:                numeric("arv",                  { precision: 12, scale: 2 }),
  estimatedRehab:     numeric("estimated_rehab",      { precision: 12, scale: 2 }),
  maxAllowableOffer:  numeric("max_allowable_offer",  { precision: 12, scale: 2 }),
  roiPct:             numeric("roi_pct",              { precision: 5,  scale: 2 }),
  equityPct:          numeric("equity_pct",           { precision: 5,  scale: 2 }),

  comps:          jsonb("comps"),
  source:         varchar("source", { length: 64 }).default("MANUAL"),
  importBatchId:  varchar("import_batch_id", { length: 64 }),
  rawCsvRow:      jsonb("raw_csv_row"),

  status:         varchar("status",         { length: 32 }).default("NEW"),
  pipelineStage:  varchar("pipeline_stage", { length: 32 }).default("NEW"),
  assignedTo:     text("assigned_to"),
  notes:          text("notes"),

  createdAt: timestamp("created_at", { withTimezone: true }).default(sql`now()`),
  updatedAt: timestamp("updated_at", { withTimezone: true }).default(sql`now()`),
});

export const dealMatches = pgTable("deal_matches", {
  id:          bigserial("id", { mode: "number" }).primaryKey(),
  dealId:      bigint("deal_id",  { mode: "number" }).notNull().references(() => deals.id, { onDelete: "cascade" }),
  buyerId:     bigint("buyer_id", { mode: "number" }).notNull().references(() => buyers.id, { onDelete: "cascade" }),
  matchScore:  integer("match_score").notNull(),
  matchReasons: jsonb("match_reasons"),
  isSent:      boolean("is_sent").default(false),
  sentAt:      timestamp("sent_at", { withTimezone: true }),
  createdAt:   timestamp("created_at", { withTimezone: true }).default(sql`now()`),
});

export type Buyer    = typeof buyers.$inferSelect;
export type NewBuyer = typeof buyers.$inferInsert;
export type Deal     = typeof deals.$inferSelect;
export type NewDeal  = typeof deals.$inferInsert;
export type DealMatch = typeof dealMatches.$inferSelect;

import type { FastifyInstance } from "fastify";
import { and, between, eq, gte, ilike, inArray, lte, or, sql } from "drizzle-orm";
import { db } from "../db/client";
import { landParcels, type NewLandParcel } from "../db/schema";
import {
  parcelListQuerySchema,
  parcelCreateSchema,
  sendValidationError,
} from "../middleware/validation";
import { computeFeasibilityScore, parcelRowToScoreInput } from "../services/feasibility";

export async function parcelRoutes(app: FastifyInstance) {
  // ─── GET /parcels ──────────────────────────────────────────────────────────
  app.get("/parcels", async (req, reply) => {
    const parsed = parcelListQuerySchema.safeParse(req.query);
    if (!parsed.success) return sendValidationError(reply, parsed.error);

    const q = parsed.data;
    const conditions: ReturnType<typeof eq>[] = [];

    if (q.city)    conditions.push(ilike(landParcels.city,   `%${q.city}%`) as any);
    if (q.state)   conditions.push(eq(landParcels.state,  q.state) as any);
    if (q.county)  conditions.push(ilike(landParcels.county, `%${q.county}%`) as any);
    if (q.zip)     conditions.push(eq(landParcels.zip, q.zip) as any);

    if (q.min_acres != null) conditions.push(gte(landParcels.areaAcres, q.min_acres) as any);
    if (q.max_acres != null) conditions.push(lte(landParcels.areaAcres, q.max_acres) as any);

    if (q.min_est_max_lot_count != null)
      conditions.push(gte(landParcels.estMaxLotCount, q.min_est_max_lot_count) as any);
    if (q.max_est_max_lot_count != null)
      conditions.push(lte(landParcels.estMaxLotCount, q.max_est_max_lot_count) as any);

    if (q.feasibility_min != null)
      conditions.push(gte(landParcels.feasibilityScore, q.feasibility_min) as any);
    if (q.feasibility_max != null)
      conditions.push(lte(landParcels.feasibilityScore, q.feasibility_max) as any);

    if (q.zoning_codes) {
      const codes = q.zoning_codes.split(",").map((s) => s.trim()).filter(Boolean);
      if (codes.length) conditions.push(inArray(landParcels.zoningCode, codes) as any);
    }

    if (q.allowed_use_categories) {
      const cats = q.allowed_use_categories.split(",").map((s) => s.trim()).filter(Boolean);
      if (cats.length) conditions.push(inArray(landParcels.allowedUseCategory, cats) as any);
    }

    if (q.recommendations) {
      const recs = q.recommendations.split(",").map((s) => s.trim()).filter(Boolean);
      if (recs.length) conditions.push(inArray(landParcels.recommendation, recs) as any);
    }

    if (q.distress) {
      const flags = new Set(q.distress.split(",").map((s) => s.trim()));
      if (flags.has("tax_delinquent"))  conditions.push(eq(landParcels.isTaxDelinquent, true) as any);
      if (flags.has("code_violation"))  conditions.push(eq(landParcels.hasCodeViolations, true) as any);
      if (flags.has("preforeclosure"))  conditions.push(eq(landParcels.hasPreforeclosureFlag, true) as any);
      if (flags.has("vacant"))          conditions.push(
        or(
          eq(landParcels.isVacantLand, true),
          eq(landParcels.isVacantStructure, true)
        ) as any
      );
    }

    const offset = (q.page - 1) * q.limit;

    const rows = await db
      .select({
        id:              landParcels.id,
        apn:             landParcels.apn,
        city:            landParcels.city,
        state:           landParcels.state,
        county:          landParcels.county,
        zip:             landParcels.zip,
        areaAcres:       landParcels.areaAcres,
        zoningCode:      landParcels.zoningCode,
        allowedUseCategory: landParcels.allowedUseCategory,
        estMaxLotCount:  landParcels.estMaxLotCount,
        feasibilityScore: landParcels.feasibilityScore,
        recommendation:  landParcels.recommendation,
        isTaxDelinquent: landParcels.isTaxDelinquent,
        hasCodeViolations: landParcels.hasCodeViolations,
        hasPreforeclosureFlag: landParcels.hasPreforeclosureFlag,
        isVacantLand:    landParcels.isVacantLand,
        pipelineStatus:  landParcels.pipelineStatus,
        latitude:        landParcels.latitude,
        longitude:       landParcels.longitude,
      })
      .from(landParcels)
      .where(conditions.length ? and(...(conditions as any[])) : undefined)
      .limit(q.limit)
      .offset(offset);

    // total count
    const [{ count }] = await db
      .select({ count: sql<number>`count(*)::int` })
      .from(landParcels)
      .where(conditions.length ? and(...(conditions as any[])) : undefined);

    return reply.send({
      data: rows,
      pagination: {
        page: q.page,
        limit: q.limit,
        total: count,
        totalPages: Math.ceil(count / q.limit),
      },
    });
  });

  // ─── GET /parcels/:id ──────────────────────────────────────────────────────
  app.get<{ Params: { id: string } }>("/parcels/:id", async (req, reply) => {
    const id = Number(req.params.id);
    if (isNaN(id)) return reply.status(400).send({ error: "Invalid id" });

    const [row] = await db.select().from(landParcels).where(eq(landParcels.id, id));
    if (!row) return reply.status(404).send({ error: "Parcel not found" });

    return reply.send({ data: row });
  });

  // ─── POST /parcels ─────────────────────────────────────────────────────────
  app.post("/parcels", async (req, reply) => {
    const parsed = parcelCreateSchema.safeParse(req.body);
    if (!parsed.success) return sendValidationError(reply, parsed.error);

    const body = parsed.data;

    // Map snake_case body to camelCase Drizzle columns
    const insertPayload: NewLandParcel = {
      apn:            body.apn,
      addressLine1:   body.address_line1,
      city:           body.city,
      state:          body.state,
      zip:            body.zip,
      county:         body.county,
      jurisdiction:   body.jurisdiction,
      latitude:       body.latitude,
      longitude:      body.longitude,
      areaSqft:       body.area_sqft,
      areaAcres:      body.area_acres,
      ownerName:              body.owner_name,
      ownerMailingAddress:    body.owner_mailing_address,
      lastSaleDate:           body.last_sale_date,
      lastSalePrice:          body.last_sale_price?.toString(),
      assessedLandValue:      body.assessed_land_value?.toString(),
      assessedTotalValue:     body.assessed_total_value?.toString(),
      yearsOwned:             body.years_owned?.toString(),
      zoningCode:         body.zoning_code,
      zoningDescription:  body.zoning_description,
      allowedUseCategory: body.allowed_use_category,
      minLotSizeSqft:     body.min_lot_size_sqft,
      maxUnitsPerAcre:    body.max_units_per_acre,
      floorAreaRatio:     body.floor_area_ratio,
      maxHeightFt:        body.max_height_ft,
      frontSetbackFt:     body.front_setback_ft,
      sideSetbackFt:      body.side_setback_ft,
      rearSetbackFt:      body.rear_setback_ft,
      topographyClass:       body.topography_class,
      floodZoneCode:         body.flood_zone_code,
      hasEnvironmentalFlag:  body.has_environmental_flag,
      accessType:            body.access_type,
      hasExistingStructure:  body.has_existing_structure,
      existingUseType:       body.existing_use_type,
      existingBuildingSqft:  body.existing_building_sqft,
      hasWater: body.has_water,
      hasSewer: body.has_sewer,
      hasPower: body.has_power,
      hasGas:   body.has_gas,
      schoolDistrict:    body.school_district,
      schoolScoreBucket: body.school_score_bucket,
      nearbyNewBuildPricePerUnit:        body.nearby_new_build_price_per_unit?.toString(),
      nearbyResalePricePerSqft:          body.nearby_resale_price_per_sqft?.toString(),
      estimatedLandValueTotal:           body.estimated_land_value_total?.toString(),
      estimatedLandValuePerAcre:         body.estimated_land_value_per_acre?.toString(),
      estimatedLandValuePerPotentialLot: body.estimated_land_value_per_potential_lot?.toString(),
      isTaxDelinquent:      body.is_tax_delinquent,
      taxDelinquentAmount:  body.tax_delinquent_amount?.toString(),
      hasCodeViolations:    body.has_code_violations,
      codeViolationCount:   body.code_violation_count,
      hasPreforeclosureFlag: body.has_preforeclosure_flag,
      isVacantLand:         body.is_vacant_land,
      isVacantStructure:    body.is_vacant_structure,
      targetProductType: body.target_product_type,
      estMaxLotCount:    body.est_max_lot_count,
      estMaxUnitCount:   body.est_max_unit_count,
      pipelineStatus:    body.pipeline_status,
      notes:             body.notes,
    };

    // Auto-compute feasibility on create
    const scoreInput = parcelRowToScoreInput({
      areaAcres:       insertPayload.areaAcres ?? null,
      estMaxLotCount:  insertPayload.estMaxLotCount ?? null,
      zoningCode:      insertPayload.zoningCode ?? null,
      allowedUseCategory: insertPayload.allowedUseCategory ?? null,
      isTaxDelinquent: insertPayload.isTaxDelinquent ?? null,
      hasCodeViolations: insertPayload.hasCodeViolations ?? null,
      yearsOwned:      insertPayload.yearsOwned ?? null,
      floodZoneCode:   insertPayload.floodZoneCode ?? null,
      topographyClass: insertPayload.topographyClass ?? null,
      estimatedLandValuePerPotentialLot: insertPayload.estimatedLandValuePerPotentialLot ?? null,
      nearbyNewBuildPricePerUnit: insertPayload.nearbyNewBuildPricePerUnit ?? null,
    });
    const { score, recommendation } = computeFeasibilityScore(scoreInput);
    insertPayload.feasibilityScore = score;
    insertPayload.recommendation = recommendation;

    const [created] = await db.insert(landParcels).values(insertPayload).returning();
    return reply.status(201).send({ data: created });
  });

  // ─── POST /parcels/:id/recompute-feasibility ───────────────────────────────
  app.post<{ Params: { id: string } }>(
    "/parcels/:id/recompute-feasibility",
    async (req, reply) => {
      const id = Number(req.params.id);
      if (isNaN(id)) return reply.status(400).send({ error: "Invalid id" });

      const [row] = await db.select().from(landParcels).where(eq(landParcels.id, id));
      if (!row) return reply.status(404).send({ error: "Parcel not found" });

      const { score, recommendation } = computeFeasibilityScore(parcelRowToScoreInput(row));

      const [updated] = await db
        .update(landParcels)
        .set({ feasibilityScore: score, recommendation })
        .where(eq(landParcels.id, id))
        .returning();

      return reply.send({ data: updated });
    }
  );
}

import { z } from "zod";
import type { FastifyRequest, FastifyReply } from "fastify";

/** Shared query-param schema for GET /parcels */
export const parcelListQuerySchema = z.object({
  city:                    z.string().optional(),
  state:                   z.string().max(2).optional(),
  county:                  z.string().optional(),
  zip:                     z.string().optional(),
  min_acres:               z.coerce.number().optional(),
  max_acres:               z.coerce.number().optional(),
  zoning_codes:            z.string().optional(), // comma-separated
  allowed_use_categories:  z.string().optional(), // comma-separated
  min_est_max_lot_count:   z.coerce.number().int().optional(),
  max_est_max_lot_count:   z.coerce.number().int().optional(),
  feasibility_min:         z.coerce.number().int().min(0).max(100).optional(),
  feasibility_max:         z.coerce.number().int().min(0).max(100).optional(),
  recommendations:         z.string().optional(), // e.g. "GO,MAYBE"
  distress:                z.string().optional(), // e.g. "tax_delinquent,vacant"
  page:                    z.coerce.number().int().min(1).default(1),
  limit:                   z.coerce.number().int().min(1).max(200).default(50),
});

/** Body schema for POST /parcels (create/upsert) */
export const parcelCreateSchema = z.object({
  apn:            z.string().max(64).optional(),
  address_line1:  z.string().optional(),
  city:           z.string().optional(),
  state:          z.string().max(2).optional(),
  zip:            z.string().max(10).optional(),
  county:         z.string().optional(),
  jurisdiction:   z.string().optional(),
  latitude:       z.number().optional(),
  longitude:      z.number().optional(),
  area_sqft:      z.number().optional(),
  area_acres:     z.number().optional(),

  owner_name:             z.string().optional(),
  owner_mailing_address:  z.string().optional(),
  last_sale_date:         z.string().optional(),
  last_sale_price:        z.number().optional(),
  assessed_land_value:    z.number().optional(),
  assessed_total_value:   z.number().optional(),
  years_owned:            z.number().optional(),

  zoning_code:          z.string().max(64).optional(),
  zoning_description:   z.string().optional(),
  allowed_use_category: z.string().max(64).optional(),
  min_lot_size_sqft:    z.number().optional(),
  max_units_per_acre:   z.number().optional(),
  floor_area_ratio:     z.number().optional(),
  max_height_ft:        z.number().optional(),
  front_setback_ft:     z.number().optional(),
  side_setback_ft:      z.number().optional(),
  rear_setback_ft:      z.number().optional(),

  topography_class:       z.string().max(32).optional(),
  flood_zone_code:        z.string().max(32).optional(),
  has_environmental_flag: z.boolean().optional(),
  access_type:            z.string().max(32).optional(),
  has_existing_structure: z.boolean().optional(),
  existing_use_type:      z.string().max(64).optional(),
  existing_building_sqft: z.number().optional(),

  has_water: z.boolean().optional(),
  has_sewer: z.boolean().optional(),
  has_power: z.boolean().optional(),
  has_gas:   z.boolean().optional(),
  school_district:    z.string().optional(),
  school_score_bucket: z.string().max(16).optional(),

  nearby_new_build_price_per_unit:        z.number().optional(),
  nearby_resale_price_per_sqft:           z.number().optional(),
  estimated_land_value_total:             z.number().optional(),
  estimated_land_value_per_acre:          z.number().optional(),
  estimated_land_value_per_potential_lot: z.number().optional(),

  is_tax_delinquent:      z.boolean().optional(),
  tax_delinquent_amount:  z.number().optional(),
  has_code_violations:    z.boolean().optional(),
  code_violation_count:   z.number().int().optional(),
  has_preforeclosure_flag: z.boolean().optional(),
  is_vacant_land:         z.boolean().optional(),
  is_vacant_structure:    z.boolean().optional(),

  target_product_type: z.string().max(64).optional(),
  est_max_lot_count:   z.number().int().optional(),
  est_max_unit_count:  z.number().int().optional(),
  pipeline_status:     z.string().max(32).optional(),
  notes:               z.string().optional(),
});

export type ParcelListQuery = z.infer<typeof parcelListQuerySchema>;
export type ParcelCreateBody = z.infer<typeof parcelCreateSchema>;

/** Helper to send a 400 with Zod error details */
export function sendValidationError(reply: FastifyReply, error: z.ZodError) {
  return reply.status(400).send({
    error: "Validation failed",
    details: error.flatten().fieldErrors,
  });
}

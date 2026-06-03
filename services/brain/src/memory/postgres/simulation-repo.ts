import type { SimulationResult } from '../../types.js';
import { getPool } from './pool.js';

export const SimulationRepo = {
  async create(sim: SimulationResult): Promise<string> {
    const result = await getPool().query<{ id: string }>(
      `INSERT INTO mirofish_simulations (
        deal_id, property_id, features,
        conservative, base, aggressive,
        recommended_mao, recommended_strategy,
        risk_score, confidence_score, model_version
      ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
      RETURNING id`,
      [
        sim.dealId ?? null,
        sim.propertyId,
        JSON.stringify(sim.features),
        JSON.stringify(sim.conservative),
        JSON.stringify(sim.base),
        JSON.stringify(sim.aggressive),
        sim.recommendedMao,
        sim.recommendedStrategy,
        sim.riskScore,
        sim.confidenceScore,
        sim.modelVersion,
      ],
    );
    return result.rows[0].id;
  },

  async findLatestForProperty(propertyId: string): Promise<SimulationResult | null> {
    const result = await getPool().query(
      `SELECT * FROM mirofish_simulations
       WHERE property_id = $1
       ORDER BY created_at DESC
       LIMIT 1`,
      [propertyId],
    );
    if (!result.rows[0]) return null;
    return rowToSimulation(result.rows[0]);
  },

  async findByDeal(dealId: string): Promise<SimulationResult[]> {
    const result = await getPool().query(
      `SELECT * FROM mirofish_simulations
       WHERE deal_id = $1
       ORDER BY created_at DESC`,
      [dealId],
    );
    return result.rows.map(rowToSimulation);
  },
};

function rowToSimulation(row: Record<string, unknown>): SimulationResult {
  return {
    propertyId:          row.property_id as string,
    dealId:              (row.deal_id as string | null) ?? undefined,
    features:            row.features as SimulationResult['features'],
    conservative:        row.conservative as SimulationResult['conservative'],
    base:                row.base as SimulationResult['base'],
    aggressive:          row.aggressive as SimulationResult['aggressive'],
    recommendedMao:      parseFloat(row.recommended_mao as string),
    recommendedStrategy: row.recommended_strategy as SimulationResult['recommendedStrategy'],
    riskScore:           parseFloat(row.risk_score as string),
    confidenceScore:     parseFloat(row.confidence_score as string),
    modelVersion:        row.model_version as string,
    createdAt:           row.created_at as Date,
  };
}

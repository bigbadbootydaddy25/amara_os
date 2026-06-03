import type { MiroFishWeights } from '../../types.js';
import { getPool } from './pool.js';

export const WeightsRepo = {
  async getLatest(): Promise<MiroFishWeights | null> {
    const result = await getPool().query(
      `SELECT * FROM mirofish_weights ORDER BY created_at DESC LIMIT 1`,
    );
    return result.rows[0] ? rowToWeights(result.rows[0]) : null;
  },

  async getByVersion(version: string): Promise<MiroFishWeights | null> {
    const result = await getPool().query(
      `SELECT * FROM mirofish_weights WHERE version = $1`,
      [version],
    );
    return result.rows[0] ? rowToWeights(result.rows[0]) : null;
  },

  async save(weights: MiroFishWeights): Promise<void> {
    const fw = weights;
    const featureWeights = {
      arv_discount_weight: fw.arvDiscountWeight,
      rehab_risk_weight:   fw.rehabRiskWeight,
      liquidity_weight:    fw.liquidityWeight,
      buyer_demand_weight: fw.buyerDemandWeight,
      distress_weight:     fw.distressWeight,
    };

    await getPool().query(
      `INSERT INTO mirofish_weights
         (version, zip_priors, feature_weights, training_samples, last_trained_at, validation_mae)
       VALUES ($1,$2,$3,$4,$5,$6)
       ON CONFLICT (version) DO UPDATE SET
         zip_priors      = EXCLUDED.zip_priors,
         feature_weights = EXCLUDED.feature_weights,
         training_samples = EXCLUDED.training_samples,
         last_trained_at = EXCLUDED.last_trained_at,
         validation_mae  = EXCLUDED.validation_mae`,
      [
        weights.version,
        JSON.stringify(weights.zipPriors),
        JSON.stringify(featureWeights),
        weights.trainingSamples,
        weights.lastTrainedAt ?? null,
        weights.validationMae ?? null,
      ],
    );
  },

  async recordOutcome(
    dealId: string,
    propertyId: string,
    predicted: {
      mao: number; arv: number; rehab: number; dom: number; profit: number;
    },
    actual: {
      contractPrice: number; arv?: number; rehab?: number; dom?: number;
      profit: number; scenario?: string; modelVersion: string;
    },
  ): Promise<void> {
    await getPool().query(
      `INSERT INTO deal_outcomes (
        deal_id, property_id,
        predicted_mao, actual_contract,
        predicted_arv, actual_arv,
        predicted_rehab, actual_rehab,
        predicted_dom, actual_dom,
        predicted_profit, actual_profit,
        actual_scenario, model_version
      ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)`,
      [
        dealId, propertyId,
        predicted.mao, actual.contractPrice,
        predicted.arv, actual.arv ?? null,
        predicted.rehab, actual.rehab ?? null,
        predicted.dom, actual.dom ?? null,
        predicted.profit, actual.profit,
        actual.scenario ?? null,
        actual.modelVersion,
      ],
    );
  },
};

function rowToWeights(row: Record<string, unknown>): MiroFishWeights {
  const fw = row.feature_weights as Record<string, number>;
  return {
    version:            row.version as string,
    arvDiscountWeight:  fw.arv_discount_weight ?? 0.35,
    rehabRiskWeight:    fw.rehab_risk_weight   ?? 0.20,
    liquidityWeight:    fw.liquidity_weight     ?? 0.20,
    buyerDemandWeight:  fw.buyer_demand_weight  ?? 0.15,
    distressWeight:     fw.distress_weight      ?? 0.10,
    zipPriors:          (row.zip_priors as Record<string, unknown>) as MiroFishWeights['zipPriors'],
    trainingSamples:    row.training_samples as number,
    lastTrainedAt:      row.last_trained_at ? new Date(row.last_trained_at as string) : undefined,
    validationMae:      row.validation_mae ? parseFloat(row.validation_mae as string) : undefined,
  };
}

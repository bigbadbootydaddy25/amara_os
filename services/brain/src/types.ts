// Core domain types for AMARA OS brain service

export type DealStrategy = 'wholesale' | 'flip' | 'brrrr' | 'subject_to' | 'novation' | 'unknown';
export type DealStatus = 'lead' | 'analyzing' | 'under_contract' | 'closed_won' | 'closed_lost' | 'dead';
export type MarketRegime = 'hot' | 'neutral' | 'cold' | 'distressed';
export type IngestionSource = 'manual' | 'csv_upload' | 'json_upload' | 'openclaw_scrape' | 'copy_paste';
export type ExitType = 'assigned' | 'double_close' | 'listed' | 'rented' | 'held' | 'lost';
export type ScenarioType = 'conservative' | 'base' | 'aggressive';

// ─────────────────────────────────────────────
// PROPERTY
// ─────────────────────────────────────────────

export interface Property {
  id?: string;
  address: string;
  city: string;
  state: string;
  zip: string;
  county?: string;
  apn?: string;
  latitude?: number;
  longitude?: number;

  bedrooms?: number;
  bathrooms?: number;
  sqft?: number;
  lotSqft?: number;
  yearBuilt?: number;
  propertyType?: string;
  zoning?: string;

  conditionGrade?: number;   // 1–10
  rehabEstimate?: number;

  askingPrice?: number;
  arvEstimate?: number;
  arvLow?: number;
  arvHigh?: number;

  taxDelinquent?: boolean;
  bankruptcy?: boolean;
  liens?: boolean;
  vacant?: boolean;
  preForeclosure?: boolean;

  ingestionSource: IngestionSource;
  rawInput?: Record<string, unknown>;
  notes?: string;
}

// ─────────────────────────────────────────────
// MIROFISH FEATURE VECTOR
// ─────────────────────────────────────────────

export interface MiroFishFeatures {
  // Core valuation
  arvMidpoint: number;          // median of low/high ARV
  discountDepth: number;        // (ARV - asking) / ARV  [0–1]
  rehabRisk: number;            // normalized rehab cost / ARV  [0–1]

  // Liquidity & demand
  liquidityScore: number;       // [0–1] based on DOM, inventory, market regime
  buyerDemandHeat: number;      // [0–1] buyer activity in ZIP
  exitVelocity: number;         // estimated days-to-close

  // Distress composite
  distressScore: number;        // weighted sum of distress flags [0–1]

  // Assignment probability
  assignmentProbability: number; // [0–1]

  // Computed ceiling
  maoCeiling: number;           // max allowable offer

  // Market context
  marketRegime: MarketRegime;
  zipMedianArv?: number;
  zipAvgDom?: number;
}

// ─────────────────────────────────────────────
// SCENARIO OUTPUT
// ─────────────────────────────────────────────

export interface ScenarioOutput {
  scenario: ScenarioType;
  mao: number;
  roiMin: number;
  roiMax: number;
  netProfit: number;
  exitDays: number;
  riskScore: number;         // [0–1]
  strategy: DealStrategy;
  reasoning: string;
}

// ─────────────────────────────────────────────
// SIMULATION RESULT
// ─────────────────────────────────────────────

export interface SimulationResult {
  propertyId: string;
  dealId?: string;
  features: MiroFishFeatures;
  conservative: ScenarioOutput;
  base: ScenarioOutput;
  aggressive: ScenarioOutput;
  recommendedMao: number;
  recommendedStrategy: DealStrategy;
  riskScore: number;
  confidenceScore: number;
  modelVersion: string;
  createdAt: Date;
}

// ─────────────────────────────────────────────
// MODEL WEIGHTS
// ─────────────────────────────────────────────

export interface MiroFishWeights {
  version: string;
  arvDiscountWeight: number;
  rehabRiskWeight: number;
  liquidityWeight: number;
  buyerDemandWeight: number;
  distressWeight: number;
  zipPriors: Record<string, ZipPrior>;
  trainingSamples: number;
  lastTrainedAt?: Date;
  validationMae?: number;
}

export interface ZipPrior {
  medianArv: number;
  avgDom: number;
  avgDiscountDepth: number;
  sampleCount: number;
}

// ─────────────────────────────────────────────
// INGESTION
// ─────────────────────────────────────────────

export interface RawDealInput {
  address: string;
  city?: string;
  state?: string;
  zip: string;
  askingPrice?: number | string;
  arvEstimate?: number | string;
  arvLow?: number | string;
  arvHigh?: number | string;
  rehabEstimate?: number | string;
  bedrooms?: number | string;
  bathrooms?: number | string;
  sqft?: number | string;
  yearBuilt?: number | string;
  conditionGrade?: number | string;
  taxDelinquent?: boolean | string;
  bankruptcy?: boolean | string;
  liens?: boolean | string;
  vacant?: boolean | string;
  notes?: string;
  [key: string]: unknown;
}

export interface IngestionResult {
  success: boolean;
  propertyId?: string;
  simulationId?: string;
  errors: string[];
  processingMs: number;
}

// ─────────────────────────────────────────────
// OUTCOME (learning feed)
// ─────────────────────────────────────────────

export interface DealOutcomeInput {
  dealId: string;
  actualContractPrice: number;
  actualArv?: number;
  actualRehab?: number;
  actualDom?: number;
  actualProfit: number;
  exitType: ExitType;
  actualScenario?: ScenarioType;
  notes?: string;
}

export interface WeightUpdate {
  previousVersion: string;
  newVersion: string;
  adjustments: Record<string, number>;
  trainingSamples: number;
  mae: number;
}

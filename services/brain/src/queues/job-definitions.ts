import type { IngestionSource, MarketRegime, DealOutcomeInput } from '../types.js';

// ─── Deal ingestion job ───────────────────────────────────────────────────────

export interface DealIngestionJobData {
  raw:          Record<string, unknown>;
  source:       IngestionSource;
  marketRegime: MarketRegime;
  traceId?:     string;
}

export interface DealIngestionJobResult {
  propertyId?:   string;
  simulationId?: string;
  errors:        string[];
  processingMs:  number;
}

// ─── Batch ingestion job ──────────────────────────────────────────────────────

export interface BatchIngestionJobData {
  payload:      string;           // raw CSV or JSON text
  format:       'csv' | 'json';
  source:       IngestionSource;
  marketRegime: MarketRegime;
  traceId?:     string;
}

export interface BatchIngestionJobResult {
  total:     number;
  succeeded: number;
  failed:    number;
}

// ─── Outcome learning job ─────────────────────────────────────────────────────

export interface OutcomeLearningJobData {
  outcome:    DealOutcomeInput;
  propertyId: string;
  zip:        string;
  buyerId?:   string;
  strategy?:  string;
}

export interface OutcomeLearningJobResult {
  weightVersion: string;
  mae:           number;
  graphSynced:   boolean;
}

// ─── Market classification job ────────────────────────────────────────────────

export interface MarketClassificationJobData {
  zip:               string;
  metro?:            string;
  avgDom?:           number;
  inventoryCount?:   number;
  priceReductionPct?: number;
  foreclosureRate?:  number;
  medianArv?:        number;
  notes?:            string;
}

export interface MarketClassificationJobResult {
  regime:  string;
  stored:  boolean;
  errors:  string[];
}

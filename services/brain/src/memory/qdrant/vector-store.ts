import { randomUUID } from 'crypto';
import { getQdrant, COLLECTIONS } from './qdrant-client.js';
import { embedText, propertyToText, marketIntelToText, buyerSignalToText } from './embedder.js';
import type { Property, SimulationResult, MarketRegime } from '../../types.js';

// ─────────────────────────────────────────────
// PROPERTY UPSERT
// ─────────────────────────────────────────────

export async function upsertProperty(
  property: Property,
  sim?: SimulationResult,
): Promise<void> {
  const text = propertyToText(property, sim);
  const vector = await embedText(text);

  await getQdrant().upsert(COLLECTIONS.PROPERTIES, {
    wait: true,
    points: [{
      id:      property.id ?? randomUUID(),
      vector,
      payload: {
        property_id:    property.id,
        address:        property.address,
        city:           property.city,
        state:          property.state,
        zip:            property.zip,
        arv_estimate:   property.arvEstimate ?? null,
        asking_price:   property.askingPrice ?? null,
        rehab_estimate: property.rehabEstimate ?? null,
        condition_grade: property.conditionGrade ?? null,
        tax_delinquent:  property.taxDelinquent ?? false,
        vacant:          property.vacant ?? false,
        ingestion_source: property.ingestionSource,
        recommended_mao:  sim?.recommendedMao ?? null,
        risk_score:       sim?.riskScore ?? null,
        strategy:         sim?.recommendedStrategy ?? null,
        indexed_at:       new Date().toISOString(),
      },
    }],
  });
}

// ─────────────────────────────────────────────
// PROPERTY SEARCH
// ─────────────────────────────────────────────

export interface PropertySearchResult {
  propertyId: string;
  address: string;
  zip: string;
  arvEstimate: number | null;
  recommendedMao: number | null;
  riskScore: number | null;
  strategy: string | null;
  score: number;
}

export async function searchProperties(
  query: string,
  filters?: { zip?: string; state?: string; maxRisk?: number; minArv?: number },
  limit = 10,
): Promise<PropertySearchResult[]> {
  const vector = await embedText(query);

  const must: unknown[] = [];
  if (filters?.zip)      must.push({ key: 'zip',        match: { value: filters.zip } });
  if (filters?.state)    must.push({ key: 'state',      match: { value: filters.state } });
  if (filters?.maxRisk)  must.push({ key: 'risk_score', range: { lte: filters.maxRisk } });
  if (filters?.minArv)   must.push({ key: 'arv_estimate', range: { gte: filters.minArv } });

  const results = await getQdrant().search(COLLECTIONS.PROPERTIES, {
    vector,
    limit,
    filter: must.length > 0 ? { must } : undefined,
    with_payload: true,
  });

  return results.map((r) => ({
    propertyId:     r.payload?.property_id as string,
    address:        r.payload?.address as string,
    zip:            r.payload?.zip as string,
    arvEstimate:    r.payload?.arv_estimate as number | null,
    recommendedMao: r.payload?.recommended_mao as number | null,
    riskScore:      r.payload?.risk_score as number | null,
    strategy:       r.payload?.strategy as string | null,
    score:          r.score,
  }));
}

// ─────────────────────────────────────────────
// MARKET INTEL UPSERT + SEARCH
// ─────────────────────────────────────────────

export interface MarketIntelPayload {
  id?: string;
  zip: string;
  metro?: string;
  regime: MarketRegime;
  medianArv?: number;
  avgDom?: number;
  inventoryCount?: number;
  notes?: string;
}

export async function upsertMarketIntel(data: MarketIntelPayload): Promise<void> {
  const text = marketIntelToText(data);
  const vector = await embedText(text);
  const id = data.id ?? randomUUID();

  await getQdrant().upsert(COLLECTIONS.MARKET_INTEL, {
    wait: true,
    points: [{
      id,
      vector,
      payload: {
        zip:            data.zip,
        metro:          data.metro ?? null,
        regime:         data.regime,
        median_arv:     data.medianArv ?? null,
        avg_dom:        data.avgDom ?? null,
        inventory_count: data.inventoryCount ?? null,
        notes:          data.notes ?? null,
        indexed_at:     new Date().toISOString(),
      },
    }],
  });
}

export async function searchMarketIntel(
  query: string,
  filters?: { zip?: string; regime?: string },
  limit = 5,
): Promise<Array<{ score: number; payload: Record<string, unknown> }>> {
  const vector = await embedText(query);
  const must: unknown[] = [];
  if (filters?.zip)    must.push({ key: 'zip',    match: { value: filters.zip } });
  if (filters?.regime) must.push({ key: 'regime', match: { value: filters.regime } });

  const results = await getQdrant().search(COLLECTIONS.MARKET_INTEL, {
    vector, limit,
    filter: must.length > 0 ? { must } : undefined,
    with_payload: true,
  });

  return results.map((r) => ({ score: r.score, payload: r.payload as Record<string, unknown> }));
}

// ─────────────────────────────────────────────
// BUYER SIGNALS UPSERT + SEARCH
// ─────────────────────────────────────────────

export interface BuyerSignalPayload {
  buyerId: string;
  name: string;
  buyerType?: string;
  targetZips?: string[];
  minPrice?: number;
  maxPrice?: number;
  notes?: string;
}

export async function upsertBuyerSignal(data: BuyerSignalPayload): Promise<void> {
  const text = buyerSignalToText(data);
  const vector = await embedText(text);

  await getQdrant().upsert(COLLECTIONS.BUYER_SIGNALS, {
    wait: true,
    points: [{
      id:      data.buyerId,
      vector,
      payload: {
        buyer_id:    data.buyerId,
        name:        data.name,
        buyer_type:  data.buyerType ?? null,
        target_zips: data.targetZips ?? [],
        min_price:   data.minPrice ?? null,
        max_price:   data.maxPrice ?? null,
        notes:       data.notes ?? null,
        indexed_at:  new Date().toISOString(),
      },
    }],
  });
}

export async function searchBuyers(
  query: string,
  filters?: { zip?: string; buyerType?: string },
  limit = 10,
): Promise<Array<{ buyerId: string; name: string; score: number; buyerType: string | null }>> {
  const vector = await embedText(query);
  const must: unknown[] = [];
  if (filters?.zip)       must.push({ key: 'target_zips', match: { any: [filters.zip] } });
  if (filters?.buyerType) must.push({ key: 'buyer_type',  match: { value: filters.buyerType } });

  const results = await getQdrant().search(COLLECTIONS.BUYER_SIGNALS, {
    vector, limit,
    filter: must.length > 0 ? { must } : undefined,
    with_payload: true,
  });

  return results.map((r) => ({
    buyerId:    r.payload?.buyer_id as string,
    name:       r.payload?.name as string,
    score:      r.score,
    buyerType:  r.payload?.buyer_type as string | null,
  }));
}

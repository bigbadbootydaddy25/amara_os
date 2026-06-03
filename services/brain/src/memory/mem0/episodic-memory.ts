/**
 * Episodic Memory Layer — Mem0
 *
 * Stores cross-session facts about deals, properties, market conditions,
 * and buyer behaviour. Falls back to a local in-process store when
 * MEM0_API_KEY is not set, so the system is fully local by default.
 */

import type { SimulationResult, Property, DealOutcomeInput } from '../../types.js';

// ─── Types ────────────────────────────────────────────────────────────────────

export interface EpisodicMemory {
  id:        string;
  userId:    string;   // scoped per agent/session
  memory:    string;   // natural-language fact
  metadata?: Record<string, unknown>;
  createdAt: Date;
}

export interface MemorySearchResult {
  id:       string;
  memory:   string;
  score:    number;
  metadata?: Record<string, unknown>;
}

// ─── Local fallback store ─────────────────────────────────────────────────────

class LocalMemoryStore {
  private store: Map<string, EpisodicMemory[]> = new Map();

  add(userId: string, memory: string, metadata?: Record<string, unknown>): string {
    const id = crypto.randomUUID();
    const entry: EpisodicMemory = {
      id, userId, memory, metadata, createdAt: new Date(),
    };
    const existing = this.store.get(userId) ?? [];
    this.store.set(userId, [...existing, entry]);
    return id;
  }

  search(userId: string, query: string, limit: number): MemorySearchResult[] {
    const entries = this.store.get(userId) ?? [];
    const q = query.toLowerCase();

    return entries
      .map((e) => ({
        id:       e.id,
        memory:   e.memory,
        metadata: e.metadata,
        // Naive relevance: count query term matches in memory text
        score: e.memory.toLowerCase().split(' ')
          .filter((w) => q.includes(w) || w.includes(q.split(' ')[0]))
          .length / Math.max(e.memory.split(' ').length, 1),
      }))
      .sort((a, b) => b.score - a.score)
      .slice(0, limit);
  }

  getAll(userId: string): EpisodicMemory[] {
    return this.store.get(userId) ?? [];
  }

  delete(id: string, userId: string): void {
    const entries = this.store.get(userId) ?? [];
    this.store.set(userId, entries.filter((e) => e.id !== id));
  }

  clear(userId: string): void {
    this.store.delete(userId);
  }
}

const localStore = new LocalMemoryStore();

// ─── Mem0 cloud client (optional) ────────────────────────────────────────────

let cloudClient: CloudMemClient | null = null;

interface CloudMemClient {
  add(messages: Array<{ role: string; content: string }>, options: { user_id: string; metadata?: Record<string, unknown> }): Promise<{ results: Array<{ id: string }> }>;
  search(query: string, options: { user_id: string; limit?: number }): Promise<Array<{ id: string; memory: string; score: number; metadata?: Record<string, unknown> }>>;
  getAll(options: { user_id: string }): Promise<Array<{ id: string; memory: string; metadata?: Record<string, unknown> }>>;
  delete(memoryId: string): Promise<void>;
}

async function getCloudClient(): Promise<CloudMemClient | null> {
  const apiKey = process.env.MEM0_API_KEY;
  if (!apiKey) return null;
  if (cloudClient) return cloudClient;

  try {
    const { MemoryClient } = await import('mem0ai');
    cloudClient = new MemoryClient({ apiKey }) as unknown as CloudMemClient;
    return cloudClient;
  } catch {
    return null;
  }
}

// ─── Public API ───────────────────────────────────────────────────────────────

const DEFAULT_USER = 'amara_brain';

export async function rememberFact(
  fact: string,
  userId = DEFAULT_USER,
  metadata?: Record<string, unknown>,
): Promise<string> {
  const cloud = await getCloudClient();

  if (cloud) {
    const result = await cloud.add(
      [{ role: 'user', content: fact }],
      { user_id: userId, metadata },
    );
    return result.results[0]?.id ?? crypto.randomUUID();
  }

  return localStore.add(userId, fact, metadata);
}

export async function searchMemory(
  query: string,
  userId = DEFAULT_USER,
  limit = 5,
): Promise<MemorySearchResult[]> {
  const cloud = await getCloudClient();

  if (cloud) {
    const results = await cloud.search(query, { user_id: userId, limit });
    return results.map((r) => ({
      id: r.id, memory: r.memory, score: r.score, metadata: r.metadata,
    }));
  }

  return localStore.search(userId, query, limit);
}

export async function getAllMemories(userId = DEFAULT_USER): Promise<EpisodicMemory[]> {
  const cloud = await getCloudClient();

  if (cloud) {
    const results = await cloud.getAll({ user_id: userId });
    return results.map((r) => ({
      id: r.id, userId, memory: r.memory,
      metadata: r.metadata, createdAt: new Date(),
    }));
  }

  return localStore.getAll(userId);
}

export async function forgetMemory(id: string, userId = DEFAULT_USER): Promise<void> {
  const cloud = await getCloudClient();
  if (cloud) { await cloud.delete(id); return; }
  localStore.delete(id, userId);
}

// ─── Domain-specific memory writers ──────────────────────────────────────────

export async function rememberDealSimulation(
  property: Property,
  sim: SimulationResult,
  userId = DEFAULT_USER,
): Promise<void> {
  const fact = [
    `Deal analysis for ${property.address}, ${property.city} ${property.state} ${property.zip}.`,
    `ARV: $${sim.features.arvMidpoint.toLocaleString()}.`,
    `Recommended MAO: $${sim.recommendedMao.toLocaleString()} (${sim.recommendedStrategy}).`,
    `Risk: ${(sim.riskScore * 100).toFixed(0)}%. Confidence: ${(sim.confidenceScore * 100).toFixed(0)}%.`,
    `Market: ${sim.features.marketRegime}. Exit velocity: ~${sim.base.exitDays} days.`,
    `Verdict: ${sim.riskScore < 0.5 ? 'Favorable' : sim.riskScore < 0.7 ? 'Moderate risk' : 'High risk'}.`,
  ].join(' ');

  await rememberFact(fact, userId, {
    type:        'deal_simulation',
    propertyId:  sim.propertyId,
    zip:         property.zip,
    mao:         sim.recommendedMao,
    strategy:    sim.recommendedStrategy,
    riskScore:   sim.riskScore,
  });
}

export async function rememberDealOutcome(
  outcome: DealOutcomeInput,
  property: Property,
  userId = DEFAULT_USER,
): Promise<void> {
  const fact = [
    `Deal closed: ${property.address}, ${property.zip}.`,
    `Contract: $${outcome.actualContractPrice.toLocaleString()}.`,
    `Profit: $${outcome.actualProfit.toLocaleString()}.`,
    outcome.actualDom ? `Days to close: ${outcome.actualDom}.` : '',
    `Exit: ${outcome.exitType}.`,
    outcome.actualScenario ? `Matched scenario: ${outcome.actualScenario}.` : '',
  ].filter(Boolean).join(' ');

  await rememberFact(fact, userId, {
    type:       'deal_outcome',
    dealId:     outcome.dealId,
    zip:        property.zip,
    profit:     outcome.actualProfit,
    exitType:   outcome.exitType,
  });
}

export async function rememberMarketCondition(
  zip: string,
  regime: string,
  notes: string,
  userId = DEFAULT_USER,
): Promise<void> {
  const fact = `Market condition for ZIP ${zip}: ${regime} regime. ${notes}`;
  await rememberFact(fact, userId, { type: 'market_condition', zip, regime });
}

export async function recallDealsInZip(
  zip: string,
  userId = DEFAULT_USER,
): Promise<MemorySearchResult[]> {
  return searchMemory(`deal analysis ${zip}`, userId, 10);
}

export async function recallMarketContext(
  zip: string,
  userId = DEFAULT_USER,
): Promise<MemorySearchResult[]> {
  return searchMemory(`market condition ${zip}`, userId, 5);
}

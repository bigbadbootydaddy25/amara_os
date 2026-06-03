/**
 * Deterministic text embedder for local-first operation.
 *
 * Production path: swap `embedText` to call a local Ollama embedding endpoint
 * (e.g. nomic-embed-text, all-minilm) or a sentence-transformers HTTP server.
 *
 * Current implementation: reproducible hash-based pseudo-embedding.
 * Preserves relative similarity for same-ZIP / same-type properties
 * and is fully deterministic — no external calls required.
 */

import { VECTOR_SIZE } from './qdrant-client.js';
import type { Property, SimulationResult } from '../../types.js';

// ─── Ollama embedding (used when OLLAMA_EMBED_URL is set) ───────────────────

async function ollamaEmbed(text: string): Promise<number[] | null> {
  const url = process.env.OLLAMA_EMBED_URL;
  if (!url) return null;

  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model: process.env.OLLAMA_EMBED_MODEL ?? 'nomic-embed-text', prompt: text }),
      signal: AbortSignal.timeout(5_000),
    });
    if (!res.ok) return null;
    const json = await res.json() as { embedding?: number[] };
    return json.embedding ?? null;
  } catch {
    return null;
  }
}

// ─── Deterministic fallback ──────────────────────────────────────────────────

function hashEmbed(text: string): number[] {
  const vec = new Float32Array(VECTOR_SIZE);
  let seed = 0x9e3779b9;

  for (let i = 0; i < text.length; i++) {
    seed ^= text.charCodeAt(i) + 0x9e3779b9 + (seed << 6) + (seed >>> 2);
  }

  for (let i = 0; i < VECTOR_SIZE; i++) {
    seed ^= seed << 13;
    seed ^= seed >>> 17;
    seed ^= seed << 5;
    vec[i] = ((seed >>> 0) / 0xffffffff) * 2 - 1;
  }

  // L2-normalize
  const norm = Math.sqrt(vec.reduce((s, v) => s + v * v, 0)) || 1;
  return Array.from(vec).map((v) => v / norm);
}

export async function embedText(text: string): Promise<number[]> {
  const ollama = await ollamaEmbed(text);
  if (ollama && ollama.length === VECTOR_SIZE) return ollama;
  return hashEmbed(text);
}

// ─── Domain-specific text builders ──────────────────────────────────────────

export function propertyToText(property: Property, sim?: SimulationResult): string {
  const parts: string[] = [
    `${property.address}, ${property.city}, ${property.state} ${property.zip}`,
    property.arvEstimate ? `ARV $${property.arvEstimate.toLocaleString()}` : '',
    property.askingPrice ? `asking $${property.askingPrice.toLocaleString()}` : '',
    property.rehabEstimate ? `rehab $${property.rehabEstimate.toLocaleString()}` : '',
    property.conditionGrade ? `condition grade ${property.conditionGrade}/10` : '',
    property.bedrooms ? `${property.bedrooms}bd` : '',
    property.bathrooms ? `${property.bathrooms}ba` : '',
    property.sqft ? `${property.sqft} sqft` : '',
    property.yearBuilt ? `built ${property.yearBuilt}` : '',
    property.taxDelinquent ? 'tax delinquent' : '',
    property.vacant ? 'vacant' : '',
    property.preForeclosure ? 'pre-foreclosure' : '',
    sim ? `recommended MAO $${sim.recommendedMao.toLocaleString()} strategy ${sim.recommendedStrategy}` : '',
    sim ? `risk ${(sim.riskScore * 100).toFixed(0)}%` : '',
  ];
  return parts.filter(Boolean).join(' | ');
}

export function marketIntelToText(params: {
  zip: string; metro?: string; regime: string;
  medianArv?: number; avgDom?: number; inventoryCount?: number;
  notes?: string;
}): string {
  return [
    `ZIP ${params.zip}`,
    params.metro ? `metro ${params.metro}` : '',
    `market regime ${params.regime}`,
    params.medianArv ? `median ARV $${params.medianArv.toLocaleString()}` : '',
    params.avgDom ? `avg DOM ${params.avgDom} days` : '',
    params.inventoryCount ? `${params.inventoryCount} active listings` : '',
    params.notes ?? '',
  ].filter(Boolean).join(' | ');
}

export function buyerSignalToText(params: {
  name: string; buyerType?: string; targetZips?: string[];
  minPrice?: number; maxPrice?: number; notes?: string;
}): string {
  return [
    params.name,
    params.buyerType ? `buyer type ${params.buyerType}` : '',
    params.targetZips?.length ? `active in ${params.targetZips.join(' ')}` : '',
    params.minPrice ? `min $${params.minPrice.toLocaleString()}` : '',
    params.maxPrice ? `max $${params.maxPrice.toLocaleString()}` : '',
    params.notes ?? '',
  ].filter(Boolean).join(' | ');
}

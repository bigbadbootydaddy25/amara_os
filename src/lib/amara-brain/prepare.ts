/**
 * prepare.ts — SACRED DATA PIPELINE
 *
 * This file is NEVER auto-edited by the self-improvement engine.
 * It is the stable foundation: all data ingestion, Neo4j writes,
 * file parsing, and import handling.
 *
 * Think of this as Karpathy's prepare.py — fixed, trusted, never touched by agents.
 */

export { ingestBuyers } from '@/lib/neural-graph/ingest-buyers';
export { ingestDeals } from '@/lib/neural-graph/ingest-deals';
export { ingestSignals } from '@/lib/neural-graph/ingest-signals';
export { buildRelationships } from '@/lib/neural-graph/build-relationships';
export { runQuery, verifyConnectivity } from '@/lib/neural-graph/neo4j-client';
export { runFullDataPull } from '@/lib/openclaw/data-puller';
export { importMiroFishScores } from '@/lib/mirofish/score-importer';
export { watchAndIngest } from '@/lib/knowledge/notebooklm-watcher';
export { syncLlmWiki } from '@/lib/knowledge/llm-wiki-sync';

import type { IngestionSource } from '../../types.js';
import { getPool } from './pool.js';

export interface IngestionLogEntry {
  source: IngestionSource;
  recordType: 'property' | 'deal' | 'market' | 'buyer';
  recordId?: string;
  status: 'success' | 'error' | 'skipped';
  rawInput?: Record<string, unknown>;
  errorMessage?: string;
  processingMs?: number;
}

export const IngestionLogRepo = {
  async log(entry: IngestionLogEntry): Promise<void> {
    await getPool().query(
      `INSERT INTO ingestion_log
         (source, record_type, record_id, status, raw_input, error_message, processing_ms)
       VALUES ($1,$2,$3,$4,$5,$6,$7)`,
      [
        entry.source,
        entry.recordType,
        entry.recordId ?? null,
        entry.status,
        entry.rawInput ? JSON.stringify(entry.rawInput) : null,
        entry.errorMessage ?? null,
        entry.processingMs ?? null,
      ],
    );
  },

  async getRecent(limit = 100): Promise<IngestionLogEntry[]> {
    const result = await getPool().query(
      `SELECT * FROM ingestion_log ORDER BY created_at DESC LIMIT $1`,
      [limit],
    );
    return result.rows.map((r) => ({
      source:       r.source as IngestionSource,
      recordType:   r.record_type,
      recordId:     r.record_id ?? undefined,
      status:       r.status,
      rawInput:     r.raw_input ?? undefined,
      errorMessage: r.error_message ?? undefined,
      processingMs: r.processing_ms ?? undefined,
    }));
  },
};

import { stringify } from 'csv-stringify/sync';
import type { InstrumentRow } from '../types/index.js';

const COLUMNS = [
  'sequence_no',
  'recording_date',
  'execution_date',
  'instrument_type',
  'grantors',
  'grantees',
  'volume',
  'page',
  'instrument_number',
  'legal_description',
  'net_mineral_acres',
  'royalty_reserved',
  'notes',
  'confidence',
] as const;

export function buildRunsheetCsv(
  instruments: Array<InstrumentRow & { sequence_no: number }>,
): Buffer {
  const rows = instruments.map((row) => ({
    sequence_no: row.sequence_no,
    recording_date: row.recording_date ?? '',
    execution_date: row.execution_date ?? '',
    instrument_type: row.instrument_type ?? '',
    grantors: row.grantors.join('; '),
    grantees: row.grantees.join('; '),
    volume: row.volume ?? '',
    page: row.page ?? '',
    instrument_number: row.instrument_number ?? '',
    legal_description: row.legal_description ?? '',
    net_mineral_acres: row.net_mineral_acres ?? '',
    royalty_reserved: row.royalty_reserved ?? '',
    notes: row.notes ?? '',
    confidence: row.confidence ?? '',
  }));

  const csv = stringify(rows, { header: true, columns: COLUMNS as unknown as string[] });
  return Buffer.from(csv, 'utf8');
}

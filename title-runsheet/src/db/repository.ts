import { query, queryOne } from './client.js';
import type {
  CurativeItemRow,
  DocumentRow,
  DocumentSource,
  InstrumentRow,
  PortalSearchResultRow,
  Project,
  RunsheetEntryRow,
} from '../types/index.js';

// ---------------------------------------------------------------------------
// Projects
// ---------------------------------------------------------------------------

export async function getProject(id: string): Promise<Project | undefined> {
  return queryOne<Project>('select * from projects where id = $1', [id]);
}

export async function listProjects(): Promise<Project[]> {
  return query<Project>('select * from projects order by created_at desc');
}

export async function setProjectStatus(id: string, status: Project['status']): Promise<void> {
  await query('update projects set status = $2, updated_at = now() where id = $1', [id, status]);
}

// ---------------------------------------------------------------------------
// Documents
// ---------------------------------------------------------------------------

export async function upsertDocument(input: {
  projectId: string;
  source: DocumentSource;
  dropboxPath: string;
  dropboxRev?: string | null;
  fileName: string;
  contentHash?: string | null;
  mimeType?: string | null;
}): Promise<DocumentRow> {
  const row = await queryOne<DocumentRow>(
    `insert into documents (project_id, source, dropbox_path, dropbox_rev, file_name, content_hash, mime_type)
     values ($1, $2, $3, $4, $5, $6, $7)
     on conflict (project_id, dropbox_path)
     do update set dropbox_rev = excluded.dropbox_rev,
                   content_hash = excluded.content_hash,
                   mime_type = excluded.mime_type,
                   updated_at = now()
     returning *`,
    [input.projectId, input.source, input.dropboxPath, input.dropboxRev ?? null, input.fileName,
      input.contentHash ?? null, input.mimeType ?? null],
  );
  if (!row) throw new Error(`Failed to upsert document ${input.dropboxPath}`);
  return row;
}

export async function listDocuments(projectId: string, status?: DocumentRow['status']): Promise<DocumentRow[]> {
  if (status) {
    return query<DocumentRow>('select * from documents where project_id = $1 and status = $2 order by created_at', [
      projectId,
      status,
    ]);
  }
  return query<DocumentRow>('select * from documents where project_id = $1 order by created_at', [projectId]);
}

export async function setDocumentStatus(
  id: string,
  status: DocumentRow['status'],
  errorMessage?: string | null,
): Promise<void> {
  await query('update documents set status = $2, error_message = $3, updated_at = now() where id = $1', [
    id,
    status,
    errorMessage ?? null,
  ]);
}

export async function setDocumentOcrText(id: string, ocrText: string): Promise<void> {
  await query('update documents set ocr_text = $2, updated_at = now() where id = $1', [id, ocrText]);
}

// ---------------------------------------------------------------------------
// Instruments
// ---------------------------------------------------------------------------

export async function insertInstrument(row: Partial<InstrumentRow> & { project_id: string }): Promise<InstrumentRow> {
  const result = await queryOne<InstrumentRow>(
    `insert into instruments (
       project_id, document_id, instrument_type, grantors, grantees, execution_date,
       recording_date, county, state, volume, page, instrument_number, legal_description,
       net_mineral_acres, royalty_reserved, notes, raw_extraction, confidence
     ) values ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18)
     returning *`,
    [
      row.project_id,
      row.document_id ?? null,
      row.instrument_type ?? null,
      row.grantors ?? [],
      row.grantees ?? [],
      row.execution_date ?? null,
      row.recording_date ?? null,
      row.county ?? null,
      row.state ?? 'TX',
      row.volume ?? null,
      row.page ?? null,
      row.instrument_number ?? null,
      row.legal_description ?? null,
      row.net_mineral_acres ?? null,
      row.royalty_reserved ?? null,
      row.notes ?? null,
      JSON.stringify(row.raw_extraction ?? {}),
      row.confidence ?? null,
    ],
  );
  if (!result) throw new Error('Failed to insert instrument');
  return result;
}

export async function listInstruments(projectId: string): Promise<InstrumentRow[]> {
  return query<InstrumentRow>(
    `select * from instruments where project_id = $1
     order by recording_date nulls last, execution_date nulls last, created_at`,
    [projectId],
  );
}

// ---------------------------------------------------------------------------
// Runsheet entries
// ---------------------------------------------------------------------------

export async function replaceRunsheetEntries(
  projectId: string,
  entries: Array<{ instrumentId: string; sequenceNo: number; summary: string }>,
): Promise<void> {
  await query('delete from runsheet_entries where project_id = $1', [projectId]);
  for (const entry of entries) {
    await query(
      `insert into runsheet_entries (project_id, instrument_id, sequence_no, entry_summary)
       values ($1, $2, $3, $4)`,
      [projectId, entry.instrumentId, entry.sequenceNo, entry.summary],
    );
  }
}

export async function listRunsheetEntries(projectId: string): Promise<RunsheetEntryRow[]> {
  return query<RunsheetEntryRow>(
    'select * from runsheet_entries where project_id = $1 order by sequence_no',
    [projectId],
  );
}

// ---------------------------------------------------------------------------
// Curative items
// ---------------------------------------------------------------------------

export async function insertCurativeItem(
  item: Omit<CurativeItemRow, 'id' | 'status'> & { status?: CurativeItemRow['status'] },
): Promise<CurativeItemRow> {
  const result = await queryOne<CurativeItemRow>(
    `insert into curative_items (project_id, instrument_id, severity, category, description, status)
     values ($1,$2,$3,$4,$5,$6)
     returning *`,
    [item.project_id, item.instrument_id, item.severity, item.category, item.description, item.status ?? 'open'],
  );
  if (!result) throw new Error('Failed to insert curative item');
  return result;
}

export async function listCurativeItems(projectId: string): Promise<CurativeItemRow[]> {
  return query<CurativeItemRow>(
    `select * from curative_items where project_id = $1
     order by (case severity when 'critical' then 0 when 'warning' then 1 else 2 end), created_at`,
    [projectId],
  );
}

// ---------------------------------------------------------------------------
// Portal search results
// ---------------------------------------------------------------------------

export async function insertPortalSearchResult(
  row: Omit<PortalSearchResultRow, 'id'>,
): Promise<PortalSearchResultRow> {
  const result = await queryOne<PortalSearchResultRow>(
    `insert into portal_search_results (
       project_id, portal, instrument_number, instrument_type, recording_date,
       grantor, grantee, download_status, dropbox_path, error_message
     ) values ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
     returning *`,
    [
      row.project_id,
      row.portal,
      row.instrument_number,
      row.instrument_type,
      row.recording_date,
      row.grantor,
      row.grantee,
      row.download_status,
      row.dropbox_path,
      row.error_message,
    ],
  );
  if (!result) throw new Error('Failed to insert portal search result');
  return result;
}

export async function listPortalSearchResults(projectId: string): Promise<PortalSearchResultRow[]> {
  return query<PortalSearchResultRow>('select * from portal_search_results where project_id = $1 order by created_at', [
    projectId,
  ]);
}

// ---------------------------------------------------------------------------
// Agent runs (audit log)
// ---------------------------------------------------------------------------

export async function startAgentRun(projectId: string, agentName: string): Promise<string> {
  const row = await queryOne<{ id: string }>(
    `insert into agent_runs (project_id, agent_name, status) values ($1, $2, 'running') returning id`,
    [projectId, agentName],
  );
  if (!row) throw new Error('Failed to start agent run');
  return row.id;
}

export async function finishAgentRun(
  runId: string,
  status: 'succeeded' | 'failed',
  summary?: string,
  errorMessage?: string,
  metadata?: Record<string, unknown>,
): Promise<void> {
  await query(
    `update agent_runs set status = $2, finished_at = now(), summary = $3, error_message = $4, metadata = $5
     where id = $1`,
    [runId, status, summary ?? null, errorMessage ?? null, JSON.stringify(metadata ?? {})],
  );
}

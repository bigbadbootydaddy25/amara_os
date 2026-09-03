export type ProjectStatus =
  | 'new'
  | 'intake'
  | 'retrieving'
  | 'abstracting'
  | 'curative'
  | 'exporting'
  | 'complete'
  | 'error';

export interface Project {
  id: string;
  name: string;
  state: string;
  county: string;
  survey_section: string | null;
  survey_block: string | null;
  survey_township: string | null;
  survey_abstract_no: string | null;
  legal_description: string | null;
  dropbox_seller_package_path: string;
  dropbox_recorded_instruments_path: string;
  dropbox_runsheet_export_path: string | null;
  dropbox_report_export_path: string | null;
  status: ProjectStatus;
  created_at: string;
  updated_at: string;
}

export type DocumentSource = 'seller_package' | 'recorded_instrument' | 'portal_download';
export type DocumentStatus = 'new' | 'processing' | 'processed' | 'error' | 'skipped';

export interface DocumentRow {
  id: string;
  project_id: string;
  source: DocumentSource;
  dropbox_path: string;
  dropbox_rev: string | null;
  file_name: string;
  content_hash: string | null;
  mime_type: string | null;
  ocr_text: string | null;
  status: DocumentStatus;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface InstrumentRow {
  id: string;
  project_id: string;
  document_id: string | null;
  instrument_type: string | null;
  grantors: string[];
  grantees: string[];
  execution_date: string | null;
  recording_date: string | null;
  county: string | null;
  state: string | null;
  volume: string | null;
  page: string | null;
  instrument_number: string | null;
  legal_description: string | null;
  net_mineral_acres: number | null;
  royalty_reserved: string | null;
  notes: string | null;
  raw_extraction: Record<string, unknown>;
  confidence: number | null;
  created_at: string;
  updated_at: string;
}

export interface RunsheetEntryRow {
  id: string;
  project_id: string;
  instrument_id: string;
  sequence_no: number;
  entry_summary: string | null;
}

export type CurativeSeverity = 'info' | 'warning' | 'critical';
export type CurativeStatus = 'open' | 'resolved' | 'waived';

export interface CurativeItemRow {
  id: string;
  project_id: string;
  instrument_id: string | null;
  severity: CurativeSeverity;
  category: string;
  description: string;
  status: CurativeStatus;
}

export interface PortalSearchResultRow {
  id: string;
  project_id: string;
  portal: string;
  instrument_number: string | null;
  instrument_type: string | null;
  recording_date: string | null;
  grantor: string | null;
  grantee: string | null;
  download_status: 'pending' | 'downloaded' | 'failed' | 'skipped';
  dropbox_path: string | null;
  error_message: string | null;
}

export type AgentName =
  | 'intake'
  | 'instrument_retrieval'
  | 'abstracting'
  | 'curative_qc'
  | 'runsheet_export'
  | 'report';

export interface AgentContext {
  project: Project;
}

export interface AgentResult {
  agentName: AgentName;
  summary: string;
  metadata?: Record<string, unknown>;
}

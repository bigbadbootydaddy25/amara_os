// ── Well ─────────────────────────────────────────────────────────────────────

export type WellStatus        = 'Active' | 'Shut-In' | 'DUC' | 'P&A' | 'Permit';
export type ProductionStatus  = 'Producing' | 'Shut-In' | 'Not Yet Producing' | 'DUC';
export type NptRisk           = 'Low' | 'Medium' | 'High' | 'Critical';
export type LeaseStatus       = 'HBP' | 'Active' | 'Expiring <60d' | 'Expiring <30d' | 'Expired';

export interface WellPad {
  id:               string;    // W01 … W30
  apiNumber:        string;    // 42-XXX-XXXXX-0000
  name:             string;
  operator:         string;
  county:           string;
  basin:            string;
  wellStatus:       WellStatus;
  productionStatus: ProductionStatus;
  nptRisk:          NptRisk;
  leaseStatus:      LeaseStatus;
  titleFlags:       string[];
  curativeFlags:    string[];
  lastUpdated:      string;    // ISO timestamp
  // SVG position
  x: number;
  y: number;
}

// ── Layers ───────────────────────────────────────────────────────────────────

export type LayerKey =
  | 'wells'
  | 'leases'
  | 'units'
  | 'pipelines'
  | 'producing'
  | 'shutIn'
  | 'duc'
  | 'titleRisk'
  | 'curativeNeeded'
  | 'nptAlerts';

export type LayerState = Record<LayerKey, boolean>;

// ── Energy Agents ─────────────────────────────────────────────────────────────

export type AgentStatus = 'idle' | 'scanning' | 'analyzing' | 'flagged' | 'critical';

export interface EnergyAgent {
  id:       string;
  name:     string;
  role:     string;
  status:   AgentStatus;
  finding:  string;
  findingTs: number;  // timestamp ms
}

// ── Data mode ────────────────────────────────────────────────────────────────

export type DataMode = 'DEMO' | 'LIVE';

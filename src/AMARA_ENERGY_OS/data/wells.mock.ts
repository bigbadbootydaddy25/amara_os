import type { WellPad } from '../types';

// All coordinates reference the SVG viewBox "0 0 900 640"
export const MOCK_WELLS: WellPad[] = [
  // ── Permian Basin ─────────────────────────────────────────────────────────
  {
    id: 'W01', apiNumber: '42-317-25891-0000', name: 'Clearwater 1H',
    operator: 'Pioneer Natural Resources', county: 'Midland', basin: 'Permian Basin',
    wellStatus: 'Active', productionStatus: 'Producing', nptRisk: 'High',
    leaseStatus: 'HBP', titleFlags: ['Gap in chain — Lot 4 Sec 22'], curativeFlags: ['Missing affidavit'],
    lastUpdated: '2026-05-18T14:32:00Z', x: 138, y: 258,
  },
  {
    id: 'W02', apiNumber: '42-317-25892-0000', name: 'Clearwater 2H',
    operator: 'Pioneer Natural Resources', county: 'Midland', basin: 'Permian Basin',
    wellStatus: 'Active', productionStatus: 'Producing', nptRisk: 'Low',
    leaseStatus: 'HBP', titleFlags: [], curativeFlags: [],
    lastUpdated: '2026-05-18T14:32:00Z', x: 162, y: 298,
  },
  {
    id: 'W03', apiNumber: '42-135-20541-0000', name: 'Ector North 1H',
    operator: 'Diamondback Energy', county: 'Ector', basin: 'Permian Basin',
    wellStatus: 'Active', productionStatus: 'Producing', nptRisk: 'Critical',
    leaseStatus: 'HBP', titleFlags: ['Adverse claim — surface/mineral split'], curativeFlags: ['Court order required', 'Missing mineral deed'],
    lastUpdated: '2026-05-19T09:12:00Z', x: 182, y: 332,
  },
  {
    id: 'W04', apiNumber: '42-003-18801-0000', name: 'Andrews Deep 1H',
    operator: 'ConocoPhillips', county: 'Andrews', basin: 'Permian Basin',
    wellStatus: 'Shut-In', productionStatus: 'Shut-In', nptRisk: 'Medium',
    leaseStatus: 'Active', titleFlags: [], curativeFlags: ['Partial interest unresolved'],
    lastUpdated: '2026-05-17T16:00:00Z', x: 158, y: 368,
  },
  {
    id: 'W05', apiNumber: '42-003-18902-0000', name: 'Andrews Deep 2H',
    operator: 'ConocoPhillips', county: 'Andrews', basin: 'Permian Basin',
    wellStatus: 'Active', productionStatus: 'Producing', nptRisk: 'High',
    leaseStatus: 'Expiring <60d', titleFlags: ['HBP calculation in dispute'], curativeFlags: [],
    lastUpdated: '2026-05-19T06:45:00Z', x: 192, y: 395,
  },
  {
    id: 'W06', apiNumber: '42-329-41201-0000', name: 'Martin Unit 1H',
    operator: 'Coterra Energy', county: 'Martin', basin: 'Permian Basin',
    wellStatus: 'Active', productionStatus: 'Producing', nptRisk: 'Low',
    leaseStatus: 'HBP', titleFlags: [], curativeFlags: [],
    lastUpdated: '2026-05-18T11:20:00Z', x: 218, y: 362,
  },
  {
    id: 'W07', apiNumber: '42-329-41305-0000', name: 'Martin Unit 2H',
    operator: 'Coterra Energy', county: 'Martin', basin: 'Permian Basin',
    wellStatus: 'DUC', productionStatus: 'DUC', nptRisk: 'Low',
    leaseStatus: 'Active', titleFlags: [], curativeFlags: [],
    lastUpdated: '2026-05-15T08:00:00Z', x: 205, y: 428,
  },
  {
    id: 'W08', apiNumber: '42-475-38801-0000', name: 'Ward Central 1H',
    operator: 'Occidental Petroleum', county: 'Ward', basin: 'Permian Basin',
    wellStatus: 'Active', productionStatus: 'Producing', nptRisk: 'Critical',
    leaseStatus: 'HBP', titleFlags: ['Orphan mineral interest — heirs unknown'], curativeFlags: ['Probate search required', 'Publication notice needed'],
    lastUpdated: '2026-05-19T11:55:00Z', x: 232, y: 408,
  },
  {
    id: 'W09', apiNumber: '42-495-29901-0000', name: 'Winkler 1H',
    operator: 'EOG Resources', county: 'Winkler', basin: 'Permian Basin',
    wellStatus: 'Active', productionStatus: 'Producing', nptRisk: 'Medium',
    leaseStatus: 'Active', titleFlags: [], curativeFlags: ['Easement conflict pending'],
    lastUpdated: '2026-05-18T13:10:00Z', x: 248, y: 375,
  },
  {
    id: 'W10', apiNumber: '42-495-29902-0000', name: 'Winkler 2H',
    operator: 'EOG Resources', county: 'Winkler', basin: 'Permian Basin',
    wellStatus: 'Shut-In', productionStatus: 'Shut-In', nptRisk: 'Medium',
    leaseStatus: 'Expiring <30d', titleFlags: [], curativeFlags: [],
    lastUpdated: '2026-05-19T07:22:00Z', x: 268, y: 342,
  },

  // ── Delaware Basin ────────────────────────────────────────────────────────
  {
    id: 'W11', apiNumber: '42-389-11201-0000', name: 'Reeves State 1H',
    operator: 'Matador Resources', county: 'Reeves', basin: 'Delaware Basin',
    wellStatus: 'Active', productionStatus: 'Producing', nptRisk: 'High',
    leaseStatus: 'HBP', titleFlags: ['State lease — split estate flag'], curativeFlags: ['GLO confirmation pending'],
    lastUpdated: '2026-05-19T10:30:00Z', x: 285, y: 295,
  },
  {
    id: 'W12', apiNumber: '42-389-11302-0000', name: 'Reeves State 2H',
    operator: 'Matador Resources', county: 'Reeves', basin: 'Delaware Basin',
    wellStatus: 'Active', productionStatus: 'Producing', nptRisk: 'Medium',
    leaseStatus: 'HBP', titleFlags: [], curativeFlags: [],
    lastUpdated: '2026-05-18T17:45:00Z', x: 308, y: 328,
  },
  {
    id: 'W13', apiNumber: '42-103-08801-0000', name: 'Culberson Deep 1H',
    operator: 'Devon Energy', county: 'Culberson', basin: 'Delaware Basin',
    wellStatus: 'Active', productionStatus: 'Producing', nptRisk: 'Critical',
    leaseStatus: 'HBP', titleFlags: ['Boundary dispute — resurvey needed', 'Undivided interest conflict'], curativeFlags: ['Boundary survey required', 'Partition action pending'],
    lastUpdated: '2026-05-19T12:10:00Z', x: 325, y: 362,
  },
  {
    id: 'W14', apiNumber: '42-301-19901-0000', name: 'Loving Unit 1H',
    operator: 'Ovintiv', county: 'Loving', basin: 'Delaware Basin',
    wellStatus: 'Active', productionStatus: 'Producing', nptRisk: 'Low',
    leaseStatus: 'Active', titleFlags: [], curativeFlags: [],
    lastUpdated: '2026-05-17T09:00:00Z', x: 342, y: 395,
  },
  {
    id: 'W15', apiNumber: '42-301-19902-0000', name: 'Loving Unit 2H',
    operator: 'Ovintiv', county: 'Loving', basin: 'Delaware Basin',
    wellStatus: 'DUC', productionStatus: 'DUC', nptRisk: 'Low',
    leaseStatus: 'Active', titleFlags: [], curativeFlags: [],
    lastUpdated: '2026-05-14T08:00:00Z', x: 318, y: 422,
  },

  // ── Central Texas ─────────────────────────────────────────────────────────
  {
    id: 'W16', apiNumber: '42-227-33401-0000', name: 'Howard Central 1H',
    operator: 'SM Energy', county: 'Howard', basin: 'Central Basin Platform',
    wellStatus: 'Active', productionStatus: 'Producing', nptRisk: 'Low',
    leaseStatus: 'HBP', titleFlags: [], curativeFlags: [],
    lastUpdated: '2026-05-18T10:00:00Z', x: 438, y: 348,
  },
  {
    id: 'W17', apiNumber: '42-227-33502-0000', name: 'Howard Central 2H',
    operator: 'SM Energy', county: 'Howard', basin: 'Central Basin Platform',
    wellStatus: 'Shut-In', productionStatus: 'Shut-In', nptRisk: 'Medium',
    leaseStatus: 'Expiring <60d', titleFlags: [], curativeFlags: ['Operating agreement review needed'],
    lastUpdated: '2026-05-16T14:20:00Z', x: 462, y: 382,
  },
  {
    id: 'W18', apiNumber: '42-263-44201-0000', name: 'Kimble Deep 1H',
    operator: 'ConocoPhillips', county: 'Kimble', basin: 'Central Basin Platform',
    wellStatus: 'Active', productionStatus: 'Producing', nptRisk: 'High',
    leaseStatus: 'Active', titleFlags: ['Mineral deed defect — acknowledgment missing'],
    curativeFlags: ['Re-execution required'],
    lastUpdated: '2026-05-19T08:55:00Z', x: 492, y: 415,
  },

  // ── Eagle Ford ────────────────────────────────────────────────────────────
  {
    id: 'W19', apiNumber: '42-479-58801-0000', name: 'Webb Shale 1H',
    operator: 'EOG Resources', county: 'Webb', basin: 'Eagle Ford',
    wellStatus: 'Active', productionStatus: 'Producing', nptRisk: 'Low',
    leaseStatus: 'HBP', titleFlags: [], curativeFlags: [],
    lastUpdated: '2026-05-18T09:30:00Z', x: 405, y: 482,
  },
  {
    id: 'W20', apiNumber: '42-479-58802-0000', name: 'Webb Shale 2H',
    operator: 'EOG Resources', county: 'Webb', basin: 'Eagle Ford',
    wellStatus: 'Active', productionStatus: 'Producing', nptRisk: 'Low',
    leaseStatus: 'HBP', titleFlags: [], curativeFlags: [],
    lastUpdated: '2026-05-18T09:30:00Z', x: 438, y: 498,
  },
  {
    id: 'W21', apiNumber: '42-271-62201-0000', name: 'LaSalle Unit 1H',
    operator: 'Chesapeake Energy', county: 'LaSalle', basin: 'Eagle Ford',
    wellStatus: 'Active', productionStatus: 'Producing', nptRisk: 'Critical',
    leaseStatus: 'Expiring <30d', titleFlags: ['Lease extension option — notice deadline 14 days'],
    curativeFlags: ['Execute extension amendment immediately'],
    lastUpdated: '2026-05-19T13:00:00Z', x: 472, y: 485,
  },
  {
    id: 'W22', apiNumber: '42-163-44801-0000', name: 'Frio South 1H',
    operator: 'Chesapeake Energy', county: 'Frio', basin: 'Eagle Ford',
    wellStatus: 'Shut-In', productionStatus: 'Shut-In', nptRisk: 'Medium',
    leaseStatus: 'Active', titleFlags: [], curativeFlags: [],
    lastUpdated: '2026-05-15T11:00:00Z', x: 505, y: 498,
  },

  // ── Fort Worth / Barnett ──────────────────────────────────────────────────
  {
    id: 'W23', apiNumber: '42-439-78801-0000', name: 'Tarrant Urban 1V',
    operator: 'Coterra Energy', county: 'Tarrant', basin: 'Barnett Shale',
    wellStatus: 'Active', productionStatus: 'Producing', nptRisk: 'Medium',
    leaseStatus: 'HBP', titleFlags: [], curativeFlags: [],
    lastUpdated: '2026-05-18T15:45:00Z', x: 568, y: 192,
  },
  {
    id: 'W24', apiNumber: '42-439-78902-0000', name: 'Tarrant Urban 2V',
    operator: 'Coterra Energy', county: 'Tarrant', basin: 'Barnett Shale',
    wellStatus: 'Active', productionStatus: 'Producing', nptRisk: 'High',
    leaseStatus: 'HBP', titleFlags: ['Urban mineral lease — pooling clause conflict'],
    curativeFlags: ['Pooling agreement amendment needed'],
    lastUpdated: '2026-05-19T10:00:00Z', x: 598, y: 218,
  },
  {
    id: 'W25', apiNumber: '42-367-51201-0000', name: 'Parker East 1H',
    operator: 'Diamondback Energy', county: 'Parker', basin: 'Barnett Shale',
    wellStatus: 'DUC', productionStatus: 'DUC', nptRisk: 'Low',
    leaseStatus: 'Active', titleFlags: [], curativeFlags: [],
    lastUpdated: '2026-05-12T08:00:00Z', x: 625, y: 202,
  },
  {
    id: 'W26', apiNumber: '42-497-22201-0000', name: 'Wise Basin 1H',
    operator: 'Pioneer Natural Resources', county: 'Wise', basin: 'Barnett Shale',
    wellStatus: 'Active', productionStatus: 'Producing', nptRisk: 'Low',
    leaseStatus: 'HBP', titleFlags: [], curativeFlags: [],
    lastUpdated: '2026-05-18T12:30:00Z', x: 648, y: 238,
  },
  {
    id: 'W27', apiNumber: '42-497-22302-0000', name: 'Wise Basin 2H',
    operator: 'Pioneer Natural Resources', county: 'Wise', basin: 'Barnett Shale',
    wellStatus: 'Shut-In', productionStatus: 'Shut-In', nptRisk: 'Medium',
    leaseStatus: 'Expiring <60d', titleFlags: [], curativeFlags: [],
    lastUpdated: '2026-05-17T10:00:00Z', x: 618, y: 255,
  },

  // ── East Texas ────────────────────────────────────────────────────────────
  {
    id: 'W28', apiNumber: '42-365-88801-0000', name: 'Panola Forest 1V',
    operator: 'Devon Energy', county: 'Panola', basin: 'East Texas Basin',
    wellStatus: 'Active', productionStatus: 'Producing', nptRisk: 'Low',
    leaseStatus: 'HBP', titleFlags: [], curativeFlags: [],
    lastUpdated: '2026-05-18T08:00:00Z', x: 668, y: 308,
  },
  {
    id: 'W29', apiNumber: '42-203-66501-0000', name: 'Harrison Deep 1V',
    operator: 'Occidental Petroleum', county: 'Harrison', basin: 'East Texas Basin',
    wellStatus: 'Active', productionStatus: 'Producing', nptRisk: 'Low',
    leaseStatus: 'HBP', titleFlags: [], curativeFlags: [],
    lastUpdated: '2026-05-18T08:00:00Z', x: 695, y: 342,
  },
  {
    id: 'W30', apiNumber: '42-401-77201-0000', name: 'Rusk Haynesville 1H',
    operator: 'Ovintiv', county: 'Rusk', basin: 'East Texas Basin',
    wellStatus: 'Shut-In', productionStatus: 'Shut-In', nptRisk: 'Medium',
    leaseStatus: 'Active', titleFlags: [], curativeFlags: [],
    lastUpdated: '2026-05-16T10:00:00Z', x: 718, y: 312,
  },
];

// Mock pipeline routes (SVG path strings, viewBox 0 0 900 640)
export const MOCK_PIPELINES: { d: string; label: string }[] = [
  { d: 'M 155,310 L 195,390 L 255,420', label: 'Permian Crude Gathering' },
  { d: 'M 290,295 L 370,250 L 460,220', label: 'Midland Basin Transport' },
  { d: 'M 568,192 L 610,218 L 652,240', label: 'Fort Worth Gas Gathering' },
  { d: 'M 405,482 L 460,488 L 505,496', label: 'Eagle Ford Condensate Line' },
  { d: 'M 668,308 L 695,340 L 720,312', label: 'East Texas Gas Transmission' },
];

// Mock lease boundaries (polygon points strings, SVG)
export const MOCK_LEASES: { points: string; id: string; label: string }[] = [
  { id: 'L1', points: '128,245 222,245 242,358 195,430 128,382', label: 'Permian Block A' },
  { id: 'L2', points: '268,278 360,278 375,412 312,462 265,412', label: 'Delaware Block B' },
  { id: 'L3', points: '550,178 660,178 678,268 595,282 542,242', label: 'Barnett Unit C' },
];

// Mock unit boundaries (polygon points strings, SVG)
export const MOCK_UNITS: { points: string; id: string; label: string }[] = [
  { id: 'U1', points: '138,298 228,298 245,392 198,432 138,408', label: 'Midland Unit 7' },
  { id: 'U2', points: '278,288 355,288 368,405 308,455 272,405', label: 'Delaware Unit 3' },
];

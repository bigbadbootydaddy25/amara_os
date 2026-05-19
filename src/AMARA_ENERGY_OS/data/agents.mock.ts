import type { EnergyAgent } from '../types';

export const INITIAL_AGENTS: EnergyAgent[] = [
  {
    id: 'title',
    name: 'Title Agent',
    role: 'Mineral title chain integrity & curative gap detection',
    status: 'idle',
    finding: 'Monitoring 30 active APIs — no new gaps detected',
    findingTs: Date.now() - 120000,
  },
  {
    id: 'lease',
    name: 'Lease Agent',
    role: 'Lease status tracking, HBP verification & expiration alerts',
    status: 'idle',
    finding: '3 leases expiring within 60 days — review recommended',
    findingTs: Date.now() - 240000,
  },
  {
    id: 'gis',
    name: 'GIS Agent',
    role: 'Spatial analysis, unit boundaries & pipeline conflict detection',
    status: 'idle',
    finding: 'Basin boundary index current — no spatial conflicts',
    findingTs: Date.now() - 90000,
  },
  {
    id: 'production',
    name: 'Production Agent',
    role: 'Production metrics, NPT event monitoring & decline analysis',
    status: 'idle',
    finding: 'Monitoring 22 producing wells — 2 NPT events active',
    findingTs: Date.now() - 60000,
  },
  {
    id: 'curative',
    name: 'Curative Agent',
    role: 'Curative action tracking, court filings & affidavit pipeline',
    status: 'idle',
    finding: '7 open curative items — 2 require immediate action',
    findingTs: Date.now() - 300000,
  },
  {
    id: 'mirofish',
    name: 'MiroFish Simulator',
    role: 'Production decline modeling, reserve estimation & scenario analysis',
    status: 'idle',
    finding: 'Last simulation run: 45-day type-curve update complete',
    findingTs: Date.now() - 600000,
  },
];

// Findings pool per agent — all energy-domain, no real estate terms
export const AGENT_FINDINGS: Record<string, string[]> = {
  title: [
    '[DEMO] Gap detected in chain — Lot 4, Sec 22, Block A, Midland County',
    '[DEMO] Orphan interest identified: W08 — heir research required',
    '[DEMO] Adverse claim flag: W13 — resurvey may redefine boundary',
    '[DEMO] Mineral deed defect resolved: W18 — re-execution confirmed',
    '[DEMO] VERIFIED: Clean title chain on W14, W15, W20 cluster',
  ],
  lease: [
    '[DEMO] ALERT: W21 (LaSalle Unit 1H) lease option deadline in 14 days',
    '[DEMO] W10 (Winkler 2H) lease expiring in 28 days — HBP risk if shut-in',
    '[DEMO] W05 (Andrews Deep 2H) HBP calculation in dispute — production log needed',
    '[DEMO] Extension executed: W22 (Frio South) renewed 3-year term',
    '[DEMO] VERIFIED: HBP confirmed on 18 of 22 producing wells — current',
  ],
  gis: [
    '[DEMO] Pipeline conflict detected: proposed route crosses Unit U-2 boundary',
    '[DEMO] Delaware Basin unit boundary update: resurvey adds 240 net acres',
    '[DEMO] GIS layer refresh: Eagle Ford formation top — 4 well adjustments',
    '[DEMO] Spatial overlap: Lease L1 intersects state acreage — GLO notice issued',
    '[DEMO] VERIFIED: All unit polygon coordinates validated against GLO data',
  ],
  production: [
    '[DEMO] NPT EVENT: W03 (Ector North) — mechanical failure, estimating 8-day downtime',
    '[DEMO] W08 (Ward Central) production rate declined 14% MoM — decline curve review',
    '[DEMO] W17 (Howard Central 2H) shut-in extended — equipment procurement delayed',
    '[DEMO] Gas-oil ratio anomaly: W24 (Tarrant Urban 2V) — formation water entry suspected',
    '[DEMO] VERIFIED: W01, W06, W09 production rates within 2% of type curve forecast',
  ],
  curative: [
    '[DEMO] Affidavit of heirship prepared: W08 — filing with Winkler County clerk',
    '[DEMO] Probate search initiated: Ward County estate — estimated 45-day timeline',
    '[DEMO] Court order obtained: W03 boundary clarification — curative complete',
    '[DEMO] Publication notice drafted for W08 orphan interest — 30-day notice period',
    '[DEMO] VERIFIED: 3 curative items closed this week — mineral interest cleared',
  ],
  mirofish: [
    '[DEMO] Decline curve updated: Permian cluster — 8.2% annual decline rate',
    '[DEMO] Reserve estimate revised: Delaware Block B — EUR +12% on new log data',
    '[DEMO] NPT impact model: W03 downtime reduces Q2 production 340 BOE net',
    '[DEMO] Type-curve scenario: Eagle Ford refrac candidate W19 — 180% IP uplift projected',
    '[DEMO] VERIFIED: 45-day production forecast matches actuals within 3.8% variance',
  ],
};

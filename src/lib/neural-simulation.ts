import { useNeuralStore, type AgentState } from '@/stores/neural-store';

const MOCK_FINDINGS: Record<string, string[]> = {
  recon: [
    '[VISUAL MOCK] APN 162-04-111-001 — owner of record: Bellagio Holdings LLC',
    '[VISUAL MOCK] Permit #2024-8821 expired — no Certificate of Occupancy issued',
    '[VISUAL MOCK] Zoning: C-2 General Commercial — 0.82 FAR available for development',
    '[VISUAL MOCK] VERIFIED: Parcel confirmed owner-occupied, 3.4 ac lot, unencumbered',
  ],
  intel: [
    '[VISUAL MOCK] NV contractor Lic #74832 — 3 open liens discovered in Clark County',
    '[VISUAL MOCK] CSLB cross-match: active in CA under alias "Desert Build Co"',
    '[VISUAL MOCK] SOS registered agent changed 47 days ago — shell flag raised',
    '[VISUAL MOCK] VERIFIED: Primary contractor clean — no active liens or judgments',
  ],
  nexus: [
    '[VISUAL MOCK] Relationship chain: Owner → LLC → silent partner (bankruptcy flagged)',
    '[VISUAL MOCK] Court record: unlawful detainer filed Q3 2024 — tenant dispute',
    '[VISUAL MOCK] LinkedIn signal: principal listed property privately — motivation confirmed',
    '[VISUAL MOCK] VERIFIED: No related-party encumbrances — clean ownership stack',
  ],
  sentinel: [
    '[VISUAL MOCK] NOD recorded 11 days ago — 90-day auction window active',
    '[VISUAL MOCK] MLS shadow listing detected — seller is testing off-market demand',
    '[VISUAL MOCK] Price reduction #3 detected — 19 days since last cut, down 8.2%',
    '[VISUAL MOCK] VERIFIED: Distress score 0.91 — NUCLEAR priority target confirmed',
  ],
  vector: [
    '[VISUAL MOCK] Lead score updated: 87/100 — above $500K acquisition threshold',
    '[VISUAL MOCK] Comparable deal: 3831 Tenaya Ave sold at 0.73 ARV — 14% below ask',
    '[VISUAL MOCK] Seller motivation index: 0.88 — fast close preferred',
    '[VISUAL MOCK] VERIFIED: Entry price $640K — projected spread $210K at 70% LTV',
  ],
  cipher: [
    '[VISUAL MOCK] Permit history: 4 pulls, 2 finalled — 2 open permits flagged',
    '[VISUAL MOCK] Title chain: 2 ownership transfers in 18 months — pattern alert',
    '[VISUAL MOCK] Easement discovered: utility corridor 12ft wide on south parcel edge',
    '[VISUAL MOCK] VERIFIED: Clean title — no senior liens, easements, or encumbrances',
  ],
  pulse: [
    '[VISUAL MOCK] Days-on-market trend: +34% in ZIP 89101 — buyer demand softening',
    '[VISUAL MOCK] Z-estimate delta: -$82K from list price — motivated seller signal',
    '[VISUAL MOCK] Absorption rate: 2.1 months — market tilting toward buyers',
    '[VISUAL MOCK] VERIFIED: Comparable pending at $668K confirms target at $640K',
  ],
  apex: [
    '[VISUAL MOCK] Underwrite complete: 18.4% IRR at 70% LTV — above 15% hurdle',
    '[VISUAL MOCK] Risk flag: foundation repair estimate $45–65K — adjust offer by $50K',
    '[VISUAL MOCK] Insurance quote: $4,200/yr — within operating budget model',
    '[VISUAL MOCK] VERIFIED: Deal approved for LOI — submit at $610K, 21-day close',
  ],
};

const TRANSITIONS: Record<AgentState, AgentState[]> = {
  idle: ['searching'],
  searching: ['processing'],
  processing: ['verified', 'nuclear'],
  verified: ['idle'],
  nuclear: ['idle'],
};

let timer: ReturnType<typeof setInterval> | null = null;

export function startSimulation() {
  if (timer !== null) return;

  timer = setInterval(() => {
    const store = useNeuralStore.getState();
    const agent = store.agents[Math.floor(Math.random() * store.agents.length)];
    const nexts = TRANSITIONS[agent.state];
    if (!nexts?.length) return;

    let next: AgentState;
    if (nexts.length === 1) {
      next = nexts[0];
    } else {
      next = Math.random() < 0.15 ? 'nuclear' : 'verified';
    }

    store.setAgentState(agent.id, next);

    if (agent.state === 'processing') {
      const pool = MOCK_FINDINGS[agent.id] ?? [];
      const msg = pool[Math.floor(Math.random() * pool.length)] ?? '[VISUAL MOCK] Signal acquired';
      store.addActivity(agent.id, msg);
    }

    if (next === 'nuclear') {
      setTimeout(() => store.setAgentState(agent.id, 'idle'), 4200);
    }
  }, 2800);
}

export function stopSimulation() {
  if (timer !== null) {
    clearInterval(timer);
    timer = null;
  }
}

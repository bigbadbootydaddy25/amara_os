export interface MiroFishScore {
  address: string;
  weight: number; // 0.0–1.0
  components: {
    distress_score: number;
    equity_score: number;
    motivation_score: number;
    market_velocity: number;
  };
  source: 'mirofish' | 'mock';
  updated_at: string;
}

// Live MiroFish API client — activate when API credentials are available
export async function fetchMiroFishScores(addresses: string[]): Promise<MiroFishScore[] | null> {
  const apiKey = process.env.MIROFISH_API_KEY?.trim();
  if (!apiKey || addresses.length === 0) return null;

  try {
    const res = await fetch('https://api.mirofish.io/v1/scores', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${apiKey}` },
      body: JSON.stringify({ addresses }),
    });
    if (!res.ok) return null;
    return (await res.json()) as MiroFishScore[];
  } catch {
    return null;
  }
}

// Mock scorer — simulates MiroFish-style ML predictions using deal data already in the system
export function mockMiroFishScore(deal: {
  address: string;
  dom?: number | null;
  price?: number | null;
  arv?: number | null;
  description?: string | null;
}): MiroFishScore {
  const dom = deal.dom ?? 0;
  const equity = deal.arv && deal.price ? (deal.arv - deal.price) / deal.arv : 0;
  const desc = (deal.description ?? '').toLowerCase();

  const distress_score = Math.min(1, (dom / 120) * 0.6 + (/as-is|investor|code|lien|estate/.test(desc) ? 0.4 : 0));
  const equity_score = Math.min(1, equity * 1.5);
  const motivation_score = Math.min(1, /motivated|fast|cash|must sell|reloc/.test(desc) ? 0.85 : dom > 90 ? 0.6 : 0.25);
  const market_velocity = Math.min(1, 0.5 + Math.random() * 0.4); // placeholder — real: pull from market data

  const weight = +(
    distress_score * 0.35 +
    equity_score * 0.35 +
    motivation_score * 0.2 +
    market_velocity * 0.1
  ).toFixed(3);

  return {
    address: deal.address,
    weight,
    components: { distress_score, equity_score, motivation_score, market_velocity },
    source: 'mock',
    updated_at: new Date().toISOString(),
  };
}

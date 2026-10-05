export type Tier = 'SR' | 'GR' | 'PC';
const RANK: Record<Tier, number> = { SR: 0, GR: 1, PC: 2 };

/** Evidence tag per spec §4: `[TIER YYYY-MM-DD]` with optional `| STATUS`. */
export function tag(tier: Tier, date: string, status?: string): string {
  return `[${tier} ${date}]${status ? ` | ${status}` : ''}`;
}

export function tierOf(t: string | null | undefined): Tier {
  const m = /^\[(SR|GR|PC)\b/.exec(t ?? '');
  return (m?.[1] as Tier) ?? 'SR';
}

/** Weakest-link rule (spec §4): a match is only as strong as its weakest deal-critical fact. */
export function weakest(tags: Array<string | null | undefined>): Tier {
  let w: Tier = 'PC';
  for (const t of tags) {
    const tier = tierOf(t);
    if (RANK[tier] < RANK[w]) w = tier;
  }
  return w;
}

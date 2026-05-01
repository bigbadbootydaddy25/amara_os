import { getMemoryClient, USER_ID } from './mem0-client';

export type MemoryCategory =
  | 'market_intel'
  | 'buyer_behavior'
  | 'deal_outcome'
  | 'agent_run'
  | 'pipeline_status'
  | 'preference';

export interface MemoryEntry {
  content: string;
  category: MemoryCategory;
  metadata?: Record<string, unknown>;
}

export async function writeMemory(entry: MemoryEntry): Promise<boolean> {
  const mem = getMemoryClient();
  if (!mem) return false; // Mem0 not configured — silently skip

  try {
    await mem.add(
      [{ role: 'user', content: entry.content }],
      {
        user_id: USER_ID,
        metadata: { category: entry.category, ...entry.metadata },
      },
    );
    return true;
  } catch {
    return false;
  }
}

export async function writeMarketMemory(market: string, summary: string): Promise<void> {
  await writeMemory({
    content: `Market ${market}: ${summary}`,
    category: 'market_intel',
    metadata: { market, date: new Date().toISOString() },
  });
}

export async function writeBuyerMemory(buyerName: string, event: string): Promise<void> {
  await writeMemory({
    content: `Buyer ${buyerName}: ${event}`,
    category: 'buyer_behavior',
    metadata: { buyerName, date: new Date().toISOString() },
  });
}

export async function writeDealMemory(address: string, decision: string, outcome?: string): Promise<void> {
  await writeMemory({
    content: `Deal ${address}: decision=${decision}${outcome ? `, outcome=${outcome}` : ''}`,
    category: 'deal_outcome',
    metadata: { address, decision, outcome, date: new Date().toISOString() },
  });
}

export async function writeAgentRunMemory(market: string, agentType: string, status: string, summary: string): Promise<void> {
  await writeMemory({
    content: `Agent run [${agentType}] in ${market}: ${status} — ${summary}`,
    category: 'agent_run',
    metadata: { market, agentType, status, date: new Date().toISOString() },
  });
}

export async function writePipelineStatus(stage: string, count: number, notes?: string): Promise<void> {
  await writeMemory({
    content: `Pipeline ${stage}: ${count} deals${notes ? ` — ${notes}` : ''}`,
    category: 'pipeline_status',
    metadata: { stage, count, date: new Date().toISOString() },
  });
}

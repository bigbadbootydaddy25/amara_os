import { getMemoryClient, USER_ID } from './mem0-client';
import type { MemoryCategory } from './memory-writer';

export interface RetrievedMemory {
  id: string;
  memory: string;
  score?: number;
  metadata?: Record<string, unknown>;
}

export async function searchMemories(
  query: string,
  limit = 20,
): Promise<RetrievedMemory[]> {
  const mem = getMemoryClient();
  if (!mem) return [];

  try {
    const results = await mem.search(query, { user_id: USER_ID, limit });
    return (results as RetrievedMemory[]) ?? [];
  } catch {
    return [];
  }
}

export async function getMemoriesByCategory(
  category: MemoryCategory,
  limit = 20,
): Promise<RetrievedMemory[]> {
  return searchMemories(category, limit);
}

export async function getSessionContext(): Promise<string> {
  const mem = getMemoryClient();
  if (!mem) return '';

  try {
    const [marketMem, buyerMem, dealMem, agentMem] = await Promise.all([
      searchMemories('market intel hot cold distress', 10),
      searchMemories('buyer behavior response purchase', 10),
      searchMemories('deal decision outcome pipeline', 10),
      searchMemories('agent run hermes results', 10),
    ]);

    const all = [...marketMem, ...buyerMem, ...dealMem, ...agentMem]
      .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
      .slice(0, 30)
      .map((m) => `- ${m.memory}`)
      .join('\n');

    return all || '';
  } catch {
    return '';
  }
}

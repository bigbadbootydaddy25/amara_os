import fs from 'fs';
import path from 'path';
import { runQuery } from '@/lib/neural-graph/neo4j-client';

const STARTING_IQ = 127;

// In-memory cache — synced to Neo4j on gain
let _currentIQ: number | null = null;

// SSE listeners — browser tabs that are subscribed to IQ events
const sseListeners = new Set<(data: string) => void>();

export function subscribeToIQEvents(listener: (data: string) => void): () => void {
  sseListeners.add(listener);
  return () => sseListeners.delete(listener);
}

function broadcast(event: Record<string, unknown>): void {
  const payload = `data: ${JSON.stringify(event)}\n\n`;
  for (const listener of sseListeners) {
    try { listener(payload); } catch { sseListeners.delete(listener); }
  }
}

async function loadIQFromNeo4j(): Promise<number> {
  try {
    const rows = await runQuery<{ iq: number }>(`MATCH (a:AMARA) RETURN a.iq AS iq LIMIT 1`);
    return rows[0]?.iq ?? STARTING_IQ;
  } catch {
    return STARTING_IQ;
  }
}

async function saveIQToNeo4j(iq: number): Promise<void> {
  try {
    await runQuery(
      `MERGE (a:AMARA {id: 'singleton'}) SET a.iq = $iq, a.updatedAt = datetime()`,
      { iq },
    );
  } catch { /* non-fatal */ }
}

export async function getCurrentIQ(): Promise<number> {
  if (_currentIQ === null) {
    _currentIQ = await loadIQFromNeo4j();
  }
  return _currentIQ;
}

export async function gainIQ(amount: number, reason: string): Promise<number> {
  const before = await getCurrentIQ();
  const after = before + Math.max(1, Math.round(amount));
  _currentIQ = after;

  await saveIQToNeo4j(after);
  appendIQLog(before, after, reason);

  // Broadcast to all SSE listeners (UI IQ display)
  broadcast({ type: 'IQ_GAIN', before, after, amount: after - before, reason });

  // IQ milestone speech triggers
  const milestones = [150, 200, 300, 500, 1000];
  for (const milestone of milestones) {
    if (before < milestone && after >= milestone) {
      broadcast({ type: 'IQ_MILESTONE', iq: milestone });
    }
  }

  return after;
}

function appendIQLog(before: number, after: number, reason: string): void {
  const logDir = path.resolve(process.cwd(), 'reports');
  const logPath = path.join(logDir, 'AMARA_IQ_LOG.md');
  fs.mkdirSync(logDir, { recursive: true });

  const line = `| ${new Date().toISOString()} | ${before} → ${after} (+${after - before}) | ${reason} |\n`;

  if (!fs.existsSync(logPath)) {
    fs.writeFileSync(logPath, `# AMARA IQ LOG\n\n| Timestamp | IQ Change | Reason |\n|-----------|-----------|--------|\n`, 'utf-8');
  }
  fs.appendFileSync(logPath, line, 'utf-8');
}

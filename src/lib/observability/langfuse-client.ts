import { Langfuse } from 'langfuse';
import fs from 'fs';
import path from 'path';

let _client: Langfuse | null = null;

export function getLangfuse(): Langfuse | null {
  const pk = process.env.LANGFUSE_PUBLIC_KEY?.trim();
  const sk = process.env.LANGFUSE_SECRET_KEY?.trim();
  if (!pk || !sk) return null;

  if (!_client) {
    _client = new Langfuse({ publicKey: pk, secretKey: sk });
  }
  return _client;
}

// Local fallback — writes traces to logs/langfuse_local/ as JSON
export function writeLocalTrace(trace: Record<string, unknown>): void {
  const dir = path.resolve(process.cwd(), 'logs/langfuse_local');
  fs.mkdirSync(dir, { recursive: true });
  const file = path.join(dir, `trace_${Date.now()}.json`);
  fs.writeFileSync(file, JSON.stringify(trace, null, 2), 'utf-8');
}

export async function flushLangfuse(): Promise<void> {
  if (_client) await _client.flushAsync();
}

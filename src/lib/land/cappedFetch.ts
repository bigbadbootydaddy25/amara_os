/**
 * Fetch helper for server-side proxy routes: bounds both time and response
 * size so a slow or hostile upstream can't hang a request or exhaust memory.
 * Mirrors the pattern used by gods-eye-view's server/providers proxies.
 */
export interface CappedFetchOptions extends RequestInit {
  timeoutMs?: number;
  maxBytes?: number;
}

export class CappedFetchError extends Error {
  constructor(
    message: string,
    public readonly reason: 'timeout' | 'too-large' | 'network' | 'http',
    public readonly status?: number,
  ) {
    super(message);
    this.name = 'CappedFetchError';
  }
}

const DEFAULT_TIMEOUT_MS = 10_000;
const DEFAULT_MAX_BYTES = 2 * 1024 * 1024;

export async function fetchCappedText(
  url: string,
  { timeoutMs = DEFAULT_TIMEOUT_MS, maxBytes = DEFAULT_MAX_BYTES, ...init }: CappedFetchOptions = {},
): Promise<string> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  let response: Response;
  try {
    response = await fetch(url, { ...init, signal: controller.signal });
  } catch (error) {
    clearTimeout(timeoutId);
    if (error instanceof Error && error.name === 'AbortError') {
      throw new CappedFetchError(`Request to upstream timed out after ${timeoutMs}ms`, 'timeout');
    }
    throw new CappedFetchError('Upstream request failed', 'network');
  }
  clearTimeout(timeoutId);

  if (!response.ok) {
    throw new CappedFetchError(`Upstream responded ${response.status}`, 'http', response.status);
  }

  const declared = Number(response.headers.get('content-length'));
  if (Number.isFinite(declared) && declared > maxBytes) {
    try {
      await response.body?.cancel();
    } catch {
      /* no-op */
    }
    throw new CappedFetchError('Upstream response exceeds size cap', 'too-large');
  }

  const asyncIterableBody = response.body as unknown as AsyncIterable<Uint8Array> | null;
  if (!asyncIterableBody || typeof asyncIterableBody[Symbol.asyncIterator] !== 'function') {
    const text = await response.text();
    if (text.length > maxBytes) {
      throw new CappedFetchError('Upstream response exceeds size cap', 'too-large');
    }
    return text;
  }

  const decoder = new TextDecoder();
  let text = '';
  let total = 0;
  for await (const chunk of asyncIterableBody) {
    total += chunk.byteLength;
    if (total > maxBytes) {
      try {
        await response.body?.cancel();
      } catch {
        /* no-op */
      }
      throw new CappedFetchError('Upstream response exceeds size cap', 'too-large');
    }
    text += decoder.decode(chunk, { stream: true });
  }
  text += decoder.decode();
  return text;
}

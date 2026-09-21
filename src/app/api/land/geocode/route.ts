import { NextResponse } from 'next/server';
import { fetchCappedText, CappedFetchError } from '@/lib/land/cappedFetch';
import { buildNominatimUrl, parseNominatimResults } from '@/lib/land/geocode';

// OSM Nominatim usage policy requires a real, identifying User-Agent.
const USER_AGENT = 'amara-os-land-module/0.1 (contact: set NOMINATIM_CONTACT env var)';

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const query = searchParams.get('q') ?? '';

  let url: string;
  try {
    url = buildNominatimUrl(query);
  } catch {
    return NextResponse.json({ error: 'Missing or empty "q" query parameter' }, { status: 400 });
  }

  try {
    const body = await fetchCappedText(url, {
      timeoutMs: 8_000,
      maxBytes: 512 * 1024,
      headers: { 'User-Agent': USER_AGENT, Accept: 'application/json' },
    });
    const results = parseNominatimResults(body);
    return NextResponse.json({ results }, { headers: { 'Cache-Control': 'no-store' } });
  } catch (error) {
    if (error instanceof CappedFetchError) {
      const status = error.reason === 'timeout' ? 504 : error.reason === 'too-large' ? 502 : 502;
      return NextResponse.json({ error: 'Geocoding lookup failed' }, { status });
    }
    return NextResponse.json({ error: 'Geocoding lookup failed' }, { status: 502 });
  }
}

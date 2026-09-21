import { NextResponse } from 'next/server';
import { fetchCappedText, CappedFetchError } from '@/lib/land/cappedFetch';
import { isFiniteCoordinate } from '@/lib/land/geo';
import { SDA_ENDPOINT, buildSoilRequestBody, parseSoilResponse } from '@/lib/land/soil';

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const lat = Number(searchParams.get('lat'));
  const lon = Number(searchParams.get('lon'));

  if (!isFiniteCoordinate(lon, lat)) {
    return NextResponse.json({ error: 'Missing or invalid lat/lon query parameters' }, { status: 400 });
  }

  try {
    const body = await fetchCappedText(SDA_ENDPOINT, {
      method: 'POST',
      timeoutMs: 15_000,
      maxBytes: 1024 * 1024,
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: buildSoilRequestBody({ lon, lat }),
    });
    const result = parseSoilResponse(body);
    return NextResponse.json(result, { headers: { 'Cache-Control': 'no-store' } });
  } catch (error) {
    if (error instanceof CappedFetchError) {
      const status = error.reason === 'timeout' ? 504 : 502;
      return NextResponse.json({ error: 'Soil lookup failed' }, { status });
    }
    return NextResponse.json({ error: 'Soil lookup failed' }, { status: 502 });
  }
}

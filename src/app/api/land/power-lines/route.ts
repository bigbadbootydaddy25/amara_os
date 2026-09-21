import { NextResponse } from 'next/server';
import { fetchCappedText, CappedFetchError } from '@/lib/land/cappedFetch';
import { bboxAroundPoint, isFiniteCoordinate } from '@/lib/land/geo';
import { OVERPASS_ENDPOINT, buildPowerLinesQuery, parsePowerLinesResponse } from '@/lib/land/overpass';

const MAX_RADIUS_M = 5_000;
const MIN_RADIUS_M = 50;

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const lat = Number(searchParams.get('lat'));
  const lon = Number(searchParams.get('lon'));
  const radiusM = Math.max(MIN_RADIUS_M, Math.min(Number(searchParams.get('radiusM')) || 500, MAX_RADIUS_M));

  if (!isFiniteCoordinate(lon, lat)) {
    return NextResponse.json({ error: 'Missing or invalid lat/lon query parameters' }, { status: 400 });
  }

  const bbox = bboxAroundPoint({ lon, lat }, radiusM);
  const query = buildPowerLinesQuery(bbox);

  try {
    const body = await fetchCappedText(OVERPASS_ENDPOINT, {
      method: 'POST',
      timeoutMs: 20_000,
      maxBytes: 4 * 1024 * 1024,
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ data: query }).toString(),
    });
    const result = parsePowerLinesResponse(body);
    return NextResponse.json({ ...result, bbox }, { headers: { 'Cache-Control': 'no-store' } });
  } catch (error) {
    if (error instanceof CappedFetchError) {
      const status = error.reason === 'timeout' ? 504 : 502;
      return NextResponse.json({ error: 'Power-line lookup failed' }, { status });
    }
    return NextResponse.json({ error: 'Power-line lookup failed' }, { status: 502 });
  }
}

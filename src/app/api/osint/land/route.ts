import { NextRequest, NextResponse } from 'next/server';
import type { OsintScanResult, OsintQueryType } from '@/types';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

const IP_RE = /^(?:\d{1,3}\.){3}\d{1,3}$/;
const COORD_RE = /^(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)$/;

const NOMINATIM_UA = 'AMARA-OS/1.0 (OSINT Land Scanner; non-commercial)';

function detectQueryType(query: string): OsintQueryType {
  if (IP_RE.test(query)) return 'ip';
  if (COORD_RE.test(query)) return 'coordinates';
  return 'address';
}

async function scanIp(ip: string): Promise<OsintScanResult> {
  const fields =
    'status,message,continent,continentCode,country,countryCode,region,regionName,city,zip,lat,lon,timezone,isp,org,as,asname,proxy,hosting,query';

  const res = await fetch(`http://ip-api.com/json/${encodeURIComponent(ip)}?fields=${fields}`, {
    signal: AbortSignal.timeout(8000),
    headers: { 'User-Agent': 'AMARA-OS/1.0' },
  });

  if (!res.ok) throw new Error(`IP lookup failed: ${res.statusText}`);

  const d = (await res.json()) as Record<string, unknown>;

  if (d.status === 'fail') {
    throw new Error(typeof d.message === 'string' ? d.message : 'IP lookup failed');
  }

  return {
    query: ip,
    queryType: 'ip',
    timestamp: new Date().toISOString(),
    location: {
      lat: typeof d.lat === 'number' ? d.lat : undefined,
      lon: typeof d.lon === 'number' ? d.lon : undefined,
      city: typeof d.city === 'string' ? d.city : undefined,
      region: typeof d.regionName === 'string' ? d.regionName : undefined,
      country: typeof d.country === 'string' ? d.country : undefined,
      countryCode: typeof d.countryCode === 'string' ? d.countryCode : undefined,
      zip: typeof d.zip === 'string' ? d.zip : undefined,
      timezone: typeof d.timezone === 'string' ? d.timezone : undefined,
      continent: typeof d.continent === 'string' ? d.continent : undefined,
    },
    network: {
      isp: typeof d.isp === 'string' ? d.isp : undefined,
      org: typeof d.org === 'string' ? d.org : undefined,
      as: typeof d.as === 'string' ? d.as : undefined,
      asName: typeof d.asname === 'string' ? d.asname : undefined,
      isProxy: d.proxy === true,
      isHosting: d.hosting === true,
    },
  };
}

async function scanCoordinates(coordStr: string): Promise<OsintScanResult> {
  const match = COORD_RE.exec(coordStr);
  if (!match) throw new Error('Invalid coordinates');

  const lat = parseFloat(match[1]);
  const lon = parseFloat(match[2]);

  const res = await fetch(
    `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}&zoom=18&addressdetails=1`,
    { signal: AbortSignal.timeout(8000), headers: { 'User-Agent': NOMINATIM_UA } },
  );

  if (!res.ok) throw new Error(`Reverse geocoding failed: ${res.statusText}`);

  const d = (await res.json()) as Record<string, unknown>;
  const addr = d.address as Record<string, string> | undefined;

  return {
    query: coordStr,
    queryType: 'coordinates',
    timestamp: new Date().toISOString(),
    location: {
      lat,
      lon,
      displayName: typeof d.display_name === 'string' ? d.display_name : undefined,
      city: addr?.city ?? addr?.town ?? addr?.village,
      region: addr?.state,
      country: addr?.country,
      countryCode: addr?.country_code?.toUpperCase(),
      zip: addr?.postcode,
    },
    place: {
      type: typeof d.type === 'string' ? d.type : undefined,
      category: typeof d.category === 'string' ? d.category : undefined,
      osmType: typeof d.osm_type === 'string' ? d.osm_type : undefined,
      osmId: typeof d.osm_id === 'number' ? d.osm_id : undefined,
      importance: typeof d.importance === 'number' ? d.importance : undefined,
      boundingBox: Array.isArray(d.boundingbox)
        ? (d.boundingbox as [string, string, string, string])
        : undefined,
    },
  };
}

async function scanAddress(address: string): Promise<OsintScanResult> {
  const res = await fetch(
    `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(address)}&limit=1&addressdetails=1`,
    { signal: AbortSignal.timeout(8000), headers: { 'User-Agent': NOMINATIM_UA } },
  );

  if (!res.ok) throw new Error(`Geocoding failed: ${res.statusText}`);

  const results = (await res.json()) as Record<string, unknown>[];

  if (!results.length) throw new Error('No location found for this query');

  const d = results[0];
  const addr = d.address as Record<string, string> | undefined;
  const lat = parseFloat(d.lat as string);
  const lon = parseFloat(d.lon as string);

  return {
    query: address,
    queryType: 'address',
    timestamp: new Date().toISOString(),
    location: {
      lat: isNaN(lat) ? undefined : lat,
      lon: isNaN(lon) ? undefined : lon,
      displayName: typeof d.display_name === 'string' ? d.display_name : undefined,
      city: addr?.city ?? addr?.town ?? addr?.village,
      region: addr?.state,
      country: addr?.country,
      countryCode: addr?.country_code?.toUpperCase(),
      zip: addr?.postcode,
    },
    place: {
      type: typeof d.type === 'string' ? d.type : undefined,
      category: typeof d.class === 'string' ? d.class : undefined,
      osmType: typeof d.osm_type === 'string' ? d.osm_type : undefined,
      osmId: typeof d.osm_id === 'number' ? d.osm_id : undefined,
      importance: typeof d.importance === 'number' ? d.importance : undefined,
      boundingBox: Array.isArray(d.boundingbox)
        ? (d.boundingbox as [string, string, string, string])
        : undefined,
    },
  };
}

export async function POST(request: NextRequest) {
  try {
    const body = (await request.json()) as { query?: string };
    const query = body.query?.trim();

    if (!query) {
      return NextResponse.json({ error: 'No query provided' }, { status: 400 });
    }

    if (query.length > 500) {
      return NextResponse.json({ error: 'Query too long' }, { status: 400 });
    }

    const queryType = detectQueryType(query);

    let result: OsintScanResult;

    switch (queryType) {
      case 'ip':
        result = await scanIp(query);
        break;
      case 'coordinates':
        result = await scanCoordinates(query);
        break;
      default:
        result = await scanAddress(query);
    }

    return NextResponse.json(result);
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Scan failed';
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { buildSoilPointQuery, buildSoilRequestBody, parseSoilResponse } from './soil';

test('buildSoilPointQuery embeds the point as WKT "lon lat"', () => {
  const q = buildSoilPointQuery({ lon: -97.7431, lat: 30.2672 });
  assert.match(q, /point\(-97\.7431 30\.2672\)/);
  assert.match(q, /SDA_Get_Mukey_from_intersection_with_WktWgs84/);
});

test('buildSoilRequestBody wraps the query as SDA JSON envelope', () => {
  const body = JSON.parse(buildSoilRequestBody({ lon: -97.7431, lat: 30.2672 }));
  assert.equal(body.format, 'JSON');
  assert.match(body.query, /point\(-97\.7431 30\.2672\)/);
});

function tableBody(rows: unknown[][]): string {
  const header = ['mukey', 'musym', 'muname', 'compname', 'comppct_r', 'drainagecl', 'hydricrating', 'majcompflag'];
  return JSON.stringify({ Table: [header, ...rows] });
}

test('parseSoilResponse flags hydric soil as poor regardless of drainage class text', () => {
  const body = tableBody([[1, 'Xx', 'Example wetland', 'Sample', 85, 'Poorly drained', 'Yes', 'Yes']]);
  const result = parseSoilResponse(body);
  assert.equal(result.suitability, 'poor');
  assert.match(result.reason, /hydric/);
});

test('parseSoilResponse flags poor drainage class as poor', () => {
  const body = tableBody([[1, 'Xx', 'Example', 'Sample', 85, 'Very poorly drained', 'No', 'Yes']]);
  assert.equal(parseSoilResponse(body).suitability, 'poor');
});

test('parseSoilResponse flags moderate drainage as caution', () => {
  const body = tableBody([[1, 'Xx', 'Example', 'Sample', 85, 'Somewhat poorly drained', 'No', 'Yes']]);
  assert.equal(parseSoilResponse(body).suitability, 'caution');
});

test('parseSoilResponse flags good drainage as likely-suitable', () => {
  const body = tableBody([[1, 'Xx', 'Example', 'Sample', 85, 'Well drained', 'No', 'Yes']]);
  const result = parseSoilResponse(body);
  assert.equal(result.suitability, 'likely-suitable');
  assert.equal(result.dominantComponent?.mapUnitName, 'Example');
});

test('parseSoilResponse returns unknown for unrecognized drainage text', () => {
  const body = tableBody([[1, 'Xx', 'Example', 'Sample', 85, 'Something weird', 'No', 'Yes']]);
  assert.equal(parseSoilResponse(body).suitability, 'unknown');
});

test('parseSoilResponse returns unknown with no components for an empty table', () => {
  const result = parseSoilResponse(JSON.stringify({ Table: [['mukey']] }));
  assert.equal(result.suitability, 'unknown');
  assert.equal(result.dominantComponent, null);
});

test('parseSoilResponse throws on malformed JSON', () => {
  assert.throws(() => parseSoilResponse('not json'));
});

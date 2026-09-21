import { test } from 'node:test';
import assert from 'node:assert/strict';
import { buildPowerLinesQuery, parsePowerLinesResponse } from './overpass';

const bbox = { minLon: -97.75, minLat: 30.26, maxLon: -97.74, maxLat: 30.27 };

test('buildPowerLinesQuery embeds the bbox as lat,lon,lat,lon and filters power tags', () => {
  const q = buildPowerLinesQuery(bbox, 15);
  assert.match(q, /\[timeout:15\]/);
  assert.match(q, /30\.26,-97\.75,30\.27,-97\.74/);
  assert.match(q, /power.*line\|minor_line\|cable/);
});

test('parsePowerLinesResponse extracts a way as a line with voltage and operator', () => {
  const body = JSON.stringify({
    elements: [
      {
        type: 'way',
        id: 123,
        tags: { power: 'line', voltage: '138000', operator: 'Oncor' },
        geometry: [
          { lat: 30.26, lon: -97.75 },
          { lat: 30.27, lon: -97.74 },
        ],
      },
    ],
  });
  const result = parsePowerLinesResponse(body);
  assert.equal(result.lines.length, 1);
  assert.equal(result.points.length, 0);
  const line = result.lines[0];
  assert.equal(line.kind, 'line');
  assert.equal(line.voltage, 138000);
  assert.equal(line.operator, 'Oncor');
  assert.deepEqual(line.path, [
    [-97.75, 30.26],
    [-97.74, 30.27],
  ]);
});

test('parsePowerLinesResponse extracts a node as a point (tower/substation)', () => {
  const body = JSON.stringify({
    elements: [{ type: 'node', id: 456, lat: 30.265, lon: -97.745, tags: { power: 'tower' } }],
  });
  const result = parsePowerLinesResponse(body);
  assert.equal(result.points.length, 1);
  assert.equal(result.points[0].kind, 'tower');
  assert.equal(result.points[0].lat, 30.265);
});

test('parsePowerLinesResponse takes the max of a semicolon-separated voltage list', () => {
  const body = JSON.stringify({
    elements: [
      {
        type: 'way',
        id: 1,
        tags: { power: 'line', voltage: '110000;220000' },
        geometry: [
          { lat: 0, lon: 0 },
          { lat: 1, lon: 1 },
        ],
      },
    ],
  });
  const result = parsePowerLinesResponse(body);
  assert.equal(result.lines[0].voltage, 220000);
});

test('parsePowerLinesResponse ignores non-power elements and malformed geometry', () => {
  const body = JSON.stringify({
    elements: [
      { type: 'way', id: 1, tags: { highway: 'primary' }, geometry: [{ lat: 0, lon: 0 }] },
      { type: 'way', id: 2, tags: { power: 'line' }, geometry: [{ lat: 0, lon: 0 }] }, // only 1 point
      { type: 'node', id: 3, tags: { power: 'tower' } }, // missing lat/lon
    ],
  });
  const result = parsePowerLinesResponse(body);
  assert.equal(result.lines.length, 0);
  assert.equal(result.points.length, 0);
});

test('parsePowerLinesResponse throws on malformed JSON and tolerates missing elements array', () => {
  assert.throws(() => parsePowerLinesResponse('not json'));
  assert.deepEqual(parsePowerLinesResponse(JSON.stringify({})), { lines: [], points: [] });
});

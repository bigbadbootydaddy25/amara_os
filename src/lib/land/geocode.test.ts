import { test } from 'node:test';
import assert from 'node:assert/strict';
import { buildNominatimUrl, parseNominatimResults } from './geocode';

test('buildNominatimUrl encodes the query and clamps limit', () => {
  const url = buildNominatimUrl('123 Main St, Austin, TX', 999);
  assert.match(url, /^https:\/\/nominatim\.openstreetmap\.org\/search\?/);
  assert.match(url, /q=123\+Main\+St%2C\+Austin%2C\+TX/);
  assert.match(url, /limit=10/); // clamped to max 10
});

test('buildNominatimUrl rejects an empty query', () => {
  assert.throws(() => buildNominatimUrl('   '));
});

test('parseNominatimResults extracts valid rows and normalizes shape', () => {
  const body = JSON.stringify([
    {
      display_name: '123 Main St, Austin, TX, USA',
      lat: '30.2672',
      lon: '-97.7431',
      boundingbox: ['30.26', '30.27', '-97.75', '-97.74'],
      category: 'place',
    },
  ]);
  const results = parseNominatimResults(body);
  assert.equal(results.length, 1);
  assert.equal(results[0].lat, 30.2672);
  assert.equal(results[0].lon, -97.7431);
  assert.deepEqual(results[0].boundingBox, [30.26, 30.27, -97.75, -97.74]);
  assert.equal(results[0].category, 'place');
});

test('parseNominatimResults drops rows with invalid or out-of-range coordinates', () => {
  const body = JSON.stringify([
    { display_name: 'bad', lat: 'not-a-number', lon: '-97.7' },
    { display_name: 'out of range', lat: '999', lon: '-97.7' },
    { display_name: 'ok', lat: '30.2672', lon: '-97.7431' },
  ]);
  const results = parseNominatimResults(body);
  assert.equal(results.length, 1);
  assert.equal(results[0].displayName, 'ok');
});

test('parseNominatimResults returns empty array for non-array payloads', () => {
  assert.deepEqual(parseNominatimResults(JSON.stringify({ error: 'nope' })), []);
});

test('parseNominatimResults throws on malformed JSON', () => {
  assert.throws(() => parseNominatimResults('not json'));
});

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { bboxAroundPoint, distanceMeters, isFiniteCoordinate } from './geo';

test('bboxAroundPoint produces a box centered on the point', () => {
  const box = bboxAroundPoint({ lon: -97.7431, lat: 30.2672 }, 1000);
  assert.ok(box.minLon < -97.7431 && box.maxLon > -97.7431);
  assert.ok(box.minLat < 30.2672 && box.maxLat > 30.2672);
});

test('bboxAroundPoint clamps at the antimeridian and poles', () => {
  const box = bboxAroundPoint({ lon: 179.999, lat: 89.999 }, 50_000);
  assert.ok(box.maxLon <= 180);
  assert.ok(box.maxLat <= 90);
});

test('distanceMeters is ~0 for the same point and grows with separation', () => {
  const a = { lon: -97.7431, lat: 30.2672 };
  const near = distanceMeters(a, a);
  assert.ok(near < 1);
  const far = distanceMeters(a, { lon: -122.4194, lat: 37.7749 });
  // Austin -> San Francisco is roughly 2400 km.
  assert.ok(far > 2_000_000 && far < 2_800_000);
});

test('isFiniteCoordinate rejects out-of-range and non-numeric input', () => {
  assert.equal(isFiniteCoordinate(-97.7, 30.2), true);
  assert.equal(isFiniteCoordinate(-200, 30.2), false);
  assert.equal(isFiniteCoordinate(-97.7, 200), false);
  assert.equal(isFiniteCoordinate('nope', 30.2), false);
  assert.equal(isFiniteCoordinate(NaN, 30.2), false);
});

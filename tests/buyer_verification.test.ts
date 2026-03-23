/**
 * Unit tests for BuyerVerificationService
 *
 * Tests the core rule engine without hitting a real database.
 * All assertions verify the truth-preserving contract:
 *   - no buyer is verified without meeting explicit thresholds
 *   - entity type is detected from name keywords
 *   - tier downgrades when recency lapses
 */

import {
  computeVerificationFlags,
  computeTier,
  detectEntityType,
} from '../src/services/buyer_verification';

// ─── Helpers ──────────────────────────────────────────────────────────────────

function daysAgo(n: number): Date {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d;
}

function makeSummary(overrides: {
  total?: number;
  tx12?: number;
  tx24?: number;
  daysSince?: number | null;
  first?: Date;
  last?: Date;
}) {
  const last = overrides.last ?? daysAgo(overrides.daysSince ?? 10);
  const first = overrides.first ?? daysAgo(365);
  return {
    buyer_entity_id: 'test-id',
    total_transactions: String(overrides.total ?? overrides.tx12 ?? 0),
    transactions_last_12mo: String(overrides.tx12 ?? 0),
    transactions_last_24mo: String(overrides.tx24 ?? overrides.tx12 ?? 0),
    first_transaction_date: first,
    last_transaction_date: last,
    days_since_last_transaction: overrides.daysSince !== undefined
      ? String(overrides.daysSince)
      : String(Math.floor((Date.now() - last.getTime()) / 86_400_000)),
    avg_days_between_transactions: null,
  };
}

// ─── detectEntityType ─────────────────────────────────────────────────────────

describe('detectEntityType', () => {
  test('detects LLC', () => {
    expect(detectEntityType('Smith Properties LLC')).toBe('llc');
  });

  test('detects builder', () => {
    expect(detectEntityType('Horizon Builders Inc')).toBe('builder_developer');
  });

  test('detects developer', () => {
    expect(detectEntityType('Urban Developer Group')).toBe('builder_developer');
  });

  test('detects institutional fund', () => {
    expect(detectEntityType('Blackstone Capital Fund II')).toBe('institution');
  });

  test('detects trust', () => {
    expect(detectEntityType('The Jones Family Trust')).toBe('trust');
  });

  test('returns unknown for plain names', () => {
    expect(detectEntityType('John Doe')).toBe('unknown');
  });
});

// ─── computeVerificationFlags ─────────────────────────────────────────────────

describe('computeVerificationFlags', () => {
  test('meets_12mo_threshold when 2+ transactions in last 12 months', () => {
    const flags = computeVerificationFlags(
      makeSummary({ total: 3, tx12: 2, tx24: 3, daysSince: 30 }),
      [daysAgo(300), daysAgo(200), daysAgo(30)],
      'Test Buyer LLC'
    );
    expect(flags.meets_12mo_threshold).toBe(true);
  });

  test('does NOT meet 12mo threshold with only 1 transaction in 12 months', () => {
    const flags = computeVerificationFlags(
      makeSummary({ total: 5, tx12: 1, tx24: 5, daysSince: 10 }),
      [],
      'Test Buyer LLC'
    );
    expect(flags.meets_12mo_threshold).toBe(false);
  });

  test('meets_24mo_threshold when 4+ transactions in 24 months', () => {
    const flags = computeVerificationFlags(
      makeSummary({ total: 5, tx12: 1, tx24: 4, daysSince: 10 }),
      [],
      'Test Buyer LLC'
    );
    expect(flags.meets_24mo_threshold).toBe(true);
  });

  test('is_recently_active false when last transaction > 180 days ago', () => {
    const flags = computeVerificationFlags(
      makeSummary({ total: 3, tx12: 0, tx24: 3, daysSince: 200 }),
      [],
      'Test Buyer LLC'
    );
    expect(flags.is_recently_active).toBe(false);
  });

  test('is_recently_active true when last transaction within 180 days', () => {
    const flags = computeVerificationFlags(
      makeSummary({ total: 3, tx12: 2, tx24: 3, daysSince: 90 }),
      [],
      'Test Buyer LLC'
    );
    expect(flags.is_recently_active).toBe(true);
  });

  test('detects builder keyword in name', () => {
    const flags = computeVerificationFlags(
      makeSummary({ total: 5, tx12: 3, tx24: 5, daysSince: 10 }),
      [],
      'Southwest Builders LLC'
    );
    expect(flags.is_builder_developer).toBe(true);
    expect(flags.is_institutional).toBe(false);
  });

  test('detects institutional keyword in name', () => {
    const flags = computeVerificationFlags(
      makeSummary({ total: 50, tx12: 10, tx24: 20, daysSince: 5 }),
      [],
      'Cerberus Capital Fund IV'
    );
    expect(flags.is_institutional).toBe(true);
    expect(flags.is_builder_developer).toBe(false);
  });
});

// ─── computeTier ─────────────────────────────────────────────────────────────

describe('computeTier', () => {
  const baseFlags = {
    is_builder_developer: false,
    is_institutional: false,
    transaction_pace_per_year: null,
    consistency_score: null,
  };

  test('insufficient_data when total_transaction_count < 2', () => {
    const tier = computeTier({
      ...baseFlags,
      meets_12mo_threshold: false,
      meets_24mo_threshold: false,
      last_transaction_days_ago: 10,
      is_recently_active: true,
      total_transaction_count: 1,
    });
    expect(tier).toBe('insufficient_data');
  });

  test('unverified when has transactions but meets no threshold', () => {
    const tier = computeTier({
      ...baseFlags,
      meets_12mo_threshold: false,
      meets_24mo_threshold: false,
      last_transaction_days_ago: 30,
      is_recently_active: true,
      total_transaction_count: 3,
    });
    expect(tier).toBe('unverified');
  });

  test('verified_active when meets 12mo threshold and recently active', () => {
    const tier = computeTier({
      ...baseFlags,
      meets_12mo_threshold: true,
      meets_24mo_threshold: false,
      last_transaction_days_ago: 45,
      is_recently_active: true,
      total_transaction_count: 4,
    });
    expect(tier).toBe('verified_active');
  });

  test('verified_inactive when meets threshold but not recently active', () => {
    const tier = computeTier({
      ...baseFlags,
      meets_12mo_threshold: false,
      meets_24mo_threshold: true,
      last_transaction_days_ago: 300,
      is_recently_active: false,
      total_transaction_count: 6,
    });
    expect(tier).toBe('verified_inactive');
  });

  test('verified_active when meets 24mo threshold and recently active', () => {
    const tier = computeTier({
      ...baseFlags,
      meets_12mo_threshold: false,
      meets_24mo_threshold: true,
      last_transaction_days_ago: 60,
      is_recently_active: true,
      total_transaction_count: 5,
    });
    expect(tier).toBe('verified_active');
  });
});

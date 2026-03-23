/**
 * Unit tests for StrategyClassifier
 * Verifies that strategy is inferred from behavioral signals — never assumed.
 */

import { classifyStrategy, StrategySignals } from '../src/services/strategy_classifier';

const baseFlags = {
  is_builder_developer: false,
  is_institutional: false,
  transaction_pace_per_year: null,
};

describe('classifyStrategy', () => {
  test('returns unknown for sparse signals', () => {
    const result = classifyStrategy({
      propertyTypes: [],
      priceAvg: null,
      priceSpreadRatio: null,
      acquisitionsPerYear: null,
      uniqueZipCount: 1,
      totalTransactions: 2,
      entityFlags: baseFlags,
    });
    expect(result.strategy).toBe('unknown');
    expect(result.confidence).toBe(0);
  });

  test('classifies new_construction from builder keyword + land acquisitions', () => {
    const result = classifyStrategy({
      propertyTypes: [
        { property_type: 'land', pct_of_total: 70 },
        { property_type: 'sfr', pct_of_total: 30 },
      ],
      priceAvg: 180_000,
      priceSpreadRatio: 0.2,
      acquisitionsPerYear: 6,
      uniqueZipCount: 2,
      totalTransactions: 12,
      entityFlags: { ...baseFlags, is_builder_developer: true },
    });
    expect(result.strategy).toBe('new_construction');
    expect(result.confidence).toBeGreaterThan(0.5);
  });

  test('classifies institutional_sfr from fund keyword + high pace', () => {
    const result = classifyStrategy({
      propertyTypes: [{ property_type: 'sfr', pct_of_total: 100 }],
      priceAvg: 250_000,
      priceSpreadRatio: 0.1,
      acquisitionsPerYear: 35,
      uniqueZipCount: 8,
      totalTransactions: 70,
      entityFlags: { ...baseFlags, is_institutional: true, transaction_pace_per_year: 35 },
    });
    expect(result.strategy).toBe('institutional_sfr');
  });

  test('classifies fix_and_flip from low price + SFR + moderate pace', () => {
    const result = classifyStrategy({
      propertyTypes: [{ property_type: 'sfr', pct_of_total: 90 }],
      priceAvg: 120_000,
      priceSpreadRatio: 0.5,
      acquisitionsPerYear: 8,
      uniqueZipCount: 4,
      totalTransactions: 16,
      entityFlags: baseFlags,
    });
    expect(result.strategy).toBe('fix_and_flip');
  });

  test('classifies rental_portfolio from multi-family concentration', () => {
    const result = classifyStrategy({
      propertyTypes: [
        { property_type: 'mfr', pct_of_total: 60 },
        { property_type: 'sfr', pct_of_total: 40 },
      ],
      priceAvg: 400_000,
      priceSpreadRatio: 0.15,
      acquisitionsPerYear: 4,
      uniqueZipCount: 2,
      totalTransactions: 8,
      entityFlags: baseFlags,
    });
    expect(result.strategy).toBe('rental_portfolio');
  });

  test('includes signal evidence in result', () => {
    const result = classifyStrategy({
      propertyTypes: [{ property_type: 'sfr', pct_of_total: 90 }],
      priceAvg: 110_000,
      priceSpreadRatio: 0.45,
      acquisitionsPerYear: 9,
      uniqueZipCount: 6,
      totalTransactions: 18,
      entityFlags: baseFlags,
    });
    expect(result.signals.length).toBeGreaterThan(0);
  });
});

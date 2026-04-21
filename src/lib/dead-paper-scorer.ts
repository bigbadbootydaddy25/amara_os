import type { DeadPaperFlags } from '@/types/real-estate';

const DEAD_PAPER_KEYWORDS = [
  'as-is', 'as is', 'investor', 'fixer', 'tlc', 'estate', 'probate',
  'must sell', 'opportunity', 'repairs', 'vacant land', 'land only',
  'raw land', 'unimproved', 'seller motivated', 'price reduced',
];

const LOT_NUMBERING_PATTERN = /(lot\s*\d+|#\s*\d{2,}|\blot\s+[a-z]?\d+)/i;
const PLACEHOLDER_ADDRESS_PATTERN = /^(0\s+unknown|xxxx|\bvacant\b|tbd\b|unassigned)/i;

export function scoreKeywords(description: string): number {
  const lower = description.toLowerCase();
  const hits = DEAD_PAPER_KEYWORDS.filter((kw) => lower.includes(kw));
  return Math.min(hits.length, 3);
}

export function detectFlags(
  address: string,
  description: string,
  context?: {
    nearbyListingCount?: number;
    parcelAcres?: number;
    nearRooftops?: boolean;
    inBuilderZone?: boolean;
    isIrregularShape?: boolean;
  },
): DeadPaperFlags {
  const combined = `${address} ${description}`;
  return {
    hasLotNumbering: LOT_NUMBERING_PATTERN.test(combined),
    hasMultipleNearbyListings: (context?.nearbyListingCount ?? 0) >= 2,
    hasPlaceholderAddress: PLACEHOLDER_ADDRESS_PATTERN.test(address.trim()),
    isOversizedParcel: (context?.parcelAcres ?? 0) > 0.5 && (context?.nearRooftops ?? false),
    inBuilderExpansionZone: context?.inBuilderZone ?? false,
    hasIrregularShape: context?.isIrregularShape ?? false,
  };
}

export function calcDeadPaperScore(flags: DeadPaperFlags, keywordScore: number): number {
  const flagScore = [
    flags.hasLotNumbering,
    flags.hasMultipleNearbyListings,
    flags.hasPlaceholderAddress,
    flags.isOversizedParcel,
    flags.inBuilderExpansionZone,
    flags.hasIrregularShape,
  ].filter(Boolean).length;

  return keywordScore + flagScore;
}

export function priorityLevel(score: number): 'ignore' | 'investigate' | 'priority' {
  if (score >= 4) return 'priority';
  if (score >= 2) return 'investigate';
  return 'ignore';
}

/**
 * Groups raw deed transactions by buyer entity.
 * Flags repeat buyers (2+ purchases) and scores AMARA buy signal.
 */

// ─── Entity name normalization ────────────────────────────────────────────────

// Suffixes stripped for grouping key (but full name preserved)
const ENTITY_SUFFIXES = [
  'LLC', 'L.L.C', 'INC', 'INCORPORATED', 'CORP', 'CORPORATION',
  'LP', 'L.P', 'LLP', 'L.L.P', 'LTD', 'LIMITED', 'TRUST',
  'CO', 'COMPANY', 'GROUP', 'PARTNERS', 'PARTNERSHIP',
  'FUND', 'CAPITAL', 'VENTURES', 'ENTERPRISE', 'ENTERPRISES',
  'REALTY', 'REAL ESTATE',
];

const SUFFIX_PATTERN = new RegExp(
  `\\b(${ENTITY_SUFFIXES.join('|').replace(/\./g, '\\.')})\\b\\.?\\s*$`,
  'i'
);

export function normalizeName(raw) {
  if (!raw) return '';
  let name = raw
    .toUpperCase()
    .replace(/[^A-Z0-9\s&']/g, ' ')   // keep alphanumeric, spaces, & and '
    .replace(/\s+/g, ' ')
    .trim();

  // Strip trailing entity suffixes iteratively (e.g., "HOMES LLC INC")
  let prev;
  do {
    prev = name;
    name = name.replace(SUFFIX_PATTERN, '').trim();
  } while (name !== prev);

  return name;
}

// ─── Entity type classification ───────────────────────────────────────────────

const TYPE_RULES = [
  {
    keywords: ['HOMES', 'CONSTRUCTION', 'BUILDERS', 'BUILDER', 'DEVELOPMENT', 'BUILD', 'CUSTOM'],
    type: 'builder',
    strategy: 'builder',
  },
  {
    keywords: ['RENTALS', 'RENTAL', 'PROPERTIES', 'HOLDINGS', 'INVESTMENTS', 'INVESTMENT', 'ASSET', 'ASSETS', 'PORTFOLIO'],
    type: 'landlord',
    strategy: 'rental',
  },
];

export function classifyEntity(name) {
  const upper = name.toUpperCase();
  for (const rule of TYPE_RULES) {
    if (rule.keywords.some((kw) => upper.includes(kw))) {
      return { type: rule.type, strategy: rule.strategy };
    }
  }
  return { type: 'flipper', strategy: 'flip' };
}

// ─── Signal scoring ───────────────────────────────────────────────────────────

export function scoreSignal(entity) {
  const multiZip = entity.zips.length > 1;
  const cashCount = entity.cash_purchases;

  if (cashCount > 3 && multiZip) return 'HIGH';
  if (cashCount > 3) return 'MEDIUM';
  if (cashCount >= 2 && cashCount <= 3) return 'MEDIUM';
  return 'LOW';
}

// ─── Main grouper ─────────────────────────────────────────────────────────────

/**
 * @param {Array<{county: string, transactions: Array}>} scraperResults
 * @returns {{ buyers: Array, stats: Object }}
 */
export function groupBuyers(scraperResults) {
  // Flatten all transactions from all counties
  const allTransactions = [];
  for (const result of scraperResults) {
    if (!result || !Array.isArray(result.transactions)) continue;
    allTransactions.push(...result.transactions);
  }

  console.log(`[grouper] Processing ${allTransactions.length} total transactions`);

  // Deduplicate by document number + county (in case a portal returns duplicates)
  const seen = new Set();
  const deduped = allTransactions.filter((t) => {
    const key = `${t.source_county}|${t.document_number || t.apn + t.document_date}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });

  console.log(`[grouper] ${deduped.length} unique transactions after deduplication`);

  // Group by normalized grantee name
  const groups = new Map(); // normalizedKey -> { fullName, transactions[] }

  for (const t of deduped) {
    if (!t.grantee) continue;

    const normalizedKey = normalizeName(t.grantee);
    if (!normalizedKey) continue;

    if (!groups.has(normalizedKey)) {
      groups.set(normalizedKey, { fullName: t.grantee, transactions: [] });
    }

    const group = groups.get(normalizedKey);
    group.transactions.push(t);

    // Keep the most common full name (longest non-empty form)
    if (t.grantee.length > group.fullName.length) {
      group.fullName = t.grantee;
    }
  }

  // Build buyer entities, filter for 2+ purchases
  const buyers = [];

  for (const [normalizedKey, group] of groups.entries()) {
    const txns = group.transactions;
    if (txns.length < 2) continue;

    const zips = [...new Set(txns.map((t) => t.zip).filter(Boolean))];
    const markets = [...new Set(txns.map((t) => t.source_county).filter(Boolean))];
    const cashTxns = txns.filter((t) => t.cash_flag);

    const prices = txns
      .map((t) => t.consideration)
      .filter((p) => p !== null && p > 0);

    const sortedDates = txns
      .map((t) => t.document_date)
      .filter(Boolean)
      .sort();

    const { type, strategy } = classifyEntity(group.fullName);

    const entity = {
      normalized_key: normalizedKey,
      name: group.fullName,
      type,
      strategy,
      purchase_count: txns.length,
      cash_purchases: cashTxns.length,
      zips,
      markets,
      min_price: prices.length > 0 ? Math.min(...prices) : null,
      max_price: prices.length > 0 ? Math.max(...prices) : null,
      last_purchase_date: sortedDates.length > 0 ? sortedDates[sortedDates.length - 1] : null,
      signal_strength: null, // computed below
      transactions: txns,
    };

    entity.signal_strength = scoreSignal(entity);
    buyers.push(entity);
  }

  // Sort by purchase_count descending, then cash_purchases descending
  buyers.sort((a, b) => {
    if (b.purchase_count !== a.purchase_count) return b.purchase_count - a.purchase_count;
    return b.cash_purchases - a.cash_purchases;
  });

  const stats = {
    total_transactions: deduped.length,
    total_buyers_found: buyers.length,
    by_signal: {
      HIGH: buyers.filter((b) => b.signal_strength === 'HIGH').length,
      MEDIUM: buyers.filter((b) => b.signal_strength === 'MEDIUM').length,
      LOW: buyers.filter((b) => b.signal_strength === 'LOW').length,
    },
    by_type: {
      flipper: buyers.filter((b) => b.type === 'flipper').length,
      landlord: buyers.filter((b) => b.type === 'landlord').length,
      builder: buyers.filter((b) => b.type === 'builder').length,
    },
    by_market: {},
  };

  for (const result of scraperResults) {
    if (!result) continue;
    stats.by_market[result.county] = {
      records_pulled: result.transactions?.length ?? 0,
      errors: result.errors ?? [],
    };
  }

  return { buyers, stats };
}

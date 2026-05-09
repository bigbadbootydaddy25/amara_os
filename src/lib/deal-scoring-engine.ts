import distressedPortfolios from '../../data/DISTRESSED_PORTFOLIOS.json';
import overleveragedBuyers from '../../data/OVERLEVERAGED_BUYERS.json';
import stalledBuilders from '../../data/STALLED_BUILDERS.json';

// ─── Domain types ──────────────────────────────────────────────────────────────

export type DealSide = 'acquisition' | 'disposition' | 'jv' | 'land';
export type BuilderRole = 'qualified_buyer' | 'motivated_seller' | 'cautious_seller';

export interface SourceEvidence {
  dataset: string;
  record_id: string;
  signals: string[];
  raw_score: number;
  intel_date?: string;
}

export interface SellerOpportunityResult {
  base_score: number;
  distress_boost: number;
  final_score: number;
  distress_match: boolean;
  motivation_signals: string[];
  evidence: SourceEvidence | null;
}

export interface BuyerPriorityResult {
  base_score: number;
  leverage_penalty: number;
  final_score: number;
  dispo_priority: 'high' | 'standard' | 'downgraded' | 'disqualified';
  risk_flags: string[];
  evidence: SourceEvidence | null;
}

export interface BuilderRoleResult {
  classified_role: BuilderRole;
  stall_score: number;
  qualified_as_buyer: boolean;
  motivation_signals: string[];
  evidence: SourceEvidence | null;
}

export interface DealScore {
  deal_id: string;
  deal_side: DealSide;
  counterparty_id: string;
  counterparty_name: string;
  seller_opportunity?: SellerOpportunityResult;
  buyer_priority?: BuyerPriorityResult;
  builder_role?: BuilderRoleResult;
  composite_score: number;
  recommendation: string;
  scored_at: string;
}

// ─── Seller-side: boost opportunity when owner portfolio is distressed ─────────

export function scoreSellerOpportunity(
  ownerId: string,
  baseScore: number = 50,
): SellerOpportunityResult {
  const portfolio = distressedPortfolios.portfolios.find((p) => p.id === ownerId);

  if (!portfolio) {
    return {
      base_score: baseScore,
      distress_boost: 0,
      final_score: baseScore,
      distress_match: false,
      motivation_signals: [],
      evidence: null,
    };
  }

  // Scale boost: distress_score 0–100 → max +40 boost at 100
  const distressBoost = Math.round((portfolio.distress_score / 100) * 40);
  const finalScore = Math.min(100, baseScore + distressBoost);

  return {
    base_score: baseScore,
    distress_boost: distressBoost,
    final_score: finalScore,
    distress_match: true,
    motivation_signals: portfolio.motivation_signals,
    evidence: {
      dataset: 'DISTRESSED_PORTFOLIOS',
      record_id: portfolio.id,
      signals: [
        `distress_score: ${portfolio.distress_score}`,
        `weighted_vacancy: ${(portfolio.distress_indicators.weighted_vacancy_rate * 100).toFixed(0)}%`,
        `DSCR: ${portfolio.distress_indicators.debt_service_coverage_ratio}`,
        `delinquency_days: ${portfolio.distress_indicators.loan_delinquency_days}`,
        `foreclosure_notices: ${portfolio.distress_indicators.foreclosure_notices}`,
        `maturity_wall_months: ${portfolio.distress_indicators.maturity_wall_months}`,
      ],
      raw_score: portfolio.distress_score,
      intel_date: portfolio.source_evidence.market_intel_date,
    },
  };
}

// ─── Buyer-side: downgrade priority when buyer is overleveraged ───────────────

export function scoreBuyerPriority(
  buyerId: string,
  baseScore: number = 50,
): BuyerPriorityResult {
  const buyer = overleveragedBuyers.buyers.find((b) => b.id === buyerId);

  if (!buyer) {
    return {
      base_score: baseScore,
      leverage_penalty: 0,
      final_score: baseScore,
      dispo_priority: 'standard',
      risk_flags: [],
      evidence: null,
    };
  }

  // Scale penalty: leverage_score 0–100 → max -45 penalty at 100
  const leveragePenalty = Math.round((buyer.leverage_score / 100) * 45);
  const finalScore = Math.max(0, baseScore - leveragePenalty);

  let dispoPriority: BuyerPriorityResult['dispo_priority'];
  if (buyer.leverage_score >= 80) {
    dispoPriority = 'disqualified';
  } else if (buyer.leverage_score >= 60) {
    dispoPriority = 'downgraded';
  } else if (buyer.leverage_score >= 35) {
    dispoPriority = 'standard';
  } else {
    dispoPriority = 'high';
  }

  return {
    base_score: baseScore,
    leverage_penalty: leveragePenalty,
    final_score: finalScore,
    dispo_priority: dispoPriority,
    risk_flags: buyer.risk_flags,
    evidence: {
      dataset: 'OVERLEVERAGED_BUYERS',
      record_id: buyer.id,
      signals: [
        `leverage_score: ${buyer.leverage_score}`,
        `portfolio_ltv: ${(buyer.leverage_indicators.portfolio_ltv * 100).toFixed(0)}%`,
        `debt_to_equity: ${buyer.leverage_indicators.debt_to_equity_ratio}`,
        `interest_coverage: ${buyer.leverage_indicators.interest_coverage_ratio}`,
        `loans_in_extension: ${buyer.leverage_indicators.loans_in_extension}`,
        `escrow_failures_12mo: ${buyer.acquisition_posture.deals_fallen_out_of_escrow_12mo}`,
      ],
      raw_score: buyer.leverage_score,
      intel_date: buyer.source_evidence.intel_date,
    },
  };
}

// ─── Builder classification: stalled → motivated seller, not buyer ────────────

export function classifyBuilderRole(builderId: string): BuilderRoleResult {
  const builder = stalledBuilders.builders.find((b) => b.id === builderId);

  if (!builder) {
    return {
      classified_role: 'qualified_buyer',
      stall_score: 0,
      qualified_as_buyer: true,
      motivation_signals: [],
      evidence: null,
    };
  }

  const role = builder.role_classification as BuilderRole;
  const qualifiedAsBuyer = role === 'qualified_buyer';

  return {
    classified_role: role,
    stall_score: builder.stall_score,
    qualified_as_buyer: qualifiedAsBuyer,
    motivation_signals: builder.motivation_signals,
    evidence: {
      dataset: 'STALLED_BUILDERS',
      record_id: builder.id,
      signals: [
        `stall_score: ${builder.stall_score}`,
        `role: ${builder.role_classification}`,
        `disqualification: ${builder.buyer_disqualification_reason}`,
        `mechanic_liens_filed: ${builder.financial_distress.mechanic_liens_filed}`,
        `construction_loan_status: ${builder.financial_distress.construction_loan_status}`,
        `cost_gap: $${builder.financial_distress.estimated_completion_cost_gap.toLocaleString()}`,
      ],
      raw_score: builder.stall_score,
      intel_date: builder.stalled_projects[0]
        ? builder.source_evidence.intel_date
        : undefined,
    },
  };
}

// ─── Composite deal scorer ────────────────────────────────────────────────────

export interface ScoringInput {
  deal_id: string;
  deal_side: DealSide;
  counterparty_id: string;
  counterparty_name: string;
  base_score?: number;
}

export function scoreDeal(input: ScoringInput): DealScore {
  const base = input.base_score ?? 50;
  const now = new Date().toISOString();

  // Seller side: check if counterparty owns a distressed portfolio
  if (input.deal_side === 'acquisition' || input.deal_side === 'land') {
    const sellerResult = scoreSellerOpportunity(input.counterparty_id, base);
    const recommendation = buildSellerRecommendation(sellerResult);

    return {
      deal_id: input.deal_id,
      deal_side: input.deal_side,
      counterparty_id: input.counterparty_id,
      counterparty_name: input.counterparty_name,
      seller_opportunity: sellerResult,
      composite_score: sellerResult.final_score,
      recommendation,
      scored_at: now,
    };
  }

  // Buyer/dispo side: check if buyer is overleveraged or a stalled builder
  if (input.deal_side === 'disposition') {
    const buyerResult = scoreBuyerPriority(input.counterparty_id, base);

    // Check whether this buyer is actually a stalled builder masquerading as a buyer
    const builderResult = classifyBuilderRole(input.counterparty_id);
    const isBuilder = builderResult.evidence !== null;

    let compositeScore = buyerResult.final_score;
    let recommendation: string;

    if (isBuilder && !builderResult.qualified_as_buyer) {
      // Stalled builder: redirect as motivated seller, not a buyer
      compositeScore = 0;
      recommendation = buildStalledBuilderRecommendation(builderResult);
    } else {
      recommendation = buildBuyerRecommendation(buyerResult);
    }

    return {
      deal_id: input.deal_id,
      deal_side: input.deal_side,
      counterparty_id: input.counterparty_id,
      counterparty_name: input.counterparty_name,
      buyer_priority: buyerResult,
      builder_role: isBuilder ? builderResult : undefined,
      composite_score: compositeScore,
      recommendation,
      scored_at: now,
    };
  }

  // JV: check all three datasets and surface whichever signal is strongest
  const sellerResult = scoreSellerOpportunity(input.counterparty_id, base);
  const buyerResult = scoreBuyerPriority(input.counterparty_id, base);
  const builderResult = classifyBuilderRole(input.counterparty_id);

  const hasDistress = sellerResult.distress_match;
  const hasLeverage = buyerResult.evidence !== null;
  const isBuilder = builderResult.evidence !== null;

  const compositeScore = hasDistress
    ? sellerResult.final_score
    : hasLeverage
      ? buyerResult.final_score
      : base;

  const recommendation = isBuilder && !builderResult.qualified_as_buyer
    ? buildStalledBuilderRecommendation(builderResult)
    : hasDistress
      ? buildSellerRecommendation(sellerResult)
      : hasLeverage
        ? buildBuyerRecommendation(buyerResult)
        : 'No distress signals found — score based on standard underwriting.';

  return {
    deal_id: input.deal_id,
    deal_side: input.deal_side,
    counterparty_id: input.counterparty_id,
    counterparty_name: input.counterparty_name,
    seller_opportunity: hasDistress ? sellerResult : undefined,
    buyer_priority: hasLeverage ? buyerResult : undefined,
    builder_role: isBuilder ? builderResult : undefined,
    composite_score: compositeScore,
    recommendation,
    scored_at: now,
  };
}

// ─── Recommendation builders ──────────────────────────────────────────────────

function buildSellerRecommendation(result: SellerOpportunityResult): string {
  if (!result.distress_match) {
    return 'No portfolio distress signals — evaluate on standard fundamentals.';
  }
  if (result.final_score >= 80) {
    return (
      `HIGH OPPORTUNITY — seller portfolio distress is severe (score ${result.evidence?.raw_score}/100). ` +
      `Prioritise outreach and structure for speed. ${result.motivation_signals[0] ?? ''}`
    );
  }
  if (result.final_score >= 65) {
    return (
      `ELEVATED OPPORTUNITY — meaningful distress detected (score ${result.evidence?.raw_score}/100). ` +
      `Engage with creative structuring. ${result.motivation_signals[0] ?? ''}`
    );
  }
  return (
    `MODERATE OPPORTUNITY — early-stage distress (score ${result.evidence?.raw_score}/100). ` +
    `Monitor cadence and maintain relationship.`
  );
}

function buildBuyerRecommendation(result: BuyerPriorityResult): string {
  if (result.dispo_priority === 'disqualified') {
    return (
      `DO NOT PRIORITISE — buyer is severely overleveraged (leverage score ${result.evidence?.raw_score}/100). ` +
      `High escrow failure risk. ${result.risk_flags[0] ?? ''}`
    );
  }
  if (result.dispo_priority === 'downgraded') {
    return (
      `DOWNGRADED — buyer carries significant leverage risk (score ${result.evidence?.raw_score}/100). ` +
      `Require proof of funds and shorter contingency periods. ${result.risk_flags[0] ?? ''}`
    );
  }
  if (result.dispo_priority === 'standard') {
    return `STANDARD — buyer leverage is manageable. Proceed with normal diligence.`;
  }
  return `HIGH PRIORITY BUYER — clean balance sheet and strong close track record.`;
}

function buildStalledBuilderRecommendation(result: BuilderRoleResult): string {
  return (
    `RECLASSIFY AS SELLER — this builder is stalled (stall score ${result.stall_score}/100) and should be ` +
    `treated as a motivated seller, not a buyer. ${result.motivation_signals[0] ?? ''} ` +
    `Source: ${result.evidence?.dataset} [${result.evidence?.record_id}]`
  );
}

// ─── Batch utilities ──────────────────────────────────────────────────────────

export function getDistressedPortfolioIds(): string[] {
  return distressedPortfolios.portfolios.map((p) => p.id);
}

export function getOverleveragedBuyerIds(): string[] {
  return overleveragedBuyers.buyers
    .filter((b) => b.leverage_score >= 60)
    .map((b) => b.id);
}

export function getStalledBuilderIds(): string[] {
  return stalledBuilders.builders
    .filter((b) => b.role_classification !== 'qualified_buyer')
    .map((b) => b.id);
}

export function scoreAllDistressedPortfolios(baseScore = 50): DealScore[] {
  return distressedPortfolios.portfolios.map((p) =>
    scoreDeal({
      deal_id: `AUTO-${p.id}`,
      deal_side: 'acquisition',
      counterparty_id: p.id,
      counterparty_name: p.owner,
      base_score: baseScore,
    }),
  );
}

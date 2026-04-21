import type { DealType, DealAnalysis } from '@/types/real-estate';

interface WholesaleInput {
  arv: number;
  repairEstimate: number;
  assignmentFee?: number;
}

interface DeadPaperInput {
  lotYield: number;
  builderResalePerLot: number;
  infrastructureCostEstimate: number;
  acquisitionCost: number;
  entitlementRisk?: 'low' | 'medium' | 'high';
}

interface BrrrrInput {
  arv: number;
  repairEstimate: number;
  monthlyRent: number;
  acquisitionCost: number;
}

const ENTITLEMENT_RISK_DISCOUNT: Record<string, number> = {
  low: 0.95,
  medium: 0.85,
  high: 0.70,
};

export function analyzeWholesale(input: WholesaleInput): DealAnalysis {
  const assignmentFee = input.assignmentFee ?? 10000;
  const mao = input.arv * 0.7 - input.repairEstimate - assignmentFee;
  return {
    dealType: 'wholesale',
    arv: input.arv,
    repairEstimate: input.repairEstimate,
    assignmentFee,
    mao: Math.max(mao, 0),
    spread: assignmentFee,
  };
}

export function analyzeFixAndFlip(input: WholesaleInput): DealAnalysis {
  const assignmentFee = input.assignmentFee ?? 15000;
  const mao = input.arv * 0.7 - input.repairEstimate - assignmentFee;
  const holdingCosts = input.arv * 0.05;
  const spread = input.arv - (mao + input.repairEstimate + holdingCosts + assignmentFee);
  return {
    dealType: 'fix_and_flip',
    arv: input.arv,
    repairEstimate: input.repairEstimate,
    assignmentFee,
    mao: Math.max(mao, 0),
    spread: Math.max(spread, 0),
  };
}

export function analyzeDeadPaper(input: DeadPaperInput): DealAnalysis {
  const riskDiscount = ENTITLEMENT_RISK_DISCOUNT[input.entitlementRisk ?? 'medium'];
  const grossRevenue = input.lotYield * input.builderResalePerLot * riskDiscount;
  const totalCosts = input.acquisitionCost + input.infrastructureCostEstimate;
  const spread = grossRevenue - totalCosts;
  return {
    dealType: 'dead_paper',
    lotYield: input.lotYield,
    builderResalePerLot: input.builderResalePerLot,
    infrastructureCostEstimate: input.infrastructureCostEstimate,
    entitlementRisk: input.entitlementRisk ?? 'medium',
    totalProjectedRevenue: grossRevenue,
    acquisitionCost: input.acquisitionCost,
    developmentCost: input.infrastructureCostEstimate,
    spread: Math.max(spread, 0),
  };
}

export function analyzeBrrrr(input: BrrrrInput): DealAnalysis {
  const annualRent = input.monthlyRent * 12;
  const rentalYield = input.arv > 0 ? (annualRent / input.arv) * 100 : 0;
  const mao = input.arv * 0.75 - input.repairEstimate;
  return {
    dealType: 'brrrr',
    arv: input.arv,
    repairEstimate: input.repairEstimate,
    mao: Math.max(mao, 0),
    monthlyRent: input.monthlyRent,
    rentalYield,
    spread: Math.max(input.arv - input.acquisitionCost - input.repairEstimate, 0),
  };
}

export function analyzeDeal(
  type: DealType,
  params: Record<string, number | string>,
): DealAnalysis {
  const n = (k: string) => Number(params[k] ?? 0);
  const s = (k: string) => String(params[k] ?? '');

  switch (type) {
    case 'wholesale':
      return analyzeWholesale({
        arv: n('arv'),
        repairEstimate: n('repairEstimate'),
        assignmentFee: n('assignmentFee') || undefined,
      });
    case 'fix_and_flip':
      return analyzeFixAndFlip({
        arv: n('arv'),
        repairEstimate: n('repairEstimate'),
        assignmentFee: n('assignmentFee') || undefined,
      });
    case 'dead_paper':
      return analyzeDeadPaper({
        lotYield: n('lotYield'),
        builderResalePerLot: n('builderResalePerLot'),
        infrastructureCostEstimate: n('infrastructureCostEstimate'),
        acquisitionCost: n('acquisitionCost'),
        entitlementRisk: (s('entitlementRisk') || 'medium') as 'low' | 'medium' | 'high',
      });
    case 'brrrr':
      return analyzeBrrrr({
        arv: n('arv'),
        repairEstimate: n('repairEstimate'),
        monthlyRent: n('monthlyRent'),
        acquisitionCost: n('acquisitionCost'),
      });
  }
}

import type { DealType, DealAnalysis, OfferTerms } from '@/types/real-estate';

export function generateOffer(dealType: DealType, analysis: DealAnalysis): OfferTerms {
  switch (dealType) {
    case 'wholesale':
      return {
        offerPrice: analysis.mao ?? 0,
        closingDays: 14,
        isAllCash: true,
        isAsIs: true,
        hasAssignmentClause: true,
        contingencies: [],
        strategy: 'direct',
        notes: `Assignment fee target: $${(analysis.assignmentFee ?? 10000).toLocaleString()}`,
      };

    case 'fix_and_flip':
      return {
        offerPrice: analysis.mao ?? 0,
        closingDays: 21,
        isAllCash: true,
        isAsIs: true,
        hasAssignmentClause: true,
        inspectionDays: 10,
        contingencies: ['inspection'],
        strategy: 'direct',
        notes: `Target ARV: $${(analysis.arv ?? 0).toLocaleString()} | Repair budget: $${(analysis.repairEstimate ?? 0).toLocaleString()}`,
      };

    case 'dead_paper':
      return {
        offerPrice: analysis.acquisitionCost ?? 0,
        closingDays: 60,
        isAllCash: false,
        isAsIs: true,
        hasAssignmentClause: true,
        inspectionDays: 30,
        contingencies: ['entitlement review', 'plat verification', 'survey'],
        strategy: 'option',
        notes: `Target spread: $${(analysis.spread ?? 0).toLocaleString()} | Lot yield: ${analysis.lotYield ?? 0} lots @ $${(analysis.builderResalePerLot ?? 0).toLocaleString()}/lot`,
      };

    case 'brrrr':
      return {
        offerPrice: analysis.mao ?? 0,
        closingDays: 21,
        isAllCash: true,
        isAsIs: true,
        hasAssignmentClause: false,
        inspectionDays: 14,
        contingencies: ['inspection', 'financing'],
        strategy: 'direct',
        notes: `Target rent: $${(analysis.monthlyRent ?? 0).toLocaleString()}/mo | Yield: ${(analysis.rentalYield ?? 0).toFixed(1)}%`,
      };
  }
}

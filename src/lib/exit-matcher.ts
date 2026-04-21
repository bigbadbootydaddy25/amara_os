import type { Buyer, Property, ExitMatch, DealType } from '@/types/real-estate';

function zipOverlap(propertyZip: string, buyerZips: string[]): boolean {
  return buyerZips.includes(propertyZip);
}

function priceInRange(price: number, buyer: Buyer): boolean {
  return price >= buyer.buyBox.minPrice && price <= buyer.buyBox.maxPrice;
}

function dealTypeMatchesBuyerType(dealType: DealType, buyer: Buyer): boolean {
  switch (dealType) {
    case 'dead_paper':
      return buyer.type === 'builder' || buyer.type === 'developer';
    case 'fix_and_flip':
      return buyer.type === 'flipper' || buyer.type === 'wholesaler';
    case 'brrrr':
      return buyer.type === 'landlord';
    case 'wholesale':
      return true;
  }
}

export function scoreMatch(property: Property, buyer: Buyer): number {
  let score = 0;
  const reasons: string[] = [];

  if (zipOverlap(property.zip, buyer.activeZips)) {
    score += 40;
    reasons.push('Active ZIP match');
  }

  const exitPrice = property.analysis?.arv ?? property.listingPrice ?? 0;
  if (priceInRange(exitPrice, buyer)) {
    score += 25;
    reasons.push('Price range match');
  }

  if (property.dealType && dealTypeMatchesBuyerType(property.dealType, buyer)) {
    score += 20;
    reasons.push('Deal type match');
  }

  if (buyer.purchases24mo >= 3) {
    score += 10;
    reasons.push('Active buyer (3+ purchases / 24mo)');
  }

  score += Math.min(buyer.confidenceScore * 5, 5);

  return Math.min(score, 100);
}

export function findBestMatches(property: Property, buyers: Buyer[], topN = 3): ExitMatch[] {
  const dealType = property.dealType ?? 'wholesale';
  const exitPrice = property.analysis?.arv ?? property.listingPrice ?? 0;

  const scored = buyers
    .filter((b) => dealTypeMatchesBuyerType(dealType, b))
    .map((buyer) => {
      const confidence = scoreMatch(property, buyer);
      const reasons: string[] = [];
      if (zipOverlap(property.zip, buyer.activeZips)) reasons.push('ZIP active');
      if (priceInRange(exitPrice, buyer)) reasons.push('Price range fit');
      if (dealTypeMatchesBuyerType(dealType, buyer)) reasons.push('Strategy match');
      if (buyer.purchases24mo >= 3) reasons.push('High purchase velocity');

      return {
        buyerId: buyer.id,
        buyerName: buyer.llcName ?? buyer.name,
        confidenceScore: confidence,
        expectedExitPrice: exitPrice,
        matchReasons: reasons,
      } satisfies ExitMatch;
    })
    .sort((a, b) => b.confidenceScore - a.confidenceScore)
    .slice(0, topN);

  return scored;
}

import type { DealType, OsintReport, DeadPaperFlags } from '@/types/real-estate';

interface ClassifierInput {
  deadPaperScore: number;
  deadPaperFlags: DeadPaperFlags;
  osint: OsintReport;
  listingDescription?: string;
  parcelAcres?: number;
  hasRentalIncome?: boolean;
  estimatedRepairs?: number;
  arv?: number;
}

export function classifyDeal(input: ClassifierInput): DealType {
  const {
    deadPaperScore,
    deadPaperFlags,
    osint,
    parcelAcres = 0,
    hasRentalIncome = false,
    estimatedRepairs = 0,
    arv = 0,
  } = input;

  // Dead paper / development signals take top priority
  const hasSubdivisionSignals =
    osint.recordedPlats && osint.recordedPlats.length > 0;
  const hasEntitlement =
    osint.entitlementStatus && osint.entitlementStatus !== 'none';
  const isLargeAcreage = parcelAcres > 1;
  const hasInfrastructureSignals =
    osint.ghostStreets || osint.partialInfrastructure;

  if (
    deadPaperScore >= 4 ||
    hasSubdivisionSignals ||
    hasEntitlement ||
    isLargeAcreage ||
    hasInfrastructureSignals ||
    deadPaperFlags.inBuilderExpansionZone
  ) {
    return 'dead_paper';
  }

  // Rental / BRRRR: has income potential and moderate repairs
  if (hasRentalIncome || (arv > 0 && estimatedRepairs / arv < 0.2)) {
    return 'brrrr';
  }

  // Fix & Flip: significant cosmetic/structural upside
  if (arv > 0 && estimatedRepairs > 0) {
    return 'fix_and_flip';
  }

  // Default: wholesale
  return 'wholesale';
}

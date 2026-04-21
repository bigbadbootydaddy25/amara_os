// ============================================================
// AMARA-AI — Real Estate Types
// ============================================================

export type BuyerType = 'builder' | 'flipper' | 'landlord' | 'developer' | 'wholesaler';

export type DealType = 'wholesale' | 'fix_and_flip' | 'brrrr' | 'dead_paper';

export type DealStatus =
  | 'new'
  | 'investigating'
  | 'verified'
  | 'offer_ready'
  | 'offer_sent'
  | 'under_contract'
  | 'closed'
  | 'dead';

export type OsintStatus = 'pending' | 'in_progress' | 'complete' | 'failed';

export interface BuyBox {
  minPrice: number;
  maxPrice: number;
  propertyTypes: string[];
  strategy: string;
  minBeds?: number;
  minBaths?: number;
  minLotAcres?: number;
  maxRepairBudget?: number;
}

export interface Buyer {
  id: string;
  name: string;
  llcName?: string;
  email?: string;
  phone?: string;
  type: BuyerType;
  buyBox: BuyBox;
  activeZips: string[];
  purchases24mo: number;
  purchases36mo: number;
  strategy: string;
  notes?: string;
  confidenceScore: number;
  createdAt: string;
  updatedAt: string;
}

export interface DeadPaperFlags {
  hasLotNumbering: boolean;
  hasMultipleNearbyListings: boolean;
  hasPlaceholderAddress: boolean;
  isOversizedParcel: boolean;
  inBuilderExpansionZone: boolean;
  hasIrregularShape: boolean;
}

export interface OsintReport {
  status: OsintStatus;
  parcelId?: string;
  apn?: string;
  legalDescription?: string;
  owner?: string;
  ownerState?: string;
  ownerIsLlc?: boolean;
  taxDelinquent?: boolean;
  holdYears?: number;
  zoningCode?: string;
  rezoningHistory?: string[];
  recordedPlats?: string[];
  permitHistory?: string[];
  ghostStreets?: boolean;
  partialInfrastructure?: boolean;
  expansionPressure?: boolean;
  entitlementStatus?: 'none' | 'pending' | 'approved' | 'expired';
  infrastructureStatus?: 'none' | 'partial' | 'complete';
  ownershipPressure?: 'low' | 'medium' | 'high';
  completedAt?: string;
  rawGisUrl?: string;
  rawPlatUrl?: string;
  rawZoningUrl?: string;
}

export interface DealAnalysis {
  dealType: DealType;
  arv?: number;
  repairEstimate?: number;
  assignmentFee?: number;
  mao?: number;
  // Dead paper / development
  lotYield?: number;
  builderResalePerLot?: number;
  infrastructureCostEstimate?: number;
  entitlementRisk?: 'low' | 'medium' | 'high';
  totalProjectedRevenue?: number;
  acquisitionCost?: number;
  developmentCost?: number;
  spread?: number;
  // BRRRR
  monthlyRent?: number;
  rentalYield?: number;
}

export interface ExitMatch {
  buyerId: string;
  buyerName: string;
  confidenceScore: number;
  expectedExitPrice: number;
  matchReasons: string[];
}

export interface OfferTerms {
  offerPrice: number;
  closingDays: number;
  isAllCash: boolean;
  isAsIs: boolean;
  hasAssignmentClause: boolean;
  inspectionDays?: number;
  contingencies: string[];
  strategy: 'loi' | 'option' | 'double_close' | 'direct';
  notes?: string;
}

export interface Property {
  id: string;
  address: string;
  city: string;
  state: string;
  zip: string;
  apn?: string;
  listingPrice?: number;
  listingSource?: string;
  listingUrl?: string;
  listingKeywords: string[];
  deadPaperScore: number;
  deadPaperFlags: DeadPaperFlags;
  dealType?: DealType;
  dealStatus: DealStatus;
  osint: OsintReport;
  analysis?: DealAnalysis;
  exitMatch?: ExitMatch;
  offerTerms?: OfferTerms;
  notes?: string;
  createdAt: string;
  updatedAt: string;
}

export interface TopDealSummary {
  property: Property;
  type: DealType;
  score: number;
  arvOrValue: number;
  cost: number;
  spread: number;
  exitBuyer?: string;
  strategy: string;
}

export interface ScanResult {
  scannedAt: string;
  candidatesFound: number;
  priorityTargets: number;
  newProperties: Property[];
}

export interface AutomationState {
  lastScanAt?: string;
  isRunning: boolean;
  currentStep?: string;
  log: string[];
}

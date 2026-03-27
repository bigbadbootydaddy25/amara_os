export interface Deal {
  id: number;
  address: string | null;
  city: string | null;
  state: string | null;
  zip: string | null;
  county: string | null;
  propertyType: string | null;
  beds: number | null;
  baths: string | null;
  sqft: number | null;
  lotSqft: number | null;
  yearBuilt: number | null;
  askingPrice: string | null;
  arv: string | null;
  estimatedRehab: string | null;
  maxAllowableOffer: string | null;
  roiPct: string | null;
  equityPct: string | null;
  comps: unknown;
  source: string | null;
  importBatchId: string | null;
  status: string | null;
  pipelineStage: string | null;
  assignedTo: string | null;
  notes: string | null;
  createdAt: string | null;
}

export interface DealMatchRow {
  matchId: number;
  buyerId: number;
  matchScore: number;
  matchReasons: MatchReason[];
  isSent: boolean;
  sentAt: string | null;
  buyerName: string | null;
  buyerEmail: string | null;
  buyerPhone: string | null;
  buyerCompany: string | null;
  dealBeds: number | null;
  dealBaths: string | null;
  dealPrice: string | null;
  label: string;
}

export interface MatchReason {
  field: string;
  weight: number;
  earned: number;
  note: string;
}

export interface Buyer {
  id: number;
  name: string;
  email: string | null;
  phone: string | null;
  company: string | null;
  propertyTypes: string[] | null;
  bedsMin: number | null;
  bedsMax: number | null;
  bathsMin: string | null;
  bathsMax: string | null;
  sqftMin: number | null;
  sqftMax: number | null;
  priceMin: string | null;
  priceMax: string | null;
  arvMin: string | null;
  arvMax: string | null;
  maxRehab: string | null;
  minRoiPct: string | null;
  zipCodes: string[] | null;
  states: string[] | null;
  isActive: boolean;
  notes: string | null;
}

export interface DealStats {
  totalDeals: number;
  totalBuyers: number;
  totalMatches: number;
  avgScore: number;
  topMatches: number;
}

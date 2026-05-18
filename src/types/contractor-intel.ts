// ---------------------------------------------------------------------------
// Contractor & Relationship Intelligence — type system
// NO FAKE DATA. NO SIMULATED CONTACTS. ONLY VERIFIED OSINT.
// ---------------------------------------------------------------------------

export type EntityType =
  | 'prime-contractor'
  | 'subcontractor'
  | 'supplier'
  | 'logistics'
  | 'broker'
  | 'shell-company'
  | 'holding-company'
  | 'government-agency'
  | 'financier'
  | 'unknown';

export type FuelCategory =
  | 'aviation'
  | 'marine'
  | 'military'
  | 'trucking'
  | 'industrial'
  | 'power-generation'
  | 'municipal'
  | 'emergency-response'
  | 'international-trade';

export type AlertPriority = 'high' | 'medium' | 'low';

export type AlertType =
  | 'expiring-contract'
  | 'emergency-fuel-request'
  | 'supplier-failure'
  | 'sanctions-disruption'
  | 'refinery-outage'
  | 'military-demand-spike'
  | 'shipping-disruption'
  | 'geopolitical-instability'
  | 'new-procurement-posting';

export type ContactRole =
  | 'procurement'
  | 'sales'
  | 'logistics'
  | 'business-development'
  | 'operations'
  | 'fuel-desk'
  | 'terminal-manager'
  | 'contract-officer'
  | 'executive'
  | 'finance';

export type AuthorityLevel = 'decision-maker' | 'influencer' | 'gatekeeper' | 'staff';

export type RelationshipType =
  | 'awards'
  | 'subcontracts-to'
  | 'supplies'
  | 'finances'
  | 'brokers-for'
  | 'provides-logistics'
  | 'parent-of'
  | 'subsidiary-of'
  | 'facilitates'
  | 'recurring-buyer'
  | 'recurring-seller';

export type RebidRisk = 'low' | 'medium' | 'high';

// ---------------------------------------------------------------------------
// Contacts
// ---------------------------------------------------------------------------

export interface ContractorContact {
  name: string;
  title: string;
  email: string | null;
  phone: string | null;
  officePhone: string | null;
  linkedIn: string | null;
  role: ContactRole;
  authorityLevel: AuthorityLevel;
  sourceUrl: string;
  sourceName: string;
  verified: boolean;
}

// ---------------------------------------------------------------------------
// Contracts (from SAM.gov / FPDS / USASpending.gov)
// ---------------------------------------------------------------------------

export interface ContractRecord {
  contractNumber: string;
  piid: string | null;
  title: string;
  awardedDate: string;
  expirationDate: string | null;
  baseValue: number;
  totalObligatedValue: number;
  agencyName: string;
  agencyCode: string;
  subAgencyName: string | null;
  primeContractorName: string;
  primeContractorCage: string | null;
  primeContractorUei: string | null;
  placeOfPerformanceCity: string;
  placeOfPerformanceState: string;
  placeOfPerformanceCountry: string;
  naicsCode: string;
  naicsDescription: string;
  productServiceCode: string;
  setAsideType: string | null;
  competitionType: string | null;
  description: string;
  sourceUrl: string;
  daysUntilExpiration: number | null;
}

// ---------------------------------------------------------------------------
// Relationships (edges in the network graph)
// ---------------------------------------------------------------------------

export interface RelationshipEdge {
  id: string;
  fromEntityId: string;
  fromEntityName: string;
  toEntityId: string;
  toEntityName: string;
  relationshipType: RelationshipType;
  contractNumbers: string[];
  estimatedAnnualValue: number | null;
  firstSeenDate: string;
  lastSeenDate: string;
  occurrenceCount: number;
  sourceUrls: string[];
}

// ---------------------------------------------------------------------------
// Buy Box — what an entity purchases
// ---------------------------------------------------------------------------

export interface BuyBox {
  categories: FuelCategory[];
  productTypes: string[];
  minimumShipmentSizeGallons: number | null;
  monthlyDemandEstimateGallons: number | null;
  yearlyDemandEstimateGallons: number | null;
  preferredRegions: string[];
  preferredDeliveryMethods: string[];
  storageCapabilityGallons: number | null;
  estimatedAnnualBudget: number | null;
  contractThresholdSAT: boolean;
  currentPainPoints: string[];
  emergencyNeedIndicators: string[];
  procurementCycle: string | null;
}

// ---------------------------------------------------------------------------
// Incumbent vendor analysis
// ---------------------------------------------------------------------------

export interface IncumbentVendor {
  vendorName: string;
  vendorCage: string | null;
  vendorUei: string | null;
  relationshipStartDate: string | null;
  estimatedAnnualValue: number | null;
  knownComplaints: string[];
  performanceIssues: string[];
  deliveryIssues: string[];
  contractDisputes: string[];
  rebidRisk: RebidRisk;
  contractExpirationDate: string | null;
  supplyVulnerabilities: string[];
  sourceUrls: string[];
}

// ---------------------------------------------------------------------------
// Opportunity scoring (all 0–100)
// ---------------------------------------------------------------------------

export interface OpportunityScores {
  relationshipScore: number;
  buyerScore: number;
  supplierScore: number;
  facilitationScore: number;
  riskScore: number;
  accessScore: number;
  compositeScore: number;
}

// ---------------------------------------------------------------------------
// Alerts
// ---------------------------------------------------------------------------

export interface ContractAlert {
  id: string;
  priority: AlertPriority;
  type: AlertType;
  title: string;
  description: string;
  entityId: string;
  entityName: string;
  contractNumber: string | null;
  detectedAt: string;
  expirationDate: string | null;
  daysUntilExpiration: number | null;
  actionRequired: string;
  sourceUrl: string;
}

// ---------------------------------------------------------------------------
// Core entity
// ---------------------------------------------------------------------------

export interface ContractorEntity {
  id: string;
  name: string;
  entityType: EntityType;
  cageCode: string | null;
  ueiSam: string | null;
  dunsNumber: string | null;
  ein: string | null;
  address: string | null;
  city: string | null;
  state: string | null;
  country: string | null;
  phone: string | null;
  website: string | null;
  samRegistered: boolean;
  samExpirationDate: string | null;
  sanctionsStatus: 'clean' | 'flagged' | 'unknown';
  sanctionsSourceUrl: string | null;
  parentCompany: string | null;
  subsidiaries: string[];
  contracts: ContractRecord[];
  contacts: ContractorContact[];
  relationships: RelationshipEdge[];
  incumbentSuppliers: IncumbentVendor[];
  buyBox: BuyBox | null;
  scores: OpportunityScores;
  alerts: ContractAlert[];
  sourceUrls: string[];
  lastUpdated: string;
}

// ---------------------------------------------------------------------------
// Contract network map (graph)
// ---------------------------------------------------------------------------

export interface ContractNetworkMap {
  rootEntityId: string;
  rootEntityName: string;
  entities: ContractorEntity[];
  edges: RelationshipEdge[];
  depth: number;
  generatedAt: string;
  totalContractValue: number;
  osintSourcesQueried: string[];
}

// ---------------------------------------------------------------------------
// API request / response shapes
// ---------------------------------------------------------------------------

export interface ContractorIntelRequest {
  query: string;
  entityType?: EntityType;
  cageCode?: string;
  ueiSam?: string;
  contractNumber?: string;
  naicsCode?: string;
  depth?: 1 | 2 | 3;
}

export interface ContractorIntelValidationResult {
  valid: boolean;
  entity?: ContractorEntity;
  errors: string[];
  warnings: string[];
  missingOsintSources: string[];
}

export interface RelationshipGraphRequest {
  entityId: string;
  depth?: 1 | 2 | 3;
  includeTypes?: RelationshipType[];
}

export interface AlertsRequest {
  entityIds?: string[];
  priorities?: AlertPriority[];
  types?: AlertType[];
  daysToExpiration?: number;
}

export interface AlertsResponse {
  alerts: ContractAlert[];
  totalCount: number;
  highCount: number;
  generatedAt: string;
}

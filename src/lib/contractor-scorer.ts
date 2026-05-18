import type {
  ContractorEntity,
  ContractorContact,
  ContractRecord,
  IncumbentVendor,
  OpportunityScores,
  RelationshipEdge,
} from '@/types/contractor-intel';

// ---------------------------------------------------------------------------
// Relationship Score — likelihood of becoming a valuable relationship
// ---------------------------------------------------------------------------

function scoreRelationship(entity: ContractorEntity): number {
  let score = 0;

  // SAM registration = verified, active entity
  if (entity.samRegistered) score += 20;

  // Has active (non-expired) contracts
  const now = Date.now();
  const activeContracts = entity.contracts.filter((c) => {
    if (!c.expirationDate) return true;
    return new Date(c.expirationDate).getTime() > now;
  });
  score += Math.min(activeContracts.length * 8, 24);

  // Recurring relationships (repeat awards or subcontracts)
  const recurringEdges = entity.relationships.filter((r) => r.occurrenceCount >= 2);
  score += Math.min(recurringEdges.length * 5, 20);

  // Has direct contacts with decision-maker authority
  const decisionMakers = entity.contacts.filter((c) => c.authorityLevel === 'decision-maker');
  score += Math.min(decisionMakers.length * 6, 18);

  // Verified contacts add confidence
  const verifiedContacts = entity.contacts.filter((c) => c.verified);
  score += Math.min(verifiedContacts.length * 3, 9);

  // Sanctions risk reduces score
  if (entity.sanctionsStatus === 'flagged') score -= 25;
  if (entity.sanctionsStatus === 'unknown') score -= 5;

  return Math.max(0, Math.min(100, score));
}

// ---------------------------------------------------------------------------
// Buyer Score — estimated purchasing power
// ---------------------------------------------------------------------------

function scoreBuyer(entity: ContractorEntity): number {
  let score = 0;

  if (!entity.buyBox) return 0;

  // Annual demand volume
  const yearlyGallons = entity.buyBox.yearlyDemandEstimateGallons ?? 0;
  if (yearlyGallons >= 10_000_000) score += 30;
  else if (yearlyGallons >= 1_000_000) score += 20;
  else if (yearlyGallons >= 100_000) score += 10;

  // Budget range
  const annualBudget = entity.buyBox.estimatedAnnualBudget ?? 0;
  if (annualBudget >= 50_000_000) score += 25;
  else if (annualBudget >= 10_000_000) score += 15;
  else if (annualBudget >= 1_000_000) score += 8;

  // Above simplified acquisition threshold = can do larger deals
  if (entity.buyBox.contractThresholdSAT) score += 15;

  // Multiple product categories = more buying needs
  score += Math.min(entity.buyBox.categories.length * 4, 16);

  // Emergency needs = premium buyer
  if (entity.buyBox.emergencyNeedIndicators.length > 0) score += 10;

  // Active contracts confirm buying power
  score += Math.min(entity.contracts.length * 2, 10);

  return Math.max(0, Math.min(100, score));
}

// ---------------------------------------------------------------------------
// Supplier Score — ability to actually deliver
// ---------------------------------------------------------------------------

function scoreSupplier(entity: ContractorEntity, edges: RelationshipEdge[]): number {
  let score = 0;

  // Has performed as prime contractor
  const primeContracts = entity.contracts.filter(
    (c) => c.primeContractorName.toLowerCase() === entity.name.toLowerCase(),
  );
  score += Math.min(primeContracts.length * 5, 25);

  // Total contract value = financial depth
  const totalValue = entity.contracts.reduce((sum, c) => sum + (c.totalObligatedValue ?? 0), 0);
  if (totalValue >= 100_000_000) score += 25;
  else if (totalValue >= 10_000_000) score += 15;
  else if (totalValue >= 1_000_000) score += 8;

  // Provides logistics (supply capability signal)
  const logisticsEdges = edges.filter(
    (e) => e.fromEntityId === entity.id && e.relationshipType === 'provides-logistics',
  );
  score += Math.min(logisticsEdges.length * 5, 15);

  // SAM registration = can receive federal contracts
  if (entity.samRegistered) score += 15;

  // Active SAM registration
  if (entity.samExpirationDate) {
    const expiry = new Date(entity.samExpirationDate).getTime();
    if (expiry > Date.now()) score += 10;
  }

  // Sanctions = serious delivery risk
  if (entity.sanctionsStatus === 'flagged') score -= 40;

  return Math.max(0, Math.min(100, score));
}

// ---------------------------------------------------------------------------
// Facilitation Score — middleman / broker opportunity likelihood
// ---------------------------------------------------------------------------

function scoreFacilitation(entity: ContractorEntity, edges: RelationshipEdge[]): number {
  let score = 0;

  const brokerEdges = edges.filter(
    (e) =>
      (e.fromEntityId === entity.id || e.toEntityId === entity.id) &&
      e.relationshipType === 'brokers-for',
  );
  score += Math.min(brokerEdges.length * 12, 36);

  // Entity type signals brokering
  if (entity.entityType === 'broker') score += 30;
  if (entity.entityType === 'logistics') score += 15;

  // Multiple relationships across different entity types = facilitator pattern
  const uniqueEntityTypes = new Set(
    edges
      .filter((e) => e.fromEntityId === entity.id || e.toEntityId === entity.id)
      .map((e) => (e.fromEntityId === entity.id ? e.toEntityId : e.fromEntityId)),
  ).size;
  score += Math.min(uniqueEntityTypes * 3, 18);

  // Shell or holding company = likely intermediary
  if (entity.entityType === 'shell-company' || entity.entityType === 'holding-company') {
    score += 20;
  }

  return Math.max(0, Math.min(100, score));
}

// ---------------------------------------------------------------------------
// Risk Score — fraud / sanctions / nonperformance risk (higher = riskier)
// ---------------------------------------------------------------------------

function scoreRisk(entity: ContractorEntity): number {
  let risk = 0;

  if (entity.sanctionsStatus === 'flagged') risk += 60;
  if (entity.sanctionsStatus === 'unknown') risk += 15;

  // Shell company or unknown entity type = higher risk
  if (entity.entityType === 'shell-company') risk += 20;
  if (entity.entityType === 'unknown') risk += 10;

  // Incumbent vendors with known complaints = delivery risk
  const vendorsWithIssues = entity.incumbentSuppliers.filter(
    (v) => v.knownComplaints.length > 0 || v.performanceIssues.length > 0,
  );
  risk += Math.min(vendorsWithIssues.length * 5, 15);

  // SAM not registered = not eligible for federal work
  if (!entity.samRegistered) risk += 10;

  // Expired SAM registration
  if (entity.samExpirationDate) {
    const expiry = new Date(entity.samExpirationDate).getTime();
    if (expiry < Date.now()) risk += 15;
  }

  // No source URLs = unverified intelligence
  if (entity.sourceUrls.length === 0) risk += 20;

  return Math.max(0, Math.min(100, risk));
}

// ---------------------------------------------------------------------------
// Access Score — ease of reaching decision makers
// ---------------------------------------------------------------------------

function scoreAccess(contacts: ContractorContact[]): number {
  let score = 0;

  const withEmail = contacts.filter((c) => c.email);
  const withPhone = contacts.filter((c) => c.phone || c.officePhone);
  const withLinkedIn = contacts.filter((c) => c.linkedIn);
  const decisionMakers = contacts.filter((c) => c.authorityLevel === 'decision-maker');

  score += Math.min(withEmail.length * 10, 30);
  score += Math.min(withPhone.length * 8, 24);
  score += Math.min(withLinkedIn.length * 5, 15);
  score += Math.min(decisionMakers.length * 10, 20);

  // Verified contacts are more reachable
  const verified = contacts.filter((c) => c.verified);
  score += Math.min(verified.length * 5, 15);

  return Math.max(0, Math.min(100, score));
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export function computeOpportunityScores(
  entity: ContractorEntity,
  allEdges: RelationshipEdge[],
): OpportunityScores {
  const relationshipScore = scoreRelationship(entity);
  const buyerScore = scoreBuyer(entity);
  const supplierScore = scoreSupplier(entity, allEdges);
  const facilitationScore = scoreFacilitation(entity, allEdges);
  const riskScore = scoreRisk(entity);
  const accessScore = scoreAccess(entity.contacts);

  const compositeScore = Math.round(
    (relationshipScore * 0.2 +
      buyerScore * 0.2 +
      supplierScore * 0.15 +
      facilitationScore * 0.1 +
      (100 - riskScore) * 0.2 +
      accessScore * 0.15),
  );

  return {
    relationshipScore,
    buyerScore,
    supplierScore,
    facilitationScore,
    riskScore,
    accessScore,
    compositeScore,
  };
}

export function detectRebidRisk(vendor: IncumbentVendor): IncumbentVendor['rebidRisk'] {
  let riskPoints = 0;

  if (vendor.knownComplaints.length >= 3) riskPoints += 3;
  else if (vendor.knownComplaints.length >= 1) riskPoints += 1;

  if (vendor.performanceIssues.length >= 2) riskPoints += 2;
  if (vendor.deliveryIssues.length >= 2) riskPoints += 2;
  if (vendor.contractDisputes.length >= 1) riskPoints += 2;
  if (vendor.supplyVulnerabilities.length >= 1) riskPoints += 1;

  if (vendor.contractExpirationDate) {
    const daysLeft =
      (new Date(vendor.contractExpirationDate).getTime() - Date.now()) / (1000 * 60 * 60 * 24);
    if (daysLeft < 90) riskPoints += 3;
    else if (daysLeft < 180) riskPoints += 1;
  }

  if (riskPoints >= 5) return 'high';
  if (riskPoints >= 2) return 'medium';
  return 'low';
}

export function computeDaysUntilExpiration(expirationDate: string | null): number | null {
  if (!expirationDate) return null;
  const expiry = new Date(expirationDate).getTime();
  const days = Math.ceil((expiry - Date.now()) / (1000 * 60 * 60 * 24));
  return days;
}

export function identifyWeakIncumbents(vendors: IncumbentVendor[]): IncumbentVendor[] {
  return vendors.filter((v) => detectRebidRisk(v) === 'high');
}

export function rankEntitiesByOpportunity(entities: ContractorEntity[]): ContractorEntity[] {
  return [...entities].sort((a, b) => b.scores.compositeScore - a.scores.compositeScore);
}

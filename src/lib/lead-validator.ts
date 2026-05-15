import type {
  VerifiedLead,
  RejectedLead,
  LeadValidationResult,
  PropertyData,
  EntitlementData,
  DistressData,
  DispositionIntelligence,
  LeadSources,
  LeadScoring,
} from '@/types';

// ---------------------------------------------------------------------------
// Field presence checks
// ---------------------------------------------------------------------------

function validatePropertyData(
  data: Partial<PropertyData> | undefined,
  errors: string[],
): data is PropertyData {
  if (!data) {
    errors.push('property: entire property block is missing');
    return false;
  }

  const required: Array<keyof PropertyData> = [
    'county',
    'city',
    'apn',
    'ownerName',
    'mailingAddress',
    'siteAddress',
    'zoning',
  ];

  let ok = true;

  for (const field of required) {
    const value = data[field];
    if (typeof value === 'string' && value.trim().length === 0) {
      errors.push(`property.${field}: empty string — real value required`);
      ok = false;
    } else if (value === undefined || value === null) {
      errors.push(`property.${field}: missing — real value required`);
      ok = false;
    }
  }

  if (typeof data.acreage !== 'number' || data.acreage <= 0) {
    errors.push('property.acreage: must be a positive number');
    ok = false;
  }

  // APN must look like a real parcel ID — at minimum non-trivial
  if (data.apn && /^(xxx|000|test|sample|fake|placeholder)/i.test(data.apn.trim())) {
    errors.push('property.apn: value looks like a placeholder — real APN required');
    ok = false;
  }

  return ok;
}

function validateEntitlementData(
  data: Partial<EntitlementData> | undefined,
  errors: string[],
): data is EntitlementData {
  if (!data) {
    errors.push('entitlement: entire entitlement block is missing');
    return false;
  }

  const required: Array<keyof EntitlementData> = [
    'subdivisionName',
    'tentativeMapStatus',
    'finalMapStatus',
    'permitStatus',
    'entitlementStatus',
    'extensionReinstatementIssue',
    'utilityStatus',
    'infrastructureStatus',
  ];

  let ok = true;

  for (const field of required) {
    const value = data[field];
    if (typeof value !== 'string' || value.trim().length === 0) {
      errors.push(`entitlement.${field}: missing or empty — real value required`);
      ok = false;
    }
  }

  return ok;
}

function validateDistressData(
  data: Partial<DistressData> | undefined,
  errors: string[],
  warnings: string[],
): data is DistressData {
  if (!data) {
    errors.push('distress: entire distress block is missing');
    return false;
  }

  if (typeof data.inactivityDurationMonths !== 'number' || data.inactivityDurationMonths < 0) {
    errors.push('distress.inactivityDurationMonths: must be a non-negative number');
    return false;
  }

  // At least one distress signal must be present and non-null
  const signals: Array<keyof Omit<DistressData, 'inactivityDurationMonths'>> = [
    'taxDelinquency',
    'bankruptcy',
    'foreclosure',
    'mechanicsLiens',
    'dissolvedLlcStatus',
    'lenderDistress',
    'pacerReference',
    'secReference',
  ];

  const presentSignals = signals.filter((k) => {
    const v = data[k];
    return typeof v === 'string' && v.trim().length > 0;
  });

  if (presentSignals.length === 0) {
    errors.push('distress: at least one verified distress signal required (tax, bankruptcy, lien, etc.)');
    return false;
  }

  if (presentSignals.length === 1) {
    warnings.push('distress: only one distress signal present — cross-match with additional sources recommended');
  }

  return true;
}

function validateDispositionIntelligence(
  data: Partial<DispositionIntelligence> | undefined,
  errors: string[],
  warnings: string[],
): data is DispositionIntelligence {
  if (!data) {
    errors.push('disposition: entire disposition block is missing');
    return false;
  }

  let ok = true;

  if (!Array.isArray(data.nearbyBuilders) || data.nearbyBuilders.length === 0) {
    errors.push('disposition.nearbyBuilders: at least one real nearby builder required for HIGH PRIORITY classification');
    ok = false;
  }

  if (!Array.isArray(data.likelyBuyers) || data.likelyBuyers.length === 0) {
    errors.push('disposition.likelyBuyers: at least one likely buyer required');
    ok = false;
  }

  if (!Array.isArray(data.likelyExitStrategies) || data.likelyExitStrategies.length === 0) {
    errors.push('disposition.likelyExitStrategies: at least one exit strategy required');
    ok = false;
  }

  if (
    typeof data.buyerDemandScore !== 'number' ||
    data.buyerDemandScore < 0 ||
    data.buyerDemandScore > 100
  ) {
    errors.push('disposition.buyerDemandScore: must be a number 0–100');
    ok = false;
  } else if (data.buyerDemandScore < 20) {
    warnings.push('disposition.buyerDemandScore: low buyer demand — lead may not reach HIGH PRIORITY');
  }

  if (
    typeof data.liquidityScore !== 'number' ||
    data.liquidityScore < 0 ||
    data.liquidityScore > 100
  ) {
    errors.push('disposition.liquidityScore: must be a number 0–100');
    ok = false;
  }

  if (
    typeof data.speedToDispositionScore !== 'number' ||
    data.speedToDispositionScore < 0 ||
    data.speedToDispositionScore > 100
  ) {
    errors.push('disposition.speedToDispositionScore: must be a number 0–100');
    ok = false;
  }

  if (typeof data.nearbyPermitActivity !== 'string' || data.nearbyPermitActivity.trim().length === 0) {
    warnings.push('disposition.nearbyPermitActivity: no permit activity description provided');
  }

  return ok;
}

function validateSources(
  data: Partial<LeadSources> | undefined,
  errors: string[],
): data is LeadSources {
  if (!data) {
    errors.push('sources: entire sources block is missing');
    return false;
  }

  if (!Array.isArray(data.sourceUrls) || data.sourceUrls.length === 0) {
    errors.push('sources.sourceUrls: at least one verifiable source URL required — no source, no lead');
    return false;
  }

  const suspectUrls = data.sourceUrls.filter(
    (u) => typeof u !== 'string' || !/^https?:\/\/.+/.test(u.trim()),
  );

  if (suspectUrls.length > 0) {
    errors.push(`sources.sourceUrls: ${suspectUrls.length} invalid URL(s) — must be full http/https URLs`);
    return false;
  }

  return true;
}

function validateScoring(
  data: Partial<LeadScoring> | undefined,
  errors: string[],
): data is LeadScoring {
  if (!data) {
    errors.push('scoring: entire scoring block is missing');
    return false;
  }

  let ok = true;

  if (
    typeof data.confidenceScore !== 'number' ||
    data.confidenceScore < 0 ||
    data.confidenceScore > 100
  ) {
    errors.push('scoring.confidenceScore: must be a number 0–100');
    ok = false;
  }

  if (typeof data.estimatedSpreadPotential !== 'string' || data.estimatedSpreadPotential.trim().length === 0) {
    errors.push('scoring.estimatedSpreadPotential: required');
    ok = false;
  }

  if (!data.riskLevel || !['low', 'medium', 'high'].includes(data.riskLevel)) {
    errors.push("scoring.riskLevel: must be 'low', 'medium', or 'high'");
    ok = false;
  }

  return ok;
}

// ---------------------------------------------------------------------------
// Cross-match rule: HIGH conviction requires MULTIPLE matching signals
// ---------------------------------------------------------------------------

function checkCrossMatch(
  lead: Partial<VerifiedLead>,
  errors: string[],
  warnings: string[],
): void {
  const distress = lead.distress;
  const disposition = lead.disposition;

  if (!distress || !disposition) {
    return;
  }

  const distressSignalCount = [
    distress.taxDelinquency,
    distress.bankruptcy,
    distress.foreclosure,
    distress.mechanicsLiens,
    distress.dissolvedLlcStatus,
    distress.lenderDistress,
    distress.pacerReference,
    distress.secReference,
  ].filter((v) => typeof v === 'string' && v.trim().length > 0).length;

  const hasEntitlementWork =
    lead.entitlement &&
    (lead.entitlement.tentativeMapStatus.toLowerCase() !== 'none' ||
      lead.entitlement.finalMapStatus.toLowerCase() !== 'none' ||
      lead.entitlement.permitStatus.toLowerCase() !== 'none');

  const hasBuyerDemand =
    typeof disposition.buyerDemandScore === 'number' && disposition.buyerDemandScore >= 40;

  const hasNearbyBuilders =
    Array.isArray(disposition.nearbyBuilders) && disposition.nearbyBuilders.length >= 1;

  if (distressSignalCount < 2) {
    warnings.push(
      'cross-match: only one distress signal — HIGH conviction requires multiple matching signals',
    );
  }

  if (!hasBuyerDemand && !hasNearbyBuilders) {
    errors.push(
      'cross-match: no verified buyer demand — lead cannot be HIGH PRIORITY without active buyers nearby',
    );
  }

  if (!hasEntitlementWork) {
    warnings.push(
      'cross-match: no existing entitlement work detected — speed-to-market value may be limited',
    );
  }
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

function generateId(): string {
  return `lead_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

export function validateLead(
  input: Partial<VerifiedLead> & {
    whyItLookedInteresting?: string;
    nextVerificationStep?: string;
  },
): LeadValidationResult {
  const errors: string[] = [];
  const warnings: string[] = [];

  const propertyOk = validatePropertyData(input.property, errors);
  const entitlementOk = validateEntitlementData(input.entitlement, errors);
  const distressOk = validateDistressData(input.distress, errors, warnings);
  const dispositionOk = validateDispositionIntelligence(input.disposition, errors, warnings);
  const sourcesOk = validateSources(input.sources, errors);
  const scoringOk = validateScoring(input.scoring, errors);

  checkCrossMatch(input, errors, warnings);

  const allFieldsOk =
    propertyOk &&
    entitlementOk &&
    distressOk &&
    dispositionOk &&
    sourcesOk &&
    scoringOk;

  if (allFieldsOk && errors.length === 0) {
    const lead: VerifiedLead = {
      id: input.id ?? generateId(),
      createdAt: input.createdAt ?? new Date().toISOString(),
      property: input.property as PropertyData,
      entitlement: input.entitlement as EntitlementData,
      distress: input.distress as DistressData,
      disposition: input.disposition as DispositionIntelligence,
      sources: input.sources as LeadSources,
      scoring: input.scoring as LeadScoring,
    };

    return { valid: true, lead, errors: [], warnings };
  }

  const missingProof = errors.map((e) => e);
  const sourcesChecked = input.sources?.sourceUrls ?? [];

  const rejected: RejectedLead = {
    id: input.id ?? generateId(),
    createdAt: input.createdAt ?? new Date().toISOString(),
    whyItLookedInteresting: input.whyItLookedInteresting ?? 'Not specified',
    missingProof,
    sourcesChecked,
    nextVerificationStep: input.nextVerificationStep ?? 'Verify required fields against public records',
    partialData: input,
  };

  return { valid: false, rejected, errors, warnings };
}

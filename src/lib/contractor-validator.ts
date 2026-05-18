import type {
  ContractorEntity,
  ContractorContact,
  ContractRecord,
  IncumbentVendor,
  BuyBox,
  ContractorIntelValidationResult,
} from '@/types/contractor-intel';

// ---------------------------------------------------------------------------
// OSINT sources that must be queried before a contractor entity is accepted
// ---------------------------------------------------------------------------

const REQUIRED_OSINT_SOURCES = [
  'SAM.gov entity registration',
  'USASpending.gov award data',
  'FPDS-NG contract data',
];

const RECOMMENDED_OSINT_SOURCES = [
  'SEC EDGAR filings',
  'OFAC SDN sanctions list',
  'OpenCorporates LLC records',
  'Company website',
  'LinkedIn company page',
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const PLACEHOLDER_PATTERNS = /^(test|fake|sample|placeholder|xxx|000|n\/a|tbd|unknown)$/i;

function isPlaceholder(value: string): boolean {
  return PLACEHOLDER_PATTERNS.test(value.trim());
}

function isValidUrl(url: string): boolean {
  return /^https?:\/\/.+/.test(url.trim());
}

function validateContacts(
  contacts: ContractorContact[] | undefined,
  warnings: string[],
): void {
  if (!contacts || contacts.length === 0) {
    warnings.push('contacts: no contacts provided — decision-maker outreach will not be possible');
    return;
  }

  contacts.forEach((contact, i) => {
    if (!contact.name || isPlaceholder(contact.name)) {
      warnings.push(`contacts[${i}]: name is missing or placeholder`);
    }
    if (!contact.email && !contact.phone && !contact.officePhone && !contact.linkedIn) {
      warnings.push(
        `contacts[${i}] (${contact.name || 'unnamed'}): no reach method — email, phone, or LinkedIn required`,
      );
    }
    if (!isValidUrl(contact.sourceUrl)) {
      warnings.push(
        `contacts[${i}] (${contact.name || 'unnamed'}): sourceUrl is not a valid http/https URL`,
      );
    }
  });

  const hasDecisionMaker = contacts.some((c) => c.authorityLevel === 'decision-maker');
  if (!hasDecisionMaker) {
    warnings.push('contacts: no decision-maker identified — access score will be limited');
  }
}

function validateContracts(
  contracts: ContractRecord[] | undefined,
  errors: string[],
  warnings: string[],
): void {
  if (!contracts || contracts.length === 0) {
    errors.push('contracts: at least one verified contract record required — no contract history, no intel');
    return;
  }

  contracts.forEach((contract, i) => {
    if (!contract.contractNumber || isPlaceholder(contract.contractNumber)) {
      errors.push(`contracts[${i}]: contractNumber is missing or placeholder — real PIID required`);
    }
    if (!contract.agencyName || isPlaceholder(contract.agencyName)) {
      errors.push(`contracts[${i}]: agencyName is missing or placeholder`);
    }
    if (!contract.primeContractorName) {
      errors.push(`contracts[${i}]: primeContractorName is required`);
    }
    if (typeof contract.totalObligatedValue !== 'number' || contract.totalObligatedValue < 0) {
      errors.push(`contracts[${i}]: totalObligatedValue must be a non-negative number`);
    }
    if (!isValidUrl(contract.sourceUrl)) {
      errors.push(`contracts[${i}]: sourceUrl must be a valid http/https URL`);
    }
    if (contract.naicsCode && !/^\d{6}$/.test(contract.naicsCode)) {
      warnings.push(`contracts[${i}]: naicsCode should be a 6-digit NAICS code`);
    }
  });
}

function validateIncumbentVendors(
  vendors: IncumbentVendor[] | undefined,
  warnings: string[],
): void {
  if (!vendors || vendors.length === 0) {
    warnings.push('incumbentSuppliers: no incumbent vendor analysis provided — rebid opportunity cannot be assessed');
    return;
  }

  vendors.forEach((vendor, i) => {
    if (!vendor.vendorName || isPlaceholder(vendor.vendorName)) {
      warnings.push(`incumbentSuppliers[${i}]: vendorName is missing or placeholder`);
    }
    if (vendor.sourceUrls.length === 0) {
      warnings.push(`incumbentSuppliers[${i}] (${vendor.vendorName || 'unnamed'}): no sourceUrls — vendor data is unverified`);
    }
    vendor.sourceUrls.forEach((url, j) => {
      if (!isValidUrl(url)) {
        warnings.push(`incumbentSuppliers[${i}].sourceUrls[${j}]: not a valid http/https URL`);
      }
    });
  });
}

function validateBuyBox(
  buyBox: BuyBox | null | undefined,
  warnings: string[],
): void {
  if (!buyBox) {
    warnings.push('buyBox: no buy-box analysis provided — buyer profiling is incomplete');
    return;
  }

  if (!buyBox.categories || buyBox.categories.length === 0) {
    warnings.push('buyBox.categories: at least one fuel/product category required');
  }

  if (buyBox.yearlyDemandEstimateGallons !== null && buyBox.yearlyDemandEstimateGallons < 0) {
    warnings.push('buyBox.yearlyDemandEstimateGallons: must be a non-negative number');
  }
}

function validateSourceUrls(sourceUrls: string[] | undefined, errors: string[]): void {
  if (!sourceUrls || sourceUrls.length === 0) {
    errors.push('sourceUrls: at least one verified OSINT source URL required — no source, no entity');
    return;
  }

  const invalidUrls = sourceUrls.filter((u) => !isValidUrl(u));
  if (invalidUrls.length > 0) {
    errors.push(`sourceUrls: ${invalidUrls.length} invalid URL(s) — must be full http/https URLs`);
  }
}

function detectMissingOsintSources(entity: ContractorEntity): string[] {
  const missing: string[] = [];

  const sourceDomains = entity.sourceUrls.map((u) => {
    try {
      return new URL(u).hostname.toLowerCase();
    } catch {
      return '';
    }
  });

  if (!sourceDomains.some((d) => d.includes('sam.gov'))) {
    missing.push('SAM.gov entity registration');
  }
  if (!sourceDomains.some((d) => d.includes('usaspending.gov') || d.includes('fpds.gov'))) {
    missing.push('USASpending.gov / FPDS-NG contract data');
  }

  return missing;
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export function validateContractorEntity(
  entity: Partial<ContractorEntity>,
): ContractorIntelValidationResult {
  const errors: string[] = [];
  const warnings: string[] = [];

  if (!entity.name || isPlaceholder(entity.name)) {
    errors.push('name: entity name is required and must not be a placeholder');
  }

  if (!entity.entityType) {
    errors.push('entityType: entity type classification is required');
  }

  if (!entity.id) {
    errors.push('id: entity ID is required');
  }

  validateSourceUrls(entity.sourceUrls, errors);
  validateContracts(entity.contracts, errors, warnings);
  validateContacts(entity.contacts, warnings);
  validateIncumbentVendors(entity.incumbentSuppliers, warnings);
  validateBuyBox(entity.buyBox, warnings);

  if (entity.cageCode && !/^[A-Z0-9]{5}$/.test(entity.cageCode)) {
    warnings.push('cageCode: CAGE code should be exactly 5 alphanumeric characters');
  }

  if (entity.ueiSam && !/^[A-Z0-9]{12}$/.test(entity.ueiSam)) {
    warnings.push('ueiSam: UEI should be exactly 12 alphanumeric characters');
  }

  const missingOsintSources =
    errors.length === 0 && entity.sourceUrls
      ? detectMissingOsintSources(entity as ContractorEntity)
      : REQUIRED_OSINT_SOURCES;

  const valid = errors.length === 0;

  if (valid) {
    return {
      valid: true,
      entity: entity as ContractorEntity,
      errors: [],
      warnings,
      missingOsintSources,
    };
  }

  return {
    valid: false,
    errors,
    warnings,
    missingOsintSources,
  };
}

export { REQUIRED_OSINT_SOURCES, RECOMMENDED_OSINT_SOURCES };

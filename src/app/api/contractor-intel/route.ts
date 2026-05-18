import { NextRequest, NextResponse } from 'next/server';
import { validateContractorEntity } from '@/lib/contractor-validator';
import { computeOpportunityScores, computeDaysUntilExpiration, detectRebidRisk } from '@/lib/contractor-scorer';
import type {
  ContractorIntelRequest,
  ContractorEntity,
  ContractAlert,
  RelationshipEdge,
} from '@/types/contractor-intel';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

// ---------------------------------------------------------------------------
// Enrich computed fields before returning
// ---------------------------------------------------------------------------

function enrichEntity(entity: ContractorEntity, allEdges: RelationshipEdge[]): ContractorEntity {
  const enrichedContracts = entity.contracts.map((c) => ({
    ...c,
    daysUntilExpiration: computeDaysUntilExpiration(c.expirationDate),
  }));

  const enrichedVendors = entity.incumbentSuppliers.map((v) => ({
    ...v,
    rebidRisk: detectRebidRisk(v),
  }));

  const scores = computeOpportunityScores(
    { ...entity, contracts: enrichedContracts, incumbentSuppliers: enrichedVendors },
    allEdges,
  );

  const alerts: ContractAlert[] = [];

  enrichedContracts.forEach((contract) => {
    if (
      contract.daysUntilExpiration !== null &&
      contract.daysUntilExpiration >= 0 &&
      contract.daysUntilExpiration <= 180
    ) {
      alerts.push({
        id: `alert_exp_${contract.contractNumber}_${Date.now()}`,
        priority: contract.daysUntilExpiration <= 30 ? 'high' : 'medium',
        type: 'expiring-contract',
        title: `Contract expiring in ${contract.daysUntilExpiration} days`,
        description: `${contract.title} (${contract.contractNumber}) awarded by ${contract.agencyName} expires on ${contract.expirationDate}.`,
        entityId: entity.id,
        entityName: entity.name,
        contractNumber: contract.contractNumber,
        detectedAt: new Date().toISOString(),
        expirationDate: contract.expirationDate,
        daysUntilExpiration: contract.daysUntilExpiration,
        actionRequired: 'Monitor for rebid opportunity. Identify contracting officer and submit capability statement.',
        sourceUrl: contract.sourceUrl,
      });
    }
  });

  enrichedVendors
    .filter((v) => v.rebidRisk === 'high')
    .forEach((vendor) => {
      alerts.push({
        id: `alert_vendor_${vendor.vendorName.replace(/\s+/g, '_')}_${Date.now()}`,
        priority: 'high',
        type: 'supplier-failure',
        title: `Weak incumbent: ${vendor.vendorName}`,
        description: `Incumbent vendor ${vendor.vendorName} has ${vendor.knownComplaints.length} complaint(s), ${vendor.performanceIssues.length} performance issue(s). High rebid risk.`,
        entityId: entity.id,
        entityName: entity.name,
        contractNumber: null,
        detectedAt: new Date().toISOString(),
        expirationDate: vendor.contractExpirationDate,
        daysUntilExpiration: computeDaysUntilExpiration(vendor.contractExpirationDate),
        actionRequired: 'Prepare competitive proposal. Contact procurement office to register as alternative supplier.',
        sourceUrl: vendor.sourceUrls[0] ?? '',
      });
    });

  if (entity.sanctionsStatus === 'flagged') {
    alerts.push({
      id: `alert_sanctions_${entity.id}_${Date.now()}`,
      priority: 'high',
      type: 'sanctions-disruption',
      title: `Sanctions flag: ${entity.name}`,
      description: `Entity ${entity.name} is flagged on a sanctions or restricted-party list. Do not engage without legal review.`,
      entityId: entity.id,
      entityName: entity.name,
      contractNumber: null,
      detectedAt: new Date().toISOString(),
      expirationDate: null,
      daysUntilExpiration: null,
      actionRequired: 'Conduct enhanced due diligence. Consult legal counsel before engagement.',
      sourceUrl: entity.sanctionsSourceUrl ?? '',
    });
  }

  return {
    ...entity,
    contracts: enrichedContracts,
    incumbentSuppliers: enrichedVendors,
    scores,
    alerts,
    lastUpdated: new Date().toISOString(),
  };
}

// ---------------------------------------------------------------------------
// Route handler
// ---------------------------------------------------------------------------

export async function POST(request: NextRequest) {
  try {
    const body = (await request.json()) as Partial<ContractorIntelRequest>;

    if (!body.query?.trim() && !body.cageCode?.trim() && !body.ueiSam?.trim() && !body.contractNumber?.trim()) {
      return NextResponse.json(
        { error: 'Provide at least one of: query, cageCode, ueiSam, contractNumber' },
        { status: 400 },
      );
    }

    // Caller submits a pre-populated ContractorEntity (gathered from OSINT).
    // We validate, enrich scores/alerts, and return it.
    // This endpoint does NOT fabricate data — the caller must supply verified OSINT.
    const entityInput = (body as { entity?: Partial<ContractorEntity> }).entity;

    if (!entityInput) {
      return NextResponse.json(
        {
          error:
            'entity block is required. Populate it from verified OSINT sources (SAM.gov, USASpending.gov, FPDS-NG) before calling this endpoint.',
          requiredOsintSources: [
            'https://sam.gov/api',
            'https://api.usaspending.gov',
            'https://www.fpds.gov/fpdsng_cms/index.php/en/worksite',
          ],
          query: body.query,
        },
        { status: 422 },
      );
    }

    const validation = validateContractorEntity(entityInput);

    if (!validation.valid) {
      return NextResponse.json(
        {
          valid: false,
          errors: validation.errors,
          warnings: validation.warnings,
          missingOsintSources: validation.missingOsintSources,
          message: 'Entity intelligence failed validation. Gather missing data from OSINT sources before resubmitting.',
        },
        { status: 422 },
      );
    }

    const entity = validation.entity!;
    const allEdges: RelationshipEdge[] = entity.relationships ?? [];
    const enriched = enrichEntity(entity, allEdges);

    return NextResponse.json({
      valid: true,
      entity: enriched,
      warnings: validation.warnings,
      missingOsintSources: validation.missingOsintSources,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Contractor intel request failed';
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

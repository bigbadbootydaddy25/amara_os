import { NextRequest, NextResponse } from 'next/server';
import { computeDaysUntilExpiration } from '@/lib/contractor-scorer';
import type {
  AlertsRequest,
  AlertsResponse,
  ContractAlert,
  ContractorEntity,
} from '@/types/contractor-intel';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

// ---------------------------------------------------------------------------
// Alert generation from a set of contractor entities
// ---------------------------------------------------------------------------

function generateAlerts(
  entities: ContractorEntity[],
  daysToExpiration: number = 180,
): ContractAlert[] {
  const alerts: ContractAlert[] = [];
  const now = new Date().toISOString();

  for (const entity of entities) {
    // Collect existing alerts from the entity
    alerts.push(...entity.alerts);

    // Check for contracts nearing expiration that may not yet have alerts
    for (const contract of entity.contracts) {
      const days = computeDaysUntilExpiration(contract.expirationDate);
      if (days === null || days > daysToExpiration || days < 0) continue;

      const alreadyAlerting = entity.alerts.some(
        (a) => a.contractNumber === contract.contractNumber && a.type === 'expiring-contract',
      );
      if (alreadyAlerting) continue;

      alerts.push({
        id: `alerts_exp_${contract.contractNumber}_${Date.now()}`,
        priority: days <= 30 ? 'high' : days <= 90 ? 'medium' : 'low',
        type: 'expiring-contract',
        title: `Contract expiring in ${days} days`,
        description: `${contract.title} (${contract.contractNumber}) with ${contract.agencyName} expires ${contract.expirationDate}. Prime: ${contract.primeContractorName}.`,
        entityId: entity.id,
        entityName: entity.name,
        contractNumber: contract.contractNumber,
        detectedAt: now,
        expirationDate: contract.expirationDate,
        daysUntilExpiration: days,
        actionRequired:
          'Identify contracting officer via SAM.gov. Submit capability statement. Monitor USASpending.gov for rebid posting.',
        sourceUrl: contract.sourceUrl,
      });
    }

    // New procurement signals (entities with no recent contracts)
    const latestAward = entity.contracts
      .map((c) => new Date(c.awardedDate).getTime())
      .sort((a, b) => b - a)[0];

    if (!latestAward || Date.now() - latestAward > 365 * 24 * 60 * 60 * 1000) {
      const alreadyAlerting = entity.alerts.some((a) => a.type === 'new-procurement-posting');
      if (!alreadyAlerting && entity.samRegistered) {
        alerts.push({
          id: `alerts_proc_${entity.id}_${Date.now()}`,
          priority: 'low',
          type: 'new-procurement-posting',
          title: `No recent awards: ${entity.name}`,
          description: `${entity.name} has no contract awards in the last 12 months. May be preparing new procurement.`,
          entityId: entity.id,
          entityName: entity.name,
          contractNumber: null,
          detectedAt: now,
          expirationDate: null,
          daysUntilExpiration: null,
          actionRequired:
            'Monitor SAM.gov for new solicitations from this entity. Check beta.sam.gov for pending opportunities.',
          sourceUrl: entity.sourceUrls[0] ?? '',
        });
      }
    }
  }

  return alerts;
}

// ---------------------------------------------------------------------------
// Route handler
// ---------------------------------------------------------------------------

export async function POST(request: NextRequest) {
  try {
    const body = (await request.json()) as AlertsRequest & {
      entities?: ContractorEntity[];
    };

    const { entities = [], priorities, types, daysToExpiration = 180 } = body;

    if (!Array.isArray(entities)) {
      return NextResponse.json(
        { error: 'entities must be an array of ContractorEntity objects' },
        { status: 400 },
      );
    }

    let alerts = generateAlerts(entities, daysToExpiration);

    // Filter by entity IDs if specified
    if (body.entityIds && body.entityIds.length > 0) {
      alerts = alerts.filter((a) => body.entityIds!.includes(a.entityId));
    }

    // Filter by priority
    if (priorities && priorities.length > 0) {
      alerts = alerts.filter((a) => priorities.includes(a.priority));
    }

    // Filter by type
    if (types && types.length > 0) {
      alerts = alerts.filter((a) => types.includes(a.type));
    }

    // Sort: high priority first, then by days until expiration ascending
    alerts.sort((a, b) => {
      const priorityOrder: Record<string, number> = { high: 0, medium: 1, low: 2 };
      const pDiff = priorityOrder[a.priority] - priorityOrder[b.priority];
      if (pDiff !== 0) return pDiff;
      const aDays = a.daysUntilExpiration ?? Infinity;
      const bDays = b.daysUntilExpiration ?? Infinity;
      return aDays - bDays;
    });

    const response: AlertsResponse = {
      alerts,
      totalCount: alerts.length,
      highCount: alerts.filter((a) => a.priority === 'high').length,
      generatedAt: new Date().toISOString(),
    };

    return NextResponse.json(response);
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Alerts request failed';
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

// Quick GET to surface a summary without a full entity payload
export async function GET() {
  return NextResponse.json({
    description: 'POST entities[] to receive prioritized alerts. High alerts include: expiring contracts (≤30 days), sanctions flags, weak incumbents.',
    alertTypes: [
      'expiring-contract',
      'emergency-fuel-request',
      'supplier-failure',
      'sanctions-disruption',
      'refinery-outage',
      'military-demand-spike',
      'shipping-disruption',
      'geopolitical-instability',
      'new-procurement-posting',
    ],
    osintSources: [
      'https://sam.gov',
      'https://api.usaspending.gov',
      'https://www.fpds.gov',
      'https://efts.sec.gov/LATEST/search-index',
      'https://sanctionssearch.ofac.treas.gov',
    ],
  });
}

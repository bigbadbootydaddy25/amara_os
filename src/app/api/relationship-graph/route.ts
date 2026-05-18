import { NextRequest, NextResponse } from 'next/server';
import { rankEntitiesByOpportunity } from '@/lib/contractor-scorer';
import type {
  RelationshipGraphRequest,
  ContractNetworkMap,
  ContractorEntity,
  RelationshipEdge,
} from '@/types/contractor-intel';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

// ---------------------------------------------------------------------------
// Graph serialisation for Neo4j-compatible Cypher or D3 adjacency list
// ---------------------------------------------------------------------------

interface CypherStatement {
  statement: string;
}

function entityToCypher(entity: ContractorEntity): CypherStatement {
  const props = [
    `id: ${JSON.stringify(entity.id)}`,
    `name: ${JSON.stringify(entity.name)}`,
    `entityType: ${JSON.stringify(entity.entityType)}`,
    entity.cageCode ? `cageCode: ${JSON.stringify(entity.cageCode)}` : null,
    entity.ueiSam ? `ueiSam: ${JSON.stringify(entity.ueiSam)}` : null,
    `samRegistered: ${entity.samRegistered}`,
    `sanctionsStatus: ${JSON.stringify(entity.sanctionsStatus)}`,
    `compositeScore: ${entity.scores.compositeScore}`,
    `riskScore: ${entity.scores.riskScore}`,
    `buyerScore: ${entity.scores.buyerScore}`,
    `supplierScore: ${entity.scores.supplierScore}`,
  ]
    .filter(Boolean)
    .join(', ');

  return {
    statement: `MERGE (e:Entity {id: ${JSON.stringify(entity.id)}}) SET e += {${props}}`,
  };
}

function edgeToCypher(edge: RelationshipEdge): CypherStatement {
  const relType = edge.relationshipType.toUpperCase().replace(/-/g, '_');
  const props = [
    `occurrenceCount: ${edge.occurrenceCount}`,
    edge.estimatedAnnualValue !== null ? `estimatedAnnualValue: ${edge.estimatedAnnualValue}` : null,
    `firstSeenDate: ${JSON.stringify(edge.firstSeenDate)}`,
    `lastSeenDate: ${JSON.stringify(edge.lastSeenDate)}`,
  ]
    .filter(Boolean)
    .join(', ');

  return {
    statement:
      `MATCH (a:Entity {id: ${JSON.stringify(edge.fromEntityId)}}), (b:Entity {id: ${JSON.stringify(edge.toEntityId)}}) ` +
      `MERGE (a)-[r:${relType} {id: ${JSON.stringify(edge.id)}}]->(b) SET r += {${props}}`,
  };
}

// ---------------------------------------------------------------------------
// D3-compatible adjacency format
// ---------------------------------------------------------------------------

interface GraphNode {
  id: string;
  name: string;
  entityType: string;
  compositeScore: number;
  riskScore: number;
  buyerScore: number;
  supplierScore: number;
  sanctionsStatus: string;
  alertCount: number;
  group: string;
}

interface GraphLink {
  source: string;
  target: string;
  relationshipType: string;
  occurrenceCount: number;
  estimatedAnnualValue: number | null;
}

function toD3Graph(entities: ContractorEntity[], edges: RelationshipEdge[]): {
  nodes: GraphNode[];
  links: GraphLink[];
} {
  const nodes: GraphNode[] = entities.map((e) => ({
    id: e.id,
    name: e.name,
    entityType: e.entityType,
    compositeScore: e.scores.compositeScore,
    riskScore: e.scores.riskScore,
    buyerScore: e.scores.buyerScore,
    supplierScore: e.scores.supplierScore,
    sanctionsStatus: e.sanctionsStatus,
    alertCount: e.alerts.filter((a) => a.priority === 'high').length,
    group: e.entityType,
  }));

  const links: GraphLink[] = edges.map((edge) => ({
    source: edge.fromEntityId,
    target: edge.toEntityId,
    relationshipType: edge.relationshipType,
    occurrenceCount: edge.occurrenceCount,
    estimatedAnnualValue: edge.estimatedAnnualValue,
  }));

  return { nodes, links };
}

// ---------------------------------------------------------------------------
// Route handler
// ---------------------------------------------------------------------------

export async function POST(request: NextRequest) {
  try {
    const body = (await request.json()) as Partial<RelationshipGraphRequest> & {
      network?: ContractNetworkMap;
    };

    if (!body.network) {
      return NextResponse.json(
        {
          error:
            'network block is required. Build the ContractNetworkMap from verified OSINT ' +
            '(SAM.gov, USASpending.gov, FPDS-NG) and pass it to this endpoint for graph serialization.',
        },
        { status: 422 },
      );
    }

    const { network } = body;
    const { depth = 1, includeTypes } = body;

    let edges = network.edges;
    if (includeTypes && includeTypes.length > 0) {
      edges = edges.filter((e) => includeTypes.includes(e.relationshipType));
    }

    const ranked = rankEntitiesByOpportunity(network.entities);
    const d3Graph = toD3Graph(ranked, edges);
    const cypherStatements = [
      ...ranked.map(entityToCypher),
      ...edges.map(edgeToCypher),
    ];

    const totalContractValue = ranked.reduce(
      (sum, e) => sum + e.contracts.reduce((s, c) => s + (c.totalObligatedValue ?? 0), 0),
      0,
    );

    const summary = {
      entityCount: ranked.length,
      edgeCount: edges.length,
      depth,
      totalContractValue,
      topOpportunities: ranked.slice(0, 5).map((e) => ({
        id: e.id,
        name: e.name,
        entityType: e.entityType,
        compositeScore: e.scores.compositeScore,
        highAlerts: e.alerts.filter((a) => a.priority === 'high').length,
      })),
      highRiskEntities: ranked
        .filter((e) => e.scores.riskScore >= 60 || e.sanctionsStatus === 'flagged')
        .map((e) => ({ id: e.id, name: e.name, riskScore: e.scores.riskScore, sanctionsStatus: e.sanctionsStatus })),
      generatedAt: network.generatedAt,
      osintSourcesQueried: network.osintSourcesQueried,
    };

    return NextResponse.json({
      d3Graph,
      cypherStatements,
      summary,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Relationship graph request failed';
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

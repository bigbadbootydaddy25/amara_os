import { runQuery } from './graph-client.js';
import type { Property, SimulationResult } from '../../types.js';

/**
 * Syncs a property and its ZIP node into Neo4j.
 * Creates or merges: (Property)-[:LOCATED_IN]->(Zip)
 */
export async function syncProperty(property: Property): Promise<void> {
  await runQuery(
    `MERGE (z:Zip {code: $zip})
     ON CREATE SET z.state = $state, z.city = $city, z.created_at = datetime()

     MERGE (p:Property {id: $id})
     ON CREATE SET
       p.address         = $address,
       p.city            = $city,
       p.state           = $state,
       p.zip             = $zip,
       p.asking_price    = $askingPrice,
       p.arv_estimate    = $arvEstimate,
       p.rehab_estimate  = $rehabEstimate,
       p.condition_grade = $conditionGrade,
       p.tax_delinquent  = $taxDelinquent,
       p.vacant          = $vacant,
       p.ingestion_source = $ingestionSource,
       p.created_at      = datetime()
     ON MATCH SET
       p.asking_price   = $askingPrice,
       p.arv_estimate   = $arvEstimate,
       p.updated_at     = datetime()

     MERGE (p)-[:LOCATED_IN]->(z)`,
    {
      id:              property.id ?? '',
      address:         property.address,
      city:            property.city,
      state:           property.state,
      zip:             property.zip,
      askingPrice:     property.askingPrice ?? null,
      arvEstimate:     property.arvEstimate ?? null,
      rehabEstimate:   property.rehabEstimate ?? null,
      conditionGrade:  property.conditionGrade ?? null,
      taxDelinquent:   property.taxDelinquent ?? false,
      vacant:          property.vacant ?? false,
      ingestionSource: property.ingestionSource,
    },
  );
}

/**
 * Syncs a simulation result onto the Property node.
 * Adds: (Property)-[:HAS_SIMULATION]->(Simulation)
 */
export async function syncSimulation(sim: SimulationResult): Promise<void> {
  await runQuery(
    `MATCH (p:Property {id: $propertyId})
     MERGE (s:Simulation {id: $simId})
     ON CREATE SET
       s.recommended_mao      = $recommendedMao,
       s.recommended_strategy = $recommendedStrategy,
       s.risk_score           = $riskScore,
       s.confidence_score     = $confidenceScore,
       s.model_version        = $modelVersion,
       s.created_at           = datetime()
     MERGE (p)-[:HAS_SIMULATION]->(s)`,
    {
      propertyId:          sim.propertyId,
      simId:               `${sim.propertyId}:${sim.createdAt.getTime()}`,
      recommendedMao:      sim.recommendedMao,
      recommendedStrategy: sim.recommendedStrategy,
      riskScore:           sim.riskScore,
      confidenceScore:     sim.confidenceScore,
      modelVersion:        sim.modelVersion,
    },
  );
}

/**
 * Links a buyer to a ZIP they are active in.
 * (Buyer)-[:ACTIVE_IN {deals_closed, avg_close_days}]->(Zip)
 */
export async function syncBuyerZipActivity(
  buyerId: string,
  buyerName: string,
  zip: string,
  dealsClosedInZip: number,
  avgCloseDays: number,
): Promise<void> {
  await runQuery(
    `MERGE (b:Buyer {id: $buyerId})
     ON CREATE SET b.name = $buyerName, b.created_at = datetime()

     MERGE (z:Zip {code: $zip})

     MERGE (b)-[r:ACTIVE_IN]->(z)
     ON CREATE SET r.deals_closed = $dealsClosed, r.avg_close_days = $avgCloseDays
     ON MATCH SET
       r.deals_closed    = $dealsClosed,
       r.avg_close_days  = $avgCloseDays,
       r.updated_at      = datetime()`,
    { buyerId, buyerName, zip, dealsClosed: dealsClosedInZip, avgCloseDays },
  );
}

/**
 * Marks a deal as WON and connects buyer → property.
 * (Buyer)-[:PURCHASED {price, profit, days}]->(Property)
 */
export async function syncDealOutcome(params: {
  dealId: string;
  propertyId: string;
  buyerId?: string;
  contractPrice: number;
  actualProfit: number;
  daysToClose: number;
  strategy: string;
}): Promise<void> {
  await runQuery(
    `MERGE (d:Deal {id: $dealId})
     ON CREATE SET
       d.contract_price = $contractPrice,
       d.actual_profit  = $actualProfit,
       d.days_to_close  = $daysToClose,
       d.strategy       = $strategy,
       d.created_at     = datetime()

     WITH d
     MATCH (p:Property {id: $propertyId})
     MERGE (d)-[:INVOLVES]->(p)`,
    {
      dealId:        params.dealId,
      propertyId:    params.propertyId,
      contractPrice: params.contractPrice,
      actualProfit:  params.actualProfit,
      daysToClose:   params.daysToClose,
      strategy:      params.strategy,
    },
  );

  if (params.buyerId) {
    await runQuery(
      `MATCH (b:Buyer {id: $buyerId}), (p:Property {id: $propertyId})
       MERGE (b)-[r:PURCHASED]->(p)
       ON CREATE SET
         r.price       = $contractPrice,
         r.profit      = $actualProfit,
         r.days        = $daysToClose,
         r.strategy    = $strategy,
         r.created_at  = datetime()`,
      {
        buyerId:       params.buyerId,
        propertyId:    params.propertyId,
        contractPrice: params.contractPrice,
        actualProfit:  params.actualProfit,
        daysToClose:   params.daysToClose,
        strategy:      params.strategy,
      },
    );
  }
}

/**
 * Query: Find buyers active in a ZIP with proven close history.
 */
export async function findBuyersForZip(zip: string): Promise<Array<{
  buyerId: string;
  buyerName: string;
  dealsClosedInZip: number;
  avgCloseDays: number;
}>> {
  const result = await runQuery(
    `MATCH (b:Buyer)-[r:ACTIVE_IN]->(z:Zip {code: $zip})
     RETURN b.id AS buyerId, b.name AS buyerName,
            r.deals_closed AS dealsClosedInZip, r.avg_close_days AS avgCloseDays
     ORDER BY r.deals_closed DESC`,
    { zip },
  );
  return result.records.map((rec) => ({
    buyerId:          rec.get('buyerId') as string,
    buyerName:        rec.get('buyerName') as string,
    dealsClosedInZip: (rec.get('dealsClosedInZip') as number) ?? 0,
    avgCloseDays:     (rec.get('avgCloseDays') as number) ?? 0,
  }));
}

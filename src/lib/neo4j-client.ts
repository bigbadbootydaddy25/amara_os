// Neo4j integration — optional. Set NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD in .env.local.
// When unconfigured the rest of the app uses file-based storage transparently.

/* eslint-disable @typescript-eslint/no-explicit-any */

type AnyDriver = any;

let driver: AnyDriver = null;
let initialized = false;

async function getDriver(): Promise<AnyDriver> {
  if (initialized) return driver as AnyDriver;
  initialized = true;

  const uri = process.env.NEO4J_URI?.trim();
  const user = process.env.NEO4J_USER?.trim();
  const password = process.env.NEO4J_PASSWORD?.trim();

  if (!uri || !user || !password) return null;

  try {
    // neo4j-driver is an optional peer dep — swallow if absent
    const importFn = (m: string): Promise<any> => import(/* webpackIgnore: true */ m as any);
    const neo4j = await importFn('neo4j-driver').catch(() => null);
    if (!neo4j) return null;
    driver = neo4j.default.driver(uri, neo4j.default.auth.basic(user, password)) as AnyDriver;
    return driver;
  } catch {
    return null;
  }
}

export async function isNeo4jAvailable(): Promise<boolean> {
  const d = await getDriver();
  if (!d) return false;
  try {
    await (d as AnyDriver).verifyConnectivity();
    return true;
  } catch {
    return false;
  }
}

export async function runQuery(
  cypher: string,
  params: Record<string, unknown> = {},
): Promise<unknown[]> {
  const d = await getDriver();
  if (!d) throw new Error('Neo4j not configured');

  const session = (d as AnyDriver).session();
  try {
    const result = await session.run(cypher, params);
    return (result.records as any[]).map((r: any) => {
      return Object.fromEntries((r.keys as string[]).map((k) => [k, r.get(k)]));
    });
  } finally {
    await session.close();
  }
}

export async function syncPropertyToGraph(property: {
  id: string;
  address: string;
  zip: string;
  dealType?: string;
  dealStatus: string;
}): Promise<void> {
  await runQuery(
    `MERGE (p:Property {id: $id})
     SET p.address = $address, p.dealType = $dealType, p.dealStatus = $dealStatus
     MERGE (z:ZIP {code: $zip})
     MERGE (p)-[:LOCATED_IN]->(z)`,
    {
      id: property.id,
      address: property.address,
      zip: property.zip,
      dealType: property.dealType ?? 'unknown',
      dealStatus: property.dealStatus,
    },
  );
}

export async function syncBuyerToGraph(buyer: {
  id: string;
  name: string;
  type: string;
  activeZips: string[];
}): Promise<void> {
  await runQuery(
    `MERGE (b:Buyer {id: $id})
     SET b.name = $name, b.type = $type
     WITH b
     UNWIND $zips AS zip
     MERGE (z:ZIP {code: zip})
     MERGE (b)-[:ACTIVE_IN]->(z)`,
    { id: buyer.id, name: buyer.name, type: buyer.type, zips: buyer.activeZips },
  );
}

export async function linkPropertyToBuyer(
  propertyId: string,
  buyerId: string,
  confidence: number,
): Promise<void> {
  await runQuery(
    `MATCH (p:Property {id: $pid}), (b:Buyer {id: $bid})
     MERGE (p)-[r:MATCHES]->(b)
     SET r.confidence = $confidence`,
    { pid: propertyId, bid: buyerId, confidence },
  );
}

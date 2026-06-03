import neo4j, { type Driver, type Session } from 'neo4j-driver';

let driver: Driver | null = null;

export function getDriver(): Driver {
  if (!driver) {
    driver = neo4j.driver(
      process.env.NEO4J_URI      ?? 'bolt://localhost:7687',
      neo4j.auth.basic(
        process.env.NEO4J_USER     ?? 'neo4j',
        process.env.NEO4J_PASSWORD ?? 'amara_neo4j_secret',
      ),
      { maxConnectionPoolSize: 10 },
    );
  }
  return driver;
}

export function getSession(): Session {
  return getDriver().session({ database: 'neo4j' });
}

export async function closeDriver(): Promise<void> {
  if (driver) {
    await driver.close();
    driver = null;
  }
}

export async function runQuery(
  cypher: string,
  params: Record<string, unknown> = {},
): Promise<neo4j.QueryResult> {
  const session = getSession();
  try {
    return await session.run(cypher, params);
  } finally {
    await session.close();
  }
}

export async function initConstraints(): Promise<void> {
  const constraints = [
    'CREATE CONSTRAINT prop_id IF NOT EXISTS FOR (p:Property) REQUIRE p.id IS UNIQUE',
    'CREATE CONSTRAINT deal_id IF NOT EXISTS FOR (d:Deal) REQUIRE d.id IS UNIQUE',
    'CREATE CONSTRAINT buyer_id IF NOT EXISTS FOR (b:Buyer) REQUIRE b.id IS UNIQUE',
    'CREATE CONSTRAINT zip_code IF NOT EXISTS FOR (z:Zip) REQUIRE z.code IS UNIQUE',
  ];
  for (const stmt of constraints) {
    await runQuery(stmt);
  }
}

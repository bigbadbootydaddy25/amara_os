import { openDb, type DB } from '../agents/lib/db';
import { loadSources } from '../agents/lib/sources';

export const ASOF = '2026-10-05';
export const src = loadSources();

export function seedDeed(db: DB, o: { no: string; type?: string; date: string; grantor?: string; grantee: string; price?: number | null; apn: string }) {
  db.prepare('INSERT INTO deeds (county, instrument_no, type, record_date, grantor, grantee, consideration, apn, source, tag) VALUES (?,?,?,?,?,?,?,?,?,?)')
    .run('Dallas', o.no, o.type ?? 'Warranty Deed', o.date, o.grantor ?? 'SOME SELLER', o.grantee, o.price ?? null, o.apn, 'dallas_county_clerk', `[GR ${ASOF}]`);
}
export function seedDot(db: DB, o: { no: string; date: string; borrower: string; lender: string; apn: string }) {
  db.prepare('INSERT INTO deeds_of_trust (county, instrument_no, record_date, grantor, lender, amount, apn) VALUES (?,?,?,?,?,?,?)')
    .run('Dallas', o.no, o.date, o.borrower, o.lender, 100000, o.apn);
}
export function seedProp(db: DB, o: { apn: string; zip: string; land_use: string; address?: string; beds?: number; sqft?: number; year?: number; cad?: number;
  prior?: string; improvement?: number; owner?: string; mailing?: string; lastSale?: string; improvementPrior?: number }) {
  db.prepare(`INSERT INTO properties (apn, county, address, zip, land_use, beds, baths, sqft, year_built, cad_value, owner, owner_mailing, land_use_prior,
    improvement_value, improvement_value_prior, last_sale_date, source, tag) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)`)
    .run(o.apn, 'Dallas', o.address ?? `${o.apn} TEST ST`, o.zip, o.land_use, o.beds ?? null, 2, o.sqft ?? null, o.year ?? null, o.cad ?? null,
      o.owner ?? null, o.mailing ?? null, o.prior ?? null, o.improvement ?? null, o.improvementPrior ?? null, o.lastSale ?? null, 'dcad', `[GR ${ASOF}]`);
}
export function seedLot(db: DB, o: { apn: string; sqft: number; frontage: number; zoning: string; flood?: string; floodway?: number }) {
  db.prepare('INSERT INTO lot_details (apn, county, lot_sqft, frontage_ft, zoning, flood_zone, water_sewer, tag, floodway) VALUES (?,?,?,?,?,?,?,?,?)')
    .run(o.apn, 'Dallas', o.sqft, o.frontage, o.zoning, o.flood ?? 'X', null, `[GR ${ASOF}]`, o.floodway ?? 0);
}

/** A small Dallas County world: one SFR repeat buyer, one grouped pair, a financed buyer, excluded names, two lot buyers (one real builder). */
export function seedWorld(db: DB): void {
  // Lone Star Homes: 2 cash SFR buys + 1 hard-money buy
  for (const [i, d, zip, price] of [[1, '2026-07-15', '75218', 120000], [2, '2026-09-20', '75218', 135000]] as const) {
    seedProp(db, { apn: `S${i}`, zip, land_use: 'A1', beds: 3, sqft: 1200 + i * 100, year: 1955, cad: 150000, owner: 'LONE STAR HOMES LLC', mailing: 'PO BOX 1 PLANO TX' });
    seedDeed(db, { no: `S${i}`, date: d, grantee: 'Lone Star Homes, L.L.C.', price, apn: `S${i}` });
  }
  seedProp(db, { apn: 'S3', zip: '75228', land_use: 'A1', beds: 3, sqft: 1300, year: 1960, cad: 140000 });
  seedDeed(db, { no: 'S3', date: '2026-08-10', grantee: 'LONE STAR HOMES LLC', price: 125000, apn: 'S3' });
  seedDot(db, { no: 'D3', date: '2026-08-10', borrower: 'LONE STAR HOMES LLC', lender: 'Kiavi Funding', apn: 'S3' });
  // Grouped pair: one cash buy each
  seedProp(db, { apn: 'G1', zip: '75217', land_use: 'A1', beds: 3, sqft: 1100, year: 1950, cad: 110000 });
  seedProp(db, { apn: 'G2', zip: '75217', land_use: 'A1', beds: 2, sqft: 1000, year: 1948, cad: 100000 });
  seedDeed(db, { no: 'G1', date: '2026-06-01', grantee: 'ALPHA HOLDINGS LLC', price: 90000, apn: 'G1' });
  seedDeed(db, { no: 'G2', date: '2026-09-01', grantee: 'BETA HOLDINGS LLC', price: 95000, apn: 'G2' });
  db.prepare("INSERT INTO buyers (normalized_name, registered_agent, mailing) VALUES ('ALPHA HOLDINGS','Pat Agent','1 Main St Dallas TX'),('BETA HOLDINGS','PAT AGENT','1 MAIN ST DALLAS TX')").run();
  // Single cash buy only -> NOT repeat
  seedProp(db, { apn: 'O1', zip: '75216', land_use: 'A1' });
  seedDeed(db, { no: 'O1', date: '2026-09-01', grantee: 'ONE TIME BUYER LLC', price: 100000, apn: 'O1' });
  // Excluded names + quitclaim
  seedProp(db, { apn: 'X1', zip: '75218', land_use: 'A1' });
  seedProp(db, { apn: 'X2', zip: '75218', land_use: 'A1' });
  seedProp(db, { apn: 'X3', zip: '75218', land_use: 'A1' });
  seedProp(db, { apn: 'X4', zip: '75218', land_use: 'A1' });
  seedDeed(db, { no: 'X1', date: '2026-08-01', grantee: 'D.R. Horton - Texas, Ltd.'.replace('- Texas, ', ''), apn: 'X1' });
  seedDeed(db, { no: 'X2', date: '2026-08-02', grantee: 'Opendoor Property Trust I', apn: 'X2' });
  seedDeed(db, { no: 'X3', date: '2026-08-03', grantee: 'QUIT CLAIM GUY LLC', type: 'Quitclaim Deed', apn: 'X3' });
  seedDeed(db, { no: 'X4', date: '2026-08-04', grantee: 'QUIT CLAIM GUY LLC', type: 'Quitclaim Deed', apn: 'X4' });
  // Lot buyers: Pioneer (permit on one lot) = builder; Speculator (no permit) = repeat but unconfirmed
  for (const [apn, zip, buyer, d] of [['L1', '75216', 'PIONEER BUILDERS LLC', '2026-04-10'], ['L2', '75216', 'PIONEER BUILDERS LLC', '2026-08-20'],
    ['L3', '75215', 'SPECULATOR LAND LLC', '2026-05-01'], ['L4', '75215', 'SPECULATOR LAND LLC', '2026-09-01']] as const) {
    seedProp(db, { apn, zip, land_use: 'C1', cad: 30000 });
    seedLot(db, { apn, sqft: 7500, frontage: 50, zoning: 'R-7.5(A)' });
    seedDeed(db, { no: apn, date: d, grantee: buyer, price: 35000, apn });
  }
  db.prepare("INSERT INTO permits (permit_no, city, apn, type, issue_date) VALUES ('BP-1','Dallas','L1','New Single Family Residence','2026-08-15')").run();
}

export const memDb = (): DB => openDb(':memory:');

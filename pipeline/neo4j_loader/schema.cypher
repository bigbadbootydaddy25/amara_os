// ============================================================
// Neo4j schema setup — run once before the first data load.
// Creates constraints and indexes for the real estate graph.
// ============================================================

// ── Constraints (ensure uniqueness) ─────────────────────────

CREATE CONSTRAINT property_address_zip IF NOT EXISTS
  FOR (p:Property) REQUIRE (p.address, p.zip_code) IS UNIQUE;

CREATE CONSTRAINT zip_code IF NOT EXISTS
  FOR (z:ZIP) REQUIRE z.zip_code IS UNIQUE;

CREATE CONSTRAINT county_name_state IF NOT EXISTS
  FOR (c:County) REQUIRE (c.name, c.state) IS UNIQUE;

CREATE CONSTRAINT cash_buyer_name IF NOT EXISTS
  FOR (b:CashBuyer) REQUIRE b.name IS UNIQUE;

CREATE CONSTRAINT distress_flag_type IF NOT EXISTS
  FOR (d:DistressFlag) REQUIRE d.type IS UNIQUE;

// ── Indexes for common query patterns ───────────────────────

CREATE INDEX property_zip IF NOT EXISTS
  FOR (p:Property) ON (p.zip_code);

CREATE INDEX property_distress_score IF NOT EXISTS
  FOR (p:Property) ON (p.distress_score);

CREATE INDEX property_type IF NOT EXISTS
  FOR (p:Property) ON (p.type);

CREATE INDEX buyer_type IF NOT EXISTS
  FOR (b:CashBuyer) ON (b.buyer_type);

CREATE INDEX buyer_zip IF NOT EXISTS
  FOR (b:CashBuyer) ON (b.zip_code);

// ── Pre-seed DistressFlag nodes ──────────────────────────────

MERGE (d:DistressFlag {type: "preforeclosure"})   SET d.label = "Pre-Foreclosure / Lis Pendens";
MERGE (d:DistressFlag {type: "tax_delinquent"})   SET d.label = "Tax Delinquent";
MERGE (d:DistressFlag {type: "code_violation"})   SET d.label = "Code Violation";
MERGE (d:DistressFlag {type: "probate"})          SET d.label = "Probate";
MERGE (d:DistressFlag {type: "dom90"})            SET d.label = "90+ Days on Market";
MERGE (d:DistressFlag {type: "nod"})              SET d.label = "Notice of Default";
MERGE (d:DistressFlag {type: "bankruptcy"})       SET d.label = "Bankruptcy Filing";
MERGE (d:DistressFlag {type: "vacant_land"})      SET d.label = "Vacant / Infill Land";
MERGE (d:DistressFlag {type: "ghost_plat"})       SET d.label = "Ghost Subdivision / Dead Plat";
MERGE (d:DistressFlag {type: "absentee_owner"})   SET d.label = "Absentee Owner";
MERGE (d:DistressFlag {type: "cash_buyer"})       SET d.label = "Cash Buyer Transaction";

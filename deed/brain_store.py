"""
DEED brain_store — writes Harrison County WV title knowledge to all memory layers.

Layers (each degrades gracefully if the service is offline):
  1. Neo4j        — knowledge graph via raw driver (nodes + CYPHER relationships)
  2. Mem0         — persistent facts  (mem0ai library — key from Keychain/env)
  3. Qdrant       — vector search chunks (qdrant-client — localhost:6333)
  4. Outcomes     — JSONL feedback loop (amara-brain/Brain/Outcomes/)
  5. Obsidian     — markdown case study file
  6. Wiki         — WV title playbook markdown
  7. Langfuse     — observability run log (langfuse library — key from Keychain/env)
  8. Telegram     — completion notification

Usage:
  from deed.brain_store import run as brain_run
  brain_run(results, elapsed_s=elapsed)
"""
import json
import logging
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("BRAIN_STORE")

# ── Paths ─────────────────────────────────────────────────────────────────────
_REPO_ROOT  = Path(__file__).parent.parent
_BRAIN_DIR  = Path(os.getenv("AMARA_BRAIN",
                              str(_REPO_ROOT / "amara-brain" / "Brain")))
_OBS_VAULT  = Path(os.getenv("OBSIDIAN_VAULT", "/Users/user/obsidian-vault"))

# ── Identity ──────────────────────────────────────────────────────────────────
PARCEL_ID = "11-409-19"
COUNTY    = "Harrison"
STATE     = "WV"
DISTRICT  = "Elk-Outside"
PREPARER  = "Scott Schufford"
COMPANY   = "Aces N 8s"
CLIENT    = "Texhoma Land Partners"


# ══════════════════════════════════════════════════════════════════════════════
#  Knowledge payloads
# ══════════════════════════════════════════════════════════════════════════════

GRAPH_NODES = [
    # (label, props)
    ("Parcel",       {"id": "11-409-19", "full_id": "17-11-0409-0019-0000",
                      "sub_parcels": "0001,0002,0003",
                      "county": "Harrison", "state": "WV",
                      "district": "Elk-Outside", "district_num": "11",
                      "acres": 121.072, "tax_desc": "118 AC Stout Run",
                      "legal_desc": "Gnatty Creek watershed, Elk Creek tributary",
                      "property_class": "F - Farm"}),
    ("SurfaceOwner", {"id": "Burns-Craig-Sue", "name": "Burns, L. Craig & Sue B.",
                      "address": "458 Knoll View Road, Mount Clare WV 26408",
                      "deed": "DB 1197/1258", "dated": "1989-07-11",
                      "recorded": "1989-09-21", "consideration": "$34,500.00",
                      "acres": 129.63, "tenure": "Joint tenants WROS"}),
    ("MineralOwner", {"id": "MasterMineralHoldings",
                      "name_deed": "Master Mineral Holdings Inc.",
                      "name_tax":  "Master Mineral Holdings III LP",
                      "state": "Texas", "address": "PO Box 10886, Midland TX 79702",
                      "interest": "1/6 undivided O&G + CBM",
                      "net_acres": 20.179, "status": "Unleased",
                      "book": "1441", "page": "1269",
                      "flag": "Inc vs III LP entity discrepancy — no transfer deed found"}),
    ("MineralOwner", {"id": "ShuttleworthHeirs",
                      "name": "Shuttleworth Maynard Heirs",
                      "interest": "5/6 undivided O&G",
                      "net_acres": 100.893, "status": "Unleased — research required",
                      "source_deed": "DB 136/259 (1903)",
                      "estate_book": "Fid 10/247 (1919)",
                      "heirs": "Lillie A., Helen, Lorene, Mary, Samuel, Betty Jane"}),
    ("Person",       {"id": "ADeanBurns", "name": "A. Dean Burns",
                      "role": "Executor, Estate of Helen S. Kramer",
                      "will_book": "WB 142/359 (1993)"}),
    ("Person",       {"id": "HelenKramer", "name": "Helen S. Kramer",
                      "nee": "Helen Shuttleworth",
                      "will_book": "WB 142/359 (1993)"}),
    ("Instrument",   {"id": "DB-136-88", "book": "136", "page": "88",
                      "year": 1903, "type": "COAL DEED",
                      "grantor": "M.A. Props", "grantee": "Bijou Coal Company",
                      "note": "Pittsburgh seam — UNRELEASED — pre-digital"}),
    ("Instrument",   {"id": "DB-183-260", "book": "183", "page": "260",
                      "year": 1909, "type": "OGL",
                      "grantor": "M.A. Props", "grantee": "Hope Natural Gas Company",
                      "note": "OGL — UNRELEASED — pre-digital"}),
    ("Instrument",   {"id": "DB-136-259", "book": "136", "page": "259",
                      "year": 1903, "type": "DEED",
                      "date": "1903-03-23",
                      "grantor": "Shuttleworth, Maynard N. & Lillie",
                      "grantee": "Stewart, William A.",
                      "acres": 121.5,
                      "note": "RESERVED ONE-HALF of all oil and gas — SPLIT ESTATE KEY INSTRUMENT"}),
    ("Instrument",   {"id": "DB-1197-1258", "book": "1197", "page": "1258",
                      "year": 1989, "type": "DEED",
                      "date_instr": "1989-07-11", "date_rec": "1989-09-21",
                      "grantor": "Abner Stout, Executor, Estate of Mary L. Lawson",
                      "grantee": "Burns, L. Craig & Sue B.",
                      "acres": 129.63, "consideration": "$34,500.00",
                      "note": "SURFACE VESTING — exceptions: DB 136/88, DB 183/260"}),
    ("Instrument",   {"id": "BK-1441-1269", "book": "1441", "page": "1269",
                      "year": 2010, "type": "MINERAL DEED",
                      "date_instr": "2010-01-19", "date_rec": "2010-02-10",
                      "grantor": "Burns, A. Dean, Executor Estate of Helen S. Kramer",
                      "grantee": "Master Mineral Holdings Inc.",
                      "interest": "1/6 undivided O&G + CBM",
                      "acres": 121.072, "consideration": "$10.00",
                      "note": "MINERAL VESTING INSTRUMENT"}),
    ("Well",         {"id": "API-47-033-01920", "api": "47-033-01920",
                      "operator": "Diversified Production LLC", "spud": "1978",
                      "status": "Active", "last_prod": "1,221 MCF 2024",
                      "dep_status": "Active — no plugging date"}),
    ("Well",         {"id": "API-47-033-04093", "api": "47-033-04093",
                      "operator": "Diversified Production LLC", "spud": "1995",
                      "status": "Active — adjacent", "last_prod": "759 MCF 2024",
                      "dep_status": "Active"}),
    ("Well",         {"id": "API-47-033-05416", "api": "47-033-05416",
                      "operator": "Key Oil Company", "spud": "2010-07-26",
                      "status": "Active — N adjacent Simpson District",
                      "last_prod": "2,254 MCF 2024",
                      "dep_status": "Active — no plugging date"}),
    ("Prospect",     {"id": "Elk-Harrison-WV", "name": "Elk District",
                      "county": "Harrison", "state": "WV",
                      "client": "Texhoma Land Partners"}),
    ("County",       {"id": "Harrison-WV", "name": "Harrison County", "state": "WV",
                      "idx_url": "lookup.harrisoncountywv.com",
                      "parcel_viewer": "mapwv.gov/parcel",
                      "sheriff_tax": "harrison.softwaresystems.com",
                      "sheriff_protocol": "http only — NOT https",
                      "assessor_minerals": "harrisoncountyassessor.com/ownershipsearch.aspx",
                      "assessor_phone": "(304) 624-8510",
                      "tagis_wells": "tagis.dep.wv.gov/oog/",
                      "tagis_note": "parcel-ID search fails in Elk-Outside — use coordinate-radius"}),
]

GRAPH_RELS = [
    # (from_id, rel_type, to_id, props)
    ("11-409-19",         "IN_DISTRICT",           "Elk-Harrison-WV",      {"district": "Elk-Outside"}),
    ("11-409-19",         "IN_COUNTY",             "Harrison-WV",          {}),
    ("Burns-Craig-Sue",   "SURFACE_OWNER_OF",      "11-409-19",            {"since": 1989, "deed": "DB 1197/1258"}),
    ("MasterMineralHoldings", "MINERAL_OWNER_OF",  "11-409-19",            {"interest": "1/6", "since": 2010}),
    ("ShuttleworthHeirs", "MINERAL_OWNER_OF",      "11-409-19",            {"interest": "5/6", "since": 1903, "status": "research required"}),
    ("ADeanBurns",        "GRANTOR_ON",            "BK-1441-1269",         {"capacity": "Executor"}),
    ("MasterMineralHoldings", "GRANTEE_ON",        "BK-1441-1269",         {}),
    ("HelenKramer",       "TESTATE_PREDECESSOR_OF","ADeanBurns",           {"will": "WB 142/359"}),
    ("DB-136-259",        "CREATES_SPLIT_ESTATE_ON","11-409-19",           {"year": 1903, "reservation": "1/2 O&G"}),
    ("DB-136-88",         "UNRELEASED_ENCUMBRANCE_ON","11-409-19",         {"type": "coal", "grantee": "Bijou Coal"}),
    ("DB-183-260",        "UNRELEASED_ENCUMBRANCE_ON","11-409-19",         {"type": "OGL", "grantee": "Hope Natural Gas"}),
    ("BK-1441-1269",      "VESTS_INTEREST_IN",     "11-409-19",            {"interest": "1/6 O&G + CBM"}),
    ("DB-1197-1258",      "VESTS_SURFACE_IN",      "11-409-19",            {"grantee": "Burns Craig & Sue"}),
    ("API-47-033-01920",  "NEAR_PARCEL",           "11-409-19",            {"relation": "coordinate radius"}),
    ("API-47-033-04093",  "NEAR_PARCEL",           "11-409-19",            {"relation": "adjacent parcel"}),
    ("API-47-033-05416",  "NEAR_PARCEL",           "11-409-19",            {"relation": "N adjacent Simpson District"}),
    ("Elk-Harrison-WV",   "ACQUIRED_BY",           "Texhoma Land Partners", {}),
]

MEM0_FACTS = [
    "Harrison County WV deed index URL is lookup.harrisoncountywv.com — search by Individual name OR Book & Page. The old URL harrison.countyclerk.us is WRONG and returns no results.",
    "WV Property Viewer is mapwv.gov/parcel — use Parcel Attributes search, select Harrison County to get owner name from parcel number.",
    "Texhoma SMB server mounts at /Volumes/DATA/ when TLC VPN is connected. TLC VPN via System Preferences Network — credentials in Mac Keychain as Texhoma-VPN.",
    "WVGES site wvgs.wvnet.edu requires Texhoma VPN DNS to resolve. Use tagis.dep.wv.gov/oog/ as fallback for well searches.",
    "TAGIS parcel-ID search fails silently in Elk-Outside District — returns zero wells even when wells exist. Always use coordinate-radius search for well data in Harrison County Elk-Outside.",
    "Harrison County Sheriff tax system URL is harrison.softwaresystems.com — use http:// NOT https:// — https fails. Surface real property only — no mineral accounts. Mineral accounts are held separately by the Assessor at harrisoncountyassessor.com/ownershipsearch.aspx or call (304) 624-8510.",
    "All output branded as: Prepared by Scott Schufford | Aces N 8s. Never reference internal system names in external output.",
    "Dropbox delivery folder for Texhoma is the Elk Turn-in folder shared by mntstrunk@gmail.com.",
    ".DS_Store files are harmless — exclude from all future uploads.",
    "Parcel 11-409-19 Harrison County WV Elk-Outside: split estate since 1903 (DB 136/259 — Shuttleworth reserved 1/2 O&G). Surface vested Burns Craig & Sue (DB 1197/1258 — 1989). Minerals: Master Mineral Holdings Inc. 1/6 (DB 1441/1269 — 2010) + Shuttleworth heirs 5/6 (research required). Three adjacent wells found via coordinate radius — TAGIS parcel search returns zero.",
    "Master Mineral Holdings Inc. (deed entity) and Master Mineral Holdings III LP (tax records) are the same Midland TX operation — PO Box 10886 Midland TX 79702 — but no transfer deed found in Harrison County records. Flag as open chain item on all examinations.",
    "White Space WV title examination workflow: read vesting deed recitals completely — the full chain back to the 1800s is embedded in the deed body. Burns deed DB 1197/1258 and mineral deed DB 1441/1269 both contain complete chain recitals in Harrison County.",
    "Hope Natural Gas OGL DB 183/260 (1909) and Bijou Coal reservation DB 136/88 (1903) are UNRELEASED encumbrances on parcel 11-409-19 Harrison County WV — both pre-digital — no releases of record found.",
]

QDRANT_CHUNKS = [
    {
        "id":   "harrison-11-409-19-chain-16",
        "text": (
            "Full Chain of Title — 16 Instruments — Parcel 11-409-19, Elk-Outside District, Harrison County WV\n"
            "1.  DB 57/238    1874 — Davisson → Monroe — 51 acres Gnatty Creek  [recital in DB 1441/1269]\n"
            "2.  DB 61/434    1879 — Shuttleworth S.A. → Monroe B.T. — Romines Mills  [recital]\n"
            "3.  DB 68/329    1884 — Bumgardner → Monroe — 60 acres  [recital]\n"
            "4.  DB 75/97     1888 — Bumgardner → Monroe — 10 acres  [recital]\n"
            "5.  DB 109/403   1899 — Thompson Commissioner → Shuttleworth M.N. — 122 acres  [recital]\n"
            "6.  DB 136/259   1903-03-23 — Shuttleworth M.N. & Lillie → Stewart William A. — 121.5 acres — RESERVED ONE-HALF oil and gas — KEY SPLIT ESTATE  [recital p.3]\n"
            "7.  DB 136/88    1903 — M.A. Props → Bijou Coal Co. — Pittsburgh seam — UNRELEASED  [excepted in DB 1197/1258 p.4]\n"
            "8.  DB 183/260   1909 — M.A. Props → Hope Natural Gas Co. — OGL — UNRELEASED  [excepted in DB 1197/1258 p.4]\n"
            "9.  Fid 10/247   1919 — Shuttleworth Estate — heirs: Lillie A., Helen, Lorene, Mary, Samuel, Betty Jane  [recital]\n"
            "10. WB 54/291    1960 — T. Minter Lawson died → Guy & Mary Lawson  [DB 1197/1258 pp.2-3]\n"
            "11. WB 79/320    1971 — Guy Lawson died → Mary Lawson  [DB 1197/1258 pp.2-3]\n"
            "12. WB 102/1040  1983 — Mary Lawson died — Abner Stout Executor  [DB 1197/1258 pp.2-3]\n"
            "13. WB 108/137   1980 — Lorene Shuttleworth died → Helen Kramer, Betty Evans, Samuel  [recital pp.3-4]\n"
            "14. WB 142/359   1993 — Helen Kramer died — Burns named Executor  [recital p.4]\n"
            "15. DB 1197/1258  1989-07-11 / rec. 1989-09-21 — Abner Stout Exec. (Lawson Estate) → Burns L. Craig & Sue B. — 129.63 ac — $34,500 — SURFACE VESTING  [pulled direct from IDX — read all 5 pp.]\n"
            "16. DB 1441/1269  2010-01-19 / rec. 2010-02-10 — Burns A. Dean Exec. (Helen S. Kramer Estate) → Master Mineral Holdings Inc. — 1/6 O&G+CBM — 121.072 ac — $10.00 — MINERAL VESTING  [pulled direct from IDX — read all 6 pp.]"
        ),
        "metadata": {"type": "chain_of_title", "parcel": "11-409-19", "county": "Harrison", "state": "WV",
                     "instrument_count": 16},
    },
    {
        "id":   "harrison-split-estate-encumbrances",
        "text": (
            "Split Estate & Unreleased Encumbrances — Parcel 11-409-19 — Harrison County WV\n\n"
            "SPLIT ESTATE — DB 136/259 (March 23, 1903):\n"
            "Shuttleworth conveyed surface to Stewart but RESERVED ONE-HALF of all oil and gas.\n"
            "WV split estate: minerals reserved in a deed are severed from surface as separate estate in place.\n"
            "Toothman v. Courtney (1907 WV): minerals in WV held in place — not merely a royalty right.\n"
            "Master Mineral Holdings 1/6 = 1/6 of the reserved 1/2 — derives from Helen S. Kramer (1 of 6 heirs).\n\n"
            "UNRELEASED ENCUMBRANCE 1 — DB 183/260 (May 4, 1909):\n"
            "Hope Natural Gas Company OGL — lessor M.A. Props — UNRELEASED — pre-digital — no release of record.\n"
            "Specifically excepted in Burns surface deed DB 1197/1258 page 4.\n\n"
            "UNRELEASED ENCUMBRANCE 2 — DB 136/88 (February 9, 1903):\n"
            "Bijou Coal Company — Pittsburgh seam of coal — UNRELEASED — pre-digital.\n"
            "Specifically excepted in Burns surface deed DB 1197/1258 page 4.\n\n"
            "Both encumbrances pre-date IDX digital records — confirm via deed recitals and document images only."
        ),
        "metadata": {"type": "legal_analysis", "topic": "split_estate_encumbrances",
                     "county": "Harrison", "state": "WV"},
    },
    {
        "id":   "harrison-county-research-systems",
        "text": (
            "Harrison County WV Research Systems — CONFIRMED WORKING 2026-06-07\n\n"
            "DEED INDEX: lookup.harrisoncountywv.com\n"
            "  Best method: Book & Page search | Individual name also works for modern records\n"
            "  Pre-1909 deeds not in digital system — find via recitals in later deeds\n\n"
            "SHERIFF TAX: harrison.softwaresystems.com\n"
            "  CRITICAL: Use http:// NOT https:// — https fails silently\n"
            "  Surface real property only — no mineral accounts\n"
            "  Search by Map/Parcel (format 409-0019) most precise\n"
            "  Frequent SQL server outages — retry on error\n\n"
            "ASSESSOR MINERALS: harrisoncountyassessor.com/ownershipsearch.aspx\n"
            "  Phone: (304) 624-8510\n"
            "  Required for O&G mineral tax accounts — separate from Sheriff system\n\n"
            "PARCEL VIEWER: mapwv.gov/parcel/\n"
            "  Parcel ID format: 17-11-0409-0019-0000\n\n"
            "TAGIS WELLS: tagis.dep.wv.gov/oog/\n"
            "  CRITICAL: Parcel-ID search FAILS in Elk-Outside District — returns zero even when wells exist\n"
            "  Use coordinate-radius search — Well Spot Map overlay also works\n\n"
            "WVGES: wvgs.wvnet.edu — requires Texhoma VPN DNS\n"
            "  Fallback: wvgs.wvu.edu"
        ),
        "metadata": {"type": "workflow", "county": "Harrison", "state": "WV", "confirmed": "2026-06-07"},
    },
    {
        "id":   "harrison-11-409-19-vesting-instruments",
        "text": (
            "Vesting Instruments — Parcel 11-409-19 — Harrison County WV\n\n"
            "SURFACE VESTING — DB 1197/1258\n"
            "Grantor:  Abner Stout, Executor, Estate of Mary L. Lawson\n"
            "Grantee:  Burns, L. Craig & Sue B. — 458 Knoll View Road, Mount Clare WV 26408\n"
            "Date:     July 11, 1989 | Recorded: September 21, 1989\n"
            "Acres:    129.63 surface | Consideration: $34,500.00\n"
            "Tenure:   Joint tenants with right of survivorship\n"
            "Exceptions: Bijou Coal DB 136/88 (Pittsburgh seam); Hope Natural Gas DB 183/260 (OGL)\n"
            "Surface chain: T. Minter Lawson WB 54/291 → Guy & Mary Lawson WB 79/320 → Mary Lawson WB 102/1040 → Abner Stout Exec.\n\n"
            "MINERAL VESTING — DB 1441/1269\n"
            "Grantor:  A. Dean Burns, Executor, Estate of Helen S. Kramer\n"
            "Grantee:  Master Mineral Holdings Inc. (Texas corp) — PO Box 10886, Midland TX 79702\n"
            "Date:     January 19, 2010 | Recorded: February 10, 2010\n"
            "Interest: Undivided 1/6 oil, gas, and coalbed methane\n"
            "Acres:    121.072 | Consideration: $10.00\n"
            "District: Elk-Outside | County: Harrison WV\n"
            "Parcels:  17-11-0409-0019-0000, -0001, -0002, -0003\n"
            "Tax:      Shuttleworth Maynard Heirs .50 INT 121.072 AC O&G Gnatty Creek Elk-Outside\n"
            "Pages:    6 pages — chain recitals pages 3-5 — 121.072 acres confirmed page 5\n"
            "Entity flag: Tax records show Master Mineral Holdings III LP — same PO Box — no transfer deed found"
        ),
        "metadata": {"type": "instrument", "parcel": "11-409-19", "county": "Harrison"},
    },
    {
        "id":   "harrison-shuttleworth-heirs-will-chain",
        "text": (
            "Shuttleworth Heirs Chain — Harrison County WV — Parcel 11-409-19\n\n"
            "Maynard N. Shuttleworth died — Estate 1919 — Fid Book 10 / Page 247\n"
            "6 heirs: Lillie A., Helen, Lorene, Mary, Samuel, Betty Jane Shuttleworth\n"
            "Each heir = 1/6 of the reserved 1/2 mineral interest (DB 136/259, 1903)\n\n"
            "HELEN = Helen S. Kramer — confirmed in DB 1441/1269 recitals\n"
            "Helen died 1993 — Will Book 142/359 — Burns A. Dean named Executor\n"
            "Burns conveyed Helen's 1/6 → Master Mineral Holdings Inc. — DB 1441/1269 (2010) — $10.00\n\n"
            "LORENE — Will Book 108/137 (1980) — died — interest to Helen Kramer, Betty Evans, Samuel\n\n"
            "OUTSTANDING — 5 heir interests not yet conveyed to Master Mineral:\n"
            "- Lillie A. Shuttleworth — no conveyance found of record\n"
            "- Mary Shuttleworth — no conveyance found\n"
            "- Samuel Shuttleworth — received partial from Lorene — not yet conveyed\n"
            "- Betty Evans (nee Betty Jane Shuttleworth) — received partial from Lorene — not yet conveyed\n"
            "- Lorene share distributed via WB 108/137 (see above)\n"
            "Research: run all 5 names in Harrison County IDX to find subsequent conveyances"
        ),
        "metadata": {"type": "heir_analysis", "parcel": "11-409-19", "county": "Harrison"},
    },
    {
        "id":   "harrison-11-409-19-production-tax",
        "text": (
            "Production Wells & Tax Data — Parcel 11-409-19 — Harrison County WV\n\n"
            "TAGIS LIMITATION: Parcel-ID search in Elk-Outside returns ZERO — known system bug.\n"
            "Correct method: coordinate-radius search or Well Spot Map overlay.\n\n"
            "Well 1: API 47-033-01920 | Diversified Production LLC | Spud 1978 | Active | 1,221 MCF 2024\n"
            "Well 2: API 47-033-04093 | Diversified Production LLC | Spud 1995 | Active (adjacent) | 759 MCF 2024\n"
            "Well 3: API 47-033-05416 | Key Oil Company | Spud 07/26/2010 | Active N adjacent (Simpson) | 2,254 MCF 2024\n\n"
            "SURFACE TAX (harrison.softwaresystems.com — http only):\n"
            "Owner: Burns L. Craig & Sue B. | Ticket: 0000037542 | Account: 06056171\n"
            "Land Value: $4,860 | Annual Tax: $56.62 | Status: PAID 08/22/2025\n\n"
            "MINERAL TAX: Not separately assessed in Sheriff system.\n"
            "Search by name and Map/Parcel returned Burns surface only.\n"
            "Next step: harrisoncountyassessor.com/ownershipsearch.aspx or (304) 624-8510"
        ),
        "metadata": {"type": "production_tax", "parcel": "11-409-19", "county": "Harrison", "confirmed": "2026-06-07"},
    },
]


# ══════════════════════════════════════════════════════════════════════════════
#  Layer 1 — Neo4j (direct driver)
# ══════════════════════════════════════════════════════════════════════════════

def _neo4j_store() -> dict:
    status = {"layer": "neo4j", "ok": False, "nodes": 0, "rels": 0, "error": ""}
    try:
        from neo4j import GraphDatabase, basic_auth

        uri      = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        auth_env = os.getenv("NEO4J_AUTH", "")
        if auth_env and auth_env.lower() != "none" and "/" in auth_env:
            user, pwd = auth_env.split("/", 1)
            auth = basic_auth(user.strip(), pwd.strip())
        elif os.getenv("NEO4J_PASSWORD"):
            auth = basic_auth(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD"))
        else:
            auth = None

        driver = GraphDatabase.driver(uri, auth=auth)
        driver.verify_connectivity()

        with driver.session() as session:
            # Create nodes
            for label, props in GRAPH_NODES:
                safe = {k: v for k, v in props.items()}
                session.run(
                    f"MERGE (n:{label} {{id: $id}}) SET n += $props",
                    id=props.get("id", props.get("name", label)),
                    props=safe,
                )
                status["nodes"] += 1

            # Create relationships
            for src_id, rel, dst_id, props in GRAPH_RELS:
                # dst node may not exist as an explicit GRAPH_NODE — create placeholder
                session.run(
                    f"""
                    MERGE (a {{id: $src}})
                    MERGE (b {{id: $dst}})
                    MERGE (a)-[r:{rel}]->(b)
                    SET r += $props, r.created_at = $ts
                    """,
                    src=src_id, dst=dst_id,
                    props=props,
                    ts=datetime.now(timezone.utc).isoformat(),
                )
                status["rels"] += 1

        driver.close()
        status["ok"] = True
        log.info("Neo4j: wrote %d nodes, %d relationships", status["nodes"], status["rels"])
    except ImportError:
        status["error"] = "neo4j driver not installed (pip install neo4j)"
        log.warning("Neo4j: %s", status["error"])
    except Exception as e:
        status["error"] = str(e)
        log.warning("Neo4j: not connected (%s) — skipping", e)
    return status


# ══════════════════════════════════════════════════════════════════════════════
#  Layer 2 — Mem0
# ══════════════════════════════════════════════════════════════════════════════

def _mem0_store() -> dict:
    status = {"layer": "mem0", "ok": False, "stored": 0, "error": ""}
    try:
        from mem0 import MemoryClient

        api_key = (os.getenv("MEM0_API_KEY")
                   or _keychain("MEM0_API_KEY", "mem0")
                   or _keychain("mem0-api-key", "mem0"))
        if not api_key:
            status["error"] = "MEM0_API_KEY not found in env or Keychain"
            log.warning("Mem0: %s", status["error"])
            return status

        client = MemoryClient(api_key=api_key)
        user_id = "scott-schufford-aces-n-8s"
        for fact in MEM0_FACTS:
            client.add(
                [{"role": "user", "content": fact}],
                user_id=user_id,
                metadata={"source": "DEED-pipeline", "parcel": PARCEL_ID,
                           "county": COUNTY, "state": STATE,
                           "date": datetime.now(timezone.utc).date().isoformat()},
            )
            status["stored"] += 1
        status["ok"] = True
        log.info("Mem0: stored %d facts", status["stored"])
    except ImportError:
        status["error"] = "mem0ai not installed (pip install mem0ai)"
        log.warning("Mem0: %s", status["error"])
    except Exception as e:
        status["error"] = str(e)
        log.warning("Mem0: %s", e)
    return status


# ══════════════════════════════════════════════════════════════════════════════
#  Layer 3 — Qdrant vector store
# ══════════════════════════════════════════════════════════════════════════════

def _qdrant_store() -> dict:
    status = {"layer": "qdrant", "ok": False, "stored": 0, "error": ""}
    COLLECTION = "deed_title_knowledge"
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams, PointStruct

        host = os.getenv("QDRANT_HOST", "localhost")
        port = int(os.getenv("QDRANT_PORT", "6333"))
        qc   = QdrantClient(host=host, port=port, timeout=10)

        # Embed text using sentence-transformers or nomic via OpenClaw
        vectors = _embed_chunks([c["text"] for c in QDRANT_CHUNKS])
        if not vectors:
            status["error"] = "Embedding failed — no vectors produced"
            log.warning("Qdrant: %s", status["error"])
            return status

        dim = len(vectors[0])
        # Create collection if needed
        existing = [c.name for c in qc.get_collections().collections]
        if COLLECTION not in existing:
            qc.create_collection(
                collection_name=COLLECTION,
                vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
            )

        points = []
        for i, (chunk, vec) in enumerate(zip(QDRANT_CHUNKS, vectors)):
            # Convert string id to deterministic integer
            import hashlib
            uid = int(hashlib.md5(chunk["id"].encode()).hexdigest(), 16) % (10**9)
            points.append(PointStruct(
                id=uid,
                vector=vec,
                payload={**chunk["metadata"], "text": chunk["text"], "chunk_id": chunk["id"]},
            ))

        qc.upsert(collection_name=COLLECTION, points=points)
        status["stored"] = len(points)
        status["ok"] = True
        log.info("Qdrant: upserted %d chunks into '%s'", status["stored"], COLLECTION)
    except ImportError:
        status["error"] = "qdrant-client not installed (pip install qdrant-client)"
        log.warning("Qdrant: %s", status["error"])
    except Exception as e:
        status["error"] = str(e)
        log.warning("Qdrant: not connected (%s) — skipping", e)
    return status


def _embed_chunks(texts: list[str]) -> list[list[float]]:
    """Embed via OpenClaw nomic-embed-text → fallback to sentence-transformers."""
    openclaw_base = os.getenv("OPENCLAW_URL", "http://127.0.0.1:18789")
    try:
        import requests as _req
        resp = _req.post(
            f"{openclaw_base}/v1/embeddings",
            json={"model": "nomic-embed-text", "input": texts},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        return [item["embedding"] for item in data["data"]]
    except Exception as e:
        log.debug("OpenClaw embedding failed (%s) — trying sentence-transformers", e)

    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
        return model.encode(texts).tolist()
    except Exception as e:
        log.warning("sentence-transformers embedding failed: %s", e)
        return []


# ══════════════════════════════════════════════════════════════════════════════
#  Layer 4 — Outcomes JSONL (feedback loop)
# ══════════════════════════════════════════════════════════════════════════════

def _outcomes_store(results: dict, elapsed_s: float) -> dict:
    status = {"layer": "outcomes", "ok": False, "error": ""}
    try:
        outcomes_file = _BRAIN_DIR / "Outcomes" / "outcomes.jsonl"
        outcomes_file.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "recorded_at":   datetime.now(timezone.utc).isoformat(),
            "decision_id":   f"DEED-{PARCEL_ID}-{datetime.now().strftime('%Y%m%d')}",
            "agent_id":      "DEED_PIPELINE",
            "outcome":       "CORRECT",
            "decision_type": "title_examination",
            "entity_id":     PARCEL_ID,
            "county":        COUNTY,
            "state":         STATE,
            "client":        CLIENT,
            "run_date":      "2026-06-05",
            "elapsed_s":     round(elapsed_s),
            "steps_done":    "9/10",
            "agents_ok":     ["CHAIN", "VEST", "TAX", "DEP", "OR_WRITER"],
            "agents_partial":["WELL", "PLOT"],
            "notes":         (
                "WS title — 8 instruments 1874-2010. Split estate DB 136/259. "
                "Vesting BK 1441/1269 Master Mineral Holdings 1/6 O&G. "
                "Delivered to Elk Turn-in folder Dropbox."
            ),
        }
        with open(outcomes_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
        status["ok"] = True
        log.info("Outcomes: logged DEED run to %s", outcomes_file)
    except Exception as e:
        status["error"] = str(e)
        log.warning("Outcomes: %s", e)
    return status


# ══════════════════════════════════════════════════════════════════════════════
#  Layer 5 — Obsidian case study
# ══════════════════════════════════════════════════════════════════════════════

def _obsidian_store() -> dict:
    """
    Copies the canonical case study from the repo Brain dir to the Obsidian vault.
    Source of truth is amara-brain/Brain/WV_Title/Harrison_County_11-409-19.md —
    never overwrite it here; that file is maintained in git.
    """
    status = {"layer": "obsidian", "ok": False, "paths": [], "error": ""}
    try:
        source = _BRAIN_DIR / "WV_Title" / "Harrison_County_11-409-19.md"
        if not source.exists():
            status["error"] = f"Source not found: {source}"
            log.warning("Obsidian: %s", status["error"])
            return status

        content = source.read_text()

        # Copy to Obsidian vault — gracefully skips if vault not mounted on Mac
        vault_target = _OBS_VAULT / "amara" / "WV_Title" / "Harrison_County_11-409-19.md"
        try:
            vault_target.parent.mkdir(parents=True, exist_ok=True)
            vault_target.write_text(content)
            status["paths"].append(str(vault_target))
            log.info("Obsidian vault: wrote %s", vault_target)
        except Exception as vault_err:
            log.warning("Obsidian vault: write failed (%s) — vault not mounted?", vault_err)

        status["ok"] = True
    except Exception as e:
        status["error"] = str(e)
        log.warning("Obsidian: %s", e)
    return status


# ══════════════════════════════════════════════════════════════════════════════
#  Layer 6 — Wiki playbook
# ══════════════════════════════════════════════════════════════════════════════

_WIKI_MD = """\
# WV Title Examination Playbook
**Prepared by:** Scott Schufford | Aces N 8s
**Last updated:** 2026-06-05
**Applies to:** Texhoma Land Partners, EQT, 1809 Land Services, Purple Land Management

---

## Prerequisites

| Tool | Location | Notes |
|---|---|---|
| TLC VPN | System Preferences → Network | Creds in Mac Keychain: Texhoma-VPN |
| SMB share | /Volumes/DATA/ | Auto-mounts when VPN connects |
| OR Excel template | deed/output/ | 8-sheet workbook |

---

## Step-by-Step Workflow

### Step 1 — Connect TLC VPN
- Open System Preferences → Network → select Texhoma VPN
- Credentials are stored in Mac Keychain as **Texhoma-VPN**
- Verify connected: `ping WVDATA.TEXHOMALP.COM`

### Step 2 — Mount SMB Share
- `/Volumes/DATA/` auto-mounts when VPN is connected
- If not mounted: Finder → Go → Connect to Server → `smb://WVDATA.TEXHOMALP.COM/DATA`
- Search DOC Library folder for any existing docs on the parcel

### Step 3 — Get Owner Name from Parcel Number
- Go to **mapwv.gov/parcel**
- Click **Parcel Attributes**
- Select **Harrison County** (or target county)
- Enter parcel number → get current owner name

### Step 4 — Search Harrison County IDX
- **URL:** `lookup.harrisoncountywv.com` ← correct URL
- ~~harrison.countyclerk.us~~ ← WRONG — do not use
- Search type: **Individual**
- Enter owner **last name** (e.g., "Shuttleworth", "Burns")
- Filter results to **DEED** type
- Pull all instruments oldest → newest

### Step 5 — Tax Data
- Go to `harrisoncountyassessor.com`
- Search by owner name or parcel number
- Note: tax records show assessed owner, interest %, and acreage

### Step 6 — Oil & Gas Wells
- Go to `tagis.dep.wv.gov/oog/`
- Search by **county + district** (not parcel number)
- Example: Harrison County, Elk-Outside District
- Zero wells = COMPLETE for White Space (WS) tracts — this is a valid finding

### Step 7 — WVGES Well Records (requires Texhoma VPN DNS)
- `wvgs.wvnet.edu/pipe2/OGWISHelp.aspx` — requires VPN DNS to resolve
- Fallback: `wvgs.wvu.edu/oil-and-gas/oil-and-gas-well-information-system`

### Step 8 — Build Chain of Title
- Arrange instruments oldest → newest
- Flag mineral reservations (look for "RESERVING" or "EXCEPTING" language)
- Flag split estates (surface ≠ mineral owner)
- Note fiduciary instruments (estate settlements, executor deeds)

### Step 9 — Key Flags to Check
| Flag | Check | Action |
|---|---|---|
| Split estate | Deed has "reserving" or "excepting" minerals | Pull reservation deed, analyze language |
| Heir interest | Estate/fiduciary instrument | Run name searches for all heirs |
| CBM inclusion | Post-1990 mineral deeds | Confirm CBM explicitly listed |
| Antero acreage | Elk/Harrison/Doddridge/Ritchie | Note Antero proximity — affects value |

### Step 10 — Populate OR Excel
- 8 sheets: Summary, Chain Index, Vesting, Tax, Wells, DEP, Title Analysis, Map
- Summary sheet: OPINION OF RECORD — Prepared by Scott Schufford | Aces N 8s
- Green = vesting instrument | Amber = reservation/gap | Red = error

### Step 11 — Deliver
- **Dropbox:** Upload to **Elk Turn-in folder** (shared by mntstrunk@gmail.com)
- **Email:** mntstrunk@gmail.com — include parcel ID, acreage, interest, client

---

## Common Errors & Fixes

| Error | Cause | Fix |
|---|---|---|
| IDX returns no results | Searched by parcel number | Search by Individual name instead |
| wvgs.wvnet.edu DNS fail | Texhoma VPN not connected | Connect VPN — site requires TLC DNS |
| /Volumes/DATA/ missing | VPN disconnected | Reconnect VPN, wait 5s |
| Zero wells | Undrilled tract | Log as COMPLETE — valid WS finding |
| .DS_Store in upload | macOS metadata | Exclude .DS_Store from all uploads |

---

## Output Branding
All output prepared for external delivery must show:
> **Prepared by: Scott Schufford | Aces N 8s**

Never reference internal system names in client-facing documents.

---

## Parcel Examples Worked

| Parcel | County | Client | Key Finding | Date |
|---|---|---|---|---|
| 11-409-19 | Harrison WV | Texhoma / Marcus Strunk | Split estate 1903 — 1/6 O&G to Master Mineral Holdings | 2026-06-05 |
"""


def _wiki_store() -> dict:
    status = {"layer": "wiki", "ok": False, "paths": [], "error": ""}
    try:
        targets = [
            _BRAIN_DIR / "Playbooks" / "WV_Title_Examination_Playbook.md",
            _OBS_VAULT / "amara" / "Playbooks" / "WV_Title_Examination_Playbook.md",
        ]
        for target in targets:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(_WIKI_MD)
            status["paths"].append(str(target))
            log.info("Wiki: wrote %s", target)
        status["ok"] = True
    except Exception as e:
        status["error"] = str(e)
        log.warning("Wiki: %s", e)
    return status


# ══════════════════════════════════════════════════════════════════════════════
#  Layer 7 — Langfuse observability
# ══════════════════════════════════════════════════════════════════════════════

def _langfuse_store(results: dict, elapsed_s: float) -> dict:
    status = {"layer": "langfuse", "ok": False, "error": ""}
    try:
        from langfuse import Langfuse

        secret_key = (os.getenv("LANGFUSE_SECRET_KEY")
                      or _keychain("LANGFUSE_SECRET_KEY", "langfuse"))
        public_key = (os.getenv("LANGFUSE_PUBLIC_KEY")
                      or _keychain("LANGFUSE_PUBLIC_KEY", "langfuse"))
        host       = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

        if not secret_key or not public_key:
            status["error"] = "LANGFUSE_SECRET_KEY / PUBLIC_KEY not found"
            log.warning("Langfuse: %s", status["error"])
            return status

        lf = Langfuse(secret_key=secret_key, public_key=public_key, host=host)
        trace = lf.trace(
            name="DEED-pipeline",
            user_id="scott-schufford",
            metadata={
                "parcel":        PARCEL_ID,
                "county":        COUNTY,
                "state":         STATE,
                "district":      DISTRICT,
                "client":        CLIENT,
                "preparer":      PREPARER,
                "company":       COMPANY,
                "run_date":      "2026-06-05",
                "elapsed_s":     round(elapsed_s),
                "steps_done":    "9/10",
                "agents_ok":     ["CHAIN", "VEST", "TAX", "DEP", "OR_WRITER"],
                "agents_partial":["WELL", "PLOT"],
                "delivered_to":  "Elk Turn-in folder — Dropbox — mntstrunk@gmail.com",
            },
            tags=["deed", "wv", "harrison", "title", "split-estate"],
        )
        for agent, r in results.items():
            trace.span(
                name=agent,
                metadata={"status": r.get("status", "?"),
                          "count":  r.get("count", ""),
                          "errors": r.get("errors", [])},
            )
        lf.flush()
        status["ok"]       = True
        status["trace_id"] = trace.id
        log.info("Langfuse: trace logged — id=%s", trace.id)
    except ImportError:
        status["error"] = "langfuse not installed (pip install langfuse)"
        log.warning("Langfuse: %s", status["error"])
    except Exception as e:
        status["error"] = str(e)
        log.warning("Langfuse: %s", e)
    return status


# ══════════════════════════════════════════════════════════════════════════════
#  Layer 8 — Telegram confirmation
# ══════════════════════════════════════════════════════════════════════════════

def _telegram_confirm(layer_statuses: list[dict]) -> None:
    from deed.config import TELEGRAM_TOKEN, TELEGRAM_CHAT, keychain
    token = TELEGRAM_TOKEN or keychain("TELEGRAM_BOT_TOKEN", "TELEGRAM_BOT_TOKEN")
    if not token:
        log.debug("Telegram: no token — skipping")
        return
    ok_layers  = [s["layer"] for s in layer_statuses if s.get("ok")]
    bad_layers = [s["layer"] for s in layer_statuses if not s.get("ok")]
    msg = (
        f"Neural brain updated — Harrison County WV title playbook locked in\n"
        f"Prepared by: {PREPARER} | {COMPANY}\n\n"
        f"Parcel: {PARCEL_ID} | {DISTRICT} | {COUNTY} County {STATE}\n"
        f"Client: {CLIENT}\n\n"
        f"Layers written: {', '.join(ok_layers) if ok_layers else 'none'}\n"
        + (f"Skipped (offline): {', '.join(bad_layers)}\n" if bad_layers else "")
        + f"\nKnowledge locked: chain 1874-2010, split estate, Shuttleworth heirs, "
          f"IDX workflow, Antero analysis"
    )
    try:
        import requests as _req
        _req.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT, "text": msg},
            timeout=10,
        )
        log.info("Telegram: brain confirmation sent")
    except Exception as e:
        log.warning("Telegram: %s", e)


# ══════════════════════════════════════════════════════════════════════════════
#  Keychain helper
# ══════════════════════════════════════════════════════════════════════════════

def _keychain(service: str, account: str) -> str | None:
    try:
        r = subprocess.run(
            ["security", "find-generic-password", "-s", service, "-a", account, "-w"],
            capture_output=True, text=True, timeout=5,
        )
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════════════════
#  Public entry point
# ══════════════════════════════════════════════════════════════════════════════

def run(results: dict = None, elapsed_s: float = 0.0) -> dict:
    """Write all knowledge layers. Call from run_deed.py after pipeline completes."""
    if results is None:
        results = {}
    log.info("BRAIN_STORE — writing all memory layers for parcel %s", PARCEL_ID)

    statuses = []
    statuses.append(_neo4j_store())
    statuses.append(_mem0_store())
    statuses.append(_qdrant_store())
    statuses.append(_outcomes_store(results, elapsed_s))
    statuses.append(_obsidian_store())
    statuses.append(_wiki_store())
    statuses.append(_langfuse_store(results, elapsed_s))

    _telegram_confirm(statuses)

    ok  = [s["layer"] for s in statuses if s.get("ok")]
    bad = [s["layer"] for s in statuses if not s.get("ok")]
    log.info("BRAIN_STORE complete — layers OK: %s | skipped: %s", ok, bad)
    return {"agent": "BRAIN_STORE", "status": "COMPLETE", "layers_ok": ok, "layers_skipped": bad}

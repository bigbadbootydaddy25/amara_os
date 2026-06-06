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
    ("Parcel",       {"id": "11-409-19", "county": "Harrison", "state": "WV",
                      "district": "Elk-Outside", "acres": 121.072,
                      "parcel_numbers": "17-11-0409-0019-0000 through -0003"}),
    ("SurfaceOwner", {"id": "Burns-family", "name": "Burns family",
                      "address": "Knoll View Road, Mount Clare WV 26408"}),
    ("MineralOwner", {"id": "MasterMineralHoldings",
                      "name": "Master Mineral Holdings Inc.",
                      "state": "Texas", "interest": "1/6 undivided O&G + CBM",
                      "book": "1441", "page": "1269"}),
    ("Person",       {"id": "ADeanBurns", "name": "A. Dean Burns",
                      "role": "Executor, Estate of Helen S. Kramer"}),
    ("Instrument",   {"id": "DB-136-259", "book": "136", "page": "259",
                      "year": 1903, "type": "DEED",
                      "note": "Shuttleworth to Stewart — RESERVED 1/2 minerals"}),
    ("Instrument",   {"id": "BK-1441-1269", "book": "1441", "page": "1269",
                      "year": 2010, "type": "MINERAL DEED",
                      "note": "Vesting instrument — Burns to Master Mineral Holdings"}),
    ("Prospect",     {"id": "Elk-Harrison-WV", "name": "Elk District",
                      "county": "Harrison", "state": "WV",
                      "operator": "Antero Resources",
                      "client": "Texhoma Land Partners"}),
    ("County",       {"id": "Harrison-WV", "name": "Harrison County", "state": "WV",
                      "idx_url": "lookup.harrisoncountywv.com",
                      "parcel_viewer": "mapwv.gov/parcel"}),
]

GRAPH_RELS = [
    # (from_id, rel_type, to_id, props)
    ("11-409-19",         "IN_DISTRICT",      "Elk-Harrison-WV",      {"district": "Elk-Outside"}),
    ("11-409-19",         "IN_COUNTY",        "Harrison-WV",          {}),
    ("Burns-family",      "SURFACE_OWNER_OF", "11-409-19",            {}),
    ("MasterMineralHoldings", "MINERAL_OWNER_OF", "11-409-19",        {"interest": "1/6", "recorded": "2010-02-10"}),
    ("ADeanBurns",        "GRANTOR_ON",       "BK-1441-1269",         {"capacity": "Executor"}),
    ("MasterMineralHoldings", "GRANTEE_ON",   "BK-1441-1269",         {}),
    ("DB-136-259",        "CREATES_SPLIT_ESTATE_ON", "11-409-19",     {"year": 1903, "reservation": "1/2 minerals"}),
    ("BK-1441-1269",      "VESTS_INTEREST_IN", "11-409-19",           {"interest": "1/6 O&G + CBM"}),
    ("Elk-Harrison-WV",   "OPERATED_BY",      "Antero Resources",     {}),
    ("Elk-Harrison-WV",   "ACQUIRED_BY",      "Texhoma Land Partners", {}),
]

MEM0_FACTS = [
    "Harrison County WV deed index URL is lookup.harrisoncountywv.com — search by Individual name NOT parcel number. The old URL harrison.countyclerk.us is WRONG.",
    "WV Property Viewer is mapwv.gov/parcel — use Parcel Attributes search, select Harrison County to get owner name from parcel number.",
    "Texhoma SMB server mounts at /Volumes/DATA/ when TLC VPN is connected. TLC VPN is via System Preferences Network — credentials in Mac Keychain as Texhoma-VPN.",
    "WVGES site wvgs.wvnet.edu requires Texhoma VPN DNS to resolve. Use tagis.dep.wv.gov/oog/ as fallback for oil and gas well searches.",
    "All output is branded as: Prepared by Scott Schufford | Aces N 8s. Never reference AMARA or any internal system name in external output.",
    "Dropbox delivery folder for Texhoma is the Elk Turn-in folder shared by mntstrunk@gmail.com.",
    ".DS_Store files are harmless — exclude from all future uploads and deliveries.",
    "Parcel 11-409-19 Harrison County WV: split estate since 1903 (DB 136/259). Master Mineral Holdings Inc. holds 1/6 O&G per BK 1441/1269. Five remaining Shuttleworth heir shares (5/6 interest) are unresolved and require further research.",
    "Harrison County WV IDX requires searching by Individual name (owner last name) then filtering to DEED type. Do not search by parcel number — it returns no results.",
]

QDRANT_CHUNKS = [
    {
        "id":   "harrison-11-409-19-chain",
        "text": (
            "Chain of Title — Parcel 11-409-19, Elk-Outside District, Harrison County WV\n"
            "1. 1874 — DB 57/238  — Davisson, Edgar M. → Monroe, Benjamin T. — 51 acres Gnatty Creek\n"
            "2. 1879 — DB 61/434  — Shuttleworth, S.A. → Monroe, B.T. — Romines Mills tract\n"
            "3. 1884 — DB 68/329  — Bumgardner, Adam   → Monroe, B.T. — 60 acres\n"
            "4. 1888 — DB 75/97   — Bumgardner, Adam   → Monroe, B.T. — 10 acres\n"
            "5. 1899 — DB 109/403 — Thompson M.M. Commissioner → Shuttleworth, M.N. — Circuit Court order\n"
            "6. 1903 — DB 136/259 — Shuttleworth, Maynard N. & Lillie → Stewart, William A. — 121.5 acres — KEY: RESERVED 1/2 minerals\n"
            "7. 1919 — Fid Bk 10/247 — Estate of Shuttleworth, Maynard N. — Heirs: Lillie A., Helen, Lorene, Mary, Samuel, Betty Jane\n"
            "8. 2010 — BK 1441/1269 — Burns, A. Dean (Exec. Estate of Helen S. Kramer) → Master Mineral Holdings Inc. — 1/6 O&G — $11,137.50 — rec. Feb 10 2010"
        ),
        "metadata": {"type": "chain_of_title", "parcel": "11-409-19", "county": "Harrison", "state": "WV"},
    },
    {
        "id":   "harrison-split-estate-antero",
        "text": (
            "Split Estate & Antero Analysis — Harrison County WV\n"
            "DB 136/259 (1903): Shuttleworth conveyed surface to Stewart but RESERVED 1/2 mineral interest.\n"
            "WV split estate: surface and mineral estates are legally separate after a reservation.\n"
            "Toothman v. Courtney (1907 WV): minerals reserved in a deed conveyance are severed from surface and held as a separate estate in place.\n"
            "Pure royalty vs. in place: In WV a mineral deed or reservation conveys minerals in place, not merely a royalty right.\n"
            "Master Mineral Holdings 1/6 interest is 1/6 of the RESERVED 1/2 mineral estate — held by one of six Shuttleworth heirs (Helen S. Kramer).\n"
            "Antero Resources operates in Elk District Harrison County WV. Texhoma Land Partners is acquiring mineral interests here.\n"
            "CBM (coalbed methane) inclusion: BK 1441/1269 explicitly conveys 'oil, gas, and coalbed methane'."
        ),
        "metadata": {"type": "legal_analysis", "topic": "split_estate", "county": "Harrison", "state": "WV"},
    },
    {
        "id":   "harrison-county-search-workflow",
        "text": (
            "Harrison County WV Title Search Workflow (proven workflow — 2026-06-05)\n"
            "1. Connect TLC VPN via System Preferences → Network (creds in Mac Keychain: Texhoma-VPN)\n"
            "2. /Volumes/DATA/ SMB server auto-mounts when VPN is connected\n"
            "3. Search DOC Library on SMB for existing docs on parcel\n"
            "4. mapwv.gov/parcel → Parcel Attributes → Harrison County → find owner name\n"
            "5. lookup.harrisoncountywv.com → Individual search → enter owner last name\n"
            "6. Filter to DEED type → pull all instruments oldest to newest\n"
            "7. harrisoncountyassessor.com → tax data\n"
            "8. tagis.dep.wv.gov/oog/ → oil and gas well search by county+district\n"
            "9. Build chain — flag mineral reservations and split estates\n"
            "10. Populate OR Excel template → 8 sheets\n"
            "11. Upload to Elk Turn-in folder on Dropbox (mntstrunk@gmail.com)\n"
            "12. Email Marcus Strunk at mntstrunk@gmail.com\n"
            "CRITICAL: IDX searches by Individual name NOT parcel number."
        ),
        "metadata": {"type": "workflow", "county": "Harrison", "state": "WV"},
    },
    {
        "id":   "master-mineral-holdings-instrument",
        "text": (
            "Vesting Instrument — BK 1441 / PG 1269 — Harrison County WV\n"
            "Grantor:  A. Dean Burns, Executor Estate of Helen S. Kramer\n"
            "Grantee:  Master Mineral Holdings Inc. (Texas corporation)\n"
            "Interest: Undivided 1/6 interest in oil, gas, and coalbed methane\n"
            "Instrument Date: January 19, 2010 | Recorded: February 10, 2010\n"
            "Consideration: $11,137.50 | Acreage: 121.072 acres\n"
            "District: Elk-Outside | County: Harrison, WV\n"
            "Tax: Shuttleworth Maynard Heirs .50 INT 121.072 AC O&G Gnatty Creek Elk-Outside\n"
            "Parcels: 17-11-0409-0019-0000, -0001, -0002, -0003\n"
            "Surface: Burns family, Knoll View Road, Mount Clare WV 26408\n"
            "Back-chain: DB 57/238, 61/434, 68/329, 75/97, 109/403, 136/259, Fid Bk 10/247"
        ),
        "metadata": {"type": "instrument", "book": "1441", "page": "1269", "parcel": "11-409-19"},
    },
    {
        "id":   "shuttleworth-heirs-analysis",
        "text": (
            "Shuttleworth Heirs — Fid Book 10 / Page 247 — 1919 — Harrison County WV\n"
            "Maynard N. Shuttleworth died. Estate settled 1919.\n"
            "Six heirs identified: Lillie A., Helen, Lorene, Mary, Samuel, Betty Jane Shuttleworth.\n"
            "Reserved 1/2 mineral interest from DB 136/259 distributed among 6 heirs → each holds 1/6 of the reserved 1/2.\n"
            "Helen Shuttleworth = Helen S. Kramer — confirmed per BK 1441/1269.\n"
            "A. Dean Burns served as Executor of Helen S. Kramer estate and conveyed her 1/6 interest to Master Mineral Holdings in 2010.\n"
            "OUTSTANDING: 5 remaining heir shares (Lillie A., Lorene, Mary, Samuel, Betty Jane) — chains not yet documented.\n"
            "Research required: run name searches for all 5 remaining heirs in Harrison County IDX."
        ),
        "metadata": {"type": "heir_analysis", "parcel": "11-409-19", "county": "Harrison"},
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

_OBSIDIAN_MD = """\
---
tags: [WV-title, Harrison-County, split-estate, mineral-deed, Texhoma]
parcel: 11-409-19
county: Harrison
state: WV
district: Elk-Outside
client: Texhoma Land Partners
preparer: Scott Schufford | Aces N 8s
run_date: 2026-06-05
status: COMPLETE
---

# Harrison County WV — Parcel 11-409-19 — Title Case Study

**Prepared by:** Scott Schufford | Aces N 8s
**Client:** Texhoma Land Partners — Marcus Strunk RPL
**Run date:** 2026-06-05

---

## Parcel Details

| Field | Value |
|---|---|
| Parcel ID | 11-409-19 |
| District | Elk-Outside |
| County | Harrison |
| State | WV |
| Acres (deed) | 121.072 |
| Acres (config) | 118.00 |
| Parcel Numbers | 17-11-0409-0019-0000 through -0003 |
| Description | Gnatty Creek watershed |

---

## Full Chain of Title

| # | Year | Book/Page | Type | Grantor | Grantee | Acres | Notes |
|---|---|---|---|---|---|---|---|
| 1 | 1874 | DB 57/238 | DEED | Davisson, Edgar M. | Monroe, Benjamin T. | 51 | Gnatty Creek |
| 2 | 1879 | DB 61/434 | DEED | Shuttleworth, S.A. | Monroe, B.T. | — | Romines Mills |
| 3 | 1884 | DB 68/329 | DEED | Bumgardner, Adam | Monroe, B.T. | 60 | |
| 4 | 1888 | DB 75/97  | DEED | Bumgardner, Adam | Monroe, B.T. | 10 | |
| 5 | 1899 | DB 109/403 | DEED | Thompson M.M. Commissioner | Shuttleworth, M.N. | — | Circuit Court |
| 6 | 1903 | DB 136/259 | DEED | Shuttleworth, M.N. & Lillie | Stewart, William A. | 121.5 | **⚠ RESERVED 1/2 MINERALS** |
| 7 | 1919 | Fid Bk 10/247 | ESTATE | Shuttleworth Estate | 6 Heirs | — | Split among heirs |
| 8 | 2010 | BK 1441/1269 | MINERAL DEED | Burns, A. Dean (Exec. Kramer Estate) | Master Mineral Holdings Inc. | 121.072 | **VESTING — $11,137.50** |

---

## Key Findings

### Split Estate — DB 136/259 (1903)
- Shuttleworth conveyed surface to Stewart but **RESERVED 1/2 mineral interest**
- Creates split estate as of 1903 — surface and mineral estates legally separate
- Antero WV mineral reservation analysis required
- *Toothman v. Courtney (1907 WV)*: minerals reserved in place, not merely royalty

### Vesting Instrument — BK 1441/1269 (2010)
- **Master Mineral Holdings Inc. (Texas corp)** holds undivided **1/6 O&G + CBM**
- Grantor: A. Dean Burns, Executor Estate of **Helen S. Kramer**
- Helen S. Kramer = Helen Shuttleworth (1 of 6 heirs from Fid Bk 10/247)
- Consideration: $11,137.50

### Outstanding Research
- 5/6 remaining Shuttleworth heir shares (Lillie A., Lorene, Mary, Samuel, Betty Jane) — **NOT YET DOCUMENTED**
- Full language of DB 136/259 reservation needed — does "minerals" include CBM?
- Monroe → Shuttleworth conveyance path not yet documented

---

## Lessons Learned

1. **IDX URL**: `lookup.harrisoncountywv.com` — search by Individual name, NOT parcel number
2. **Property viewer**: `mapwv.gov/parcel` → Parcel Attributes → Harrison County → get owner name first
3. **VPN required**: WVGES site `wvgs.wvnet.edu` only resolves via Texhoma VPN DNS
4. **SMB auto-mounts**: `/Volumes/DATA/` is available as soon as TLC VPN connects
5. **Zero wells is valid**: WS (White Space) tracts may be undrilled — not an error
6. **Split estate flag**: Always check every deed for mineral reservation language before 1970

---

## Search Workflow That Worked

```
1. Connect TLC VPN (System Preferences → Network → Texhoma-VPN)
2. /Volumes/DATA/ auto-mounts
3. mapwv.gov/parcel → Parcel Attributes → Harrison County → find owner name
4. lookup.harrisoncountywv.com → Individual → "Shuttleworth" or "Burns"
5. Filter to DEED type → pull all instruments by date
6. Build chain 1874→2010 — flag DB 136/259 reservation
7. Run WELL search: tagis.dep.wv.gov/oog/ (county+district, not parcel)
8. Populate OR Excel (8 sheets)
9. Upload to Elk Turn-in folder (mntstrunk@gmail.com Dropbox)
10. Email Marcus at mntstrunk@gmail.com
```

---

## Output Files

- `WS_11-409-19_OR_2026-06-04.xlsx` — Opinion of Record
- `WS_11-409-19_OR_2026-06-04/` — Package folder
- `DEED_NOTES_11-409-19.txt` — Run notes

---

## Related

- [[WV_Title_Examination_Playbook]]
- [[Harrison_County_WV_IDX_Guide]]
- [[Split_Estate_WV_Analysis]]
"""


def _obsidian_store() -> dict:
    status = {"layer": "obsidian", "ok": False, "paths": [], "error": ""}
    try:
        # Write to both Obsidian vault and repo Brain dir
        targets = [
            _OBS_VAULT / "amara" / "WV_Title" / "Harrison_County_11-409-19.md",
            _BRAIN_DIR / "WV_Title" / "Harrison_County_11-409-19.md",
        ]
        for target in targets:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(_OBSIDIAN_MD)
            status["paths"].append(str(target))
            log.info("Obsidian: wrote %s", target)
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

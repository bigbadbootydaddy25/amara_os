# AI_BRAIN Neuron Network Status

**Run:** 2026-05-10 03:53 UTC
**Root:** /home/user/amara_os
**Report:** `agents/neuron-network/reports/20260510T035304Z/NEURON_NETWORK_STATUS.md`

---

## Summary

| Status | Count |
|---|---|
| ✅ OK | 1 |
| ❌ Failed | 0 |
| ❌ Missing | 9 |
| 🔑 No Credentials | 0 |
| 📦 Not Installed | 5 |
| **Total checks** | **15** |

## Backends

| Component | Installed | Connected | Status | Details |
|---|---|---|---|---|
| Hermes | ❌ | — | ❌ MISSING | `/bin/sh: 1: hermes: not found` |
| Neo4j Docker | ❌ | — | ❌ MISSING | `failed to connect to the docker API at unix:///var/run/docker.sock; check if the path is correct and if the daemon is ru` |

## Vaults

| Component | Installed | Connected | Status | Details |
|---|---|---|---|---|
| Obsidian Vault | ❌ | — | ❌ MISSING | `—` |

## Python Libraries

| Component | Installed | Connected | Status | Details |
|---|---|---|---|---|
| Mem0 | ❌ | — | 📦 NOT INSTALLED | `Traceback (most recent call last):   File "<string>", line 1, in <module> ModuleNotFoundError: No module named 'mem0'` |
| LangChain | ❌ | — | 📦 NOT INSTALLED | `Traceback (most recent call last):   File "<string>", line 1, in <module> ModuleNotFoundError: No module named 'langchai` |
| Langfuse | ❌ | — | 📦 NOT INSTALLED | `Traceback (most recent call last):   File "<string>", line 1, in <module> ModuleNotFoundError: No module named 'langfuse` |
| Supabase | ❌ | — | 📦 NOT INSTALLED | `Traceback (most recent call last):   File "<string>", line 1, in <module> ModuleNotFoundError: No module named 'supabase` |
| Neo4j Python Driver | ❌ | — | 📦 NOT INSTALLED | `Traceback (most recent call last):   File "<string>", line 1, in <module> ModuleNotFoundError: No module named 'neo4j'` |

## AI Agents

| Component | Installed | Connected | Status | Details |
|---|---|---|---|---|
| Buyer Activity OSINT | ❌ | — | ❌ MISSING | `—` |
| Entity Resolution | ❌ | — | ❌ MISSING | `—` |
| Deal Scoring Engine | ✅ | ✅ | ✅ OK | `—` |
| Portfolio Distress Analysis | ❌ | — | ❌ MISSING | `—` |
| Ownership Graph | ❌ | — | ❌ MISSING | `—` |
| Integration Auditor | ❌ | — | ❌ MISSING | `—` |

## Integrations

| Component | Installed | Connected | Status | Details |
|---|---|---|---|---|
| MiroFish | ❌ | — | ❌ MISSING | `—` |

---

## Failure Detail

### Hermes — MISSING
- **Command:** `hermes --version`
- **Error:** `/bin/sh: 1: hermes: not found`
- **Duration:** 2ms

### Neo4j Docker — MISSING
- **Command:** `docker ps --filter name=neo4j --format '{{.Names}}	{{.Status}}'`
- **Error:** `failed to connect to the docker API at unix:///var/run/docker.sock; check if the path is correct and if the daemon is running: dial unix /var/run/docker.sock: connect: no such file or directory`
- **Duration:** 153ms

### Obsidian Vault — MISSING
- **Command:** `test -d /home/user/amara_os/obsidian-vault`
- **Duration:** 1ms

### Mem0 — NOT INSTALLED
- **Command:** `python3 -c "import mem0; print('mem0 ok')"`
- **Error:** `Traceback (most recent call last):
  File "<string>", line 1, in <module>
ModuleNotFoundError: No module named 'mem0'`
- **Duration:** 18ms

### LangChain — NOT INSTALLED
- **Command:** `python3 -c "import langchain; print('langchain ok')"`
- **Error:** `Traceback (most recent call last):
  File "<string>", line 1, in <module>
ModuleNotFoundError: No module named 'langchain'`
- **Duration:** 13ms

### Langfuse — NOT INSTALLED
- **Command:** `python3 -c "import langfuse; print('langfuse ok')"`
- **Error:** `Traceback (most recent call last):
  File "<string>", line 1, in <module>
ModuleNotFoundError: No module named 'langfuse'`
- **Duration:** 12ms

### Supabase — NOT INSTALLED
- **Command:** `python3 -c "import supabase; print('supabase ok')"`
- **Error:** `Traceback (most recent call last):
  File "<string>", line 1, in <module>
ModuleNotFoundError: No module named 'supabase'`
- **Duration:** 11ms

### Neo4j Python Driver — NOT INSTALLED
- **Command:** `python3 -c "import neo4j; print('neo4j driver ok')"`
- **Error:** `Traceback (most recent call last):
  File "<string>", line 1, in <module>
ModuleNotFoundError: No module named 'neo4j'`
- **Duration:** 13ms

### Buyer Activity OSINT — MISSING
- **Command:** `test -f agents/buyer-activity-osint/run.py`
- **Duration:** 1ms

### Entity Resolution — MISSING
- **Command:** `test -f agents/entity-resolution/run.py`
- **Duration:** 1ms

### Portfolio Distress Analysis — MISSING
- **Command:** `test -f agents/portfolio-distress-analysis/run.py`
- **Duration:** 1ms

### Ownership Graph — MISSING
- **Command:** `test -f agents/ownership-graph/run.py`
- **Duration:** 1ms

### Integration Auditor — MISSING
- **Command:** `test -f agents/integration-auditor/run.py`
- **Duration:** 1ms

### MiroFish — MISSING
- **Command:** `test -d integrations/MiroFish`
- **Duration:** 1ms

---

## Evidence Paths

| Path | Purpose |
|---|---|
| `data/portfolio-distress/DISTRESSED_PORTFOLIOS.json` | Distressed portfolio owners |
| `data/portfolio-distress/OVERLEVERAGED_BUYERS.json` | Overleveraged buyers |
| `data/portfolio-distress/STALLED_BUILDERS.json` | Stalled builders |
| `data/deal-scoring/HOT_DEALS.json` | Hot deal matches |
| `data/deal-scoring/BUILDER_MATCHES.json` | Builder match records |
| `data/deal-scoring/CASH_BUYER_MATCHES.json` | Cash buyer match records |
| `agents/deal-scoring-engine/reports/` | Deal scoring run history |
| `agents/neuron-network/reports/20260510T035304Z/` | This run's artifacts |
| `reports/NEURON_NETWORK_STATUS.md` | Latest run summary (top-level) |

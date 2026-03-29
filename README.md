# AMARA OS — Buyer-First Real Estate Intelligence System

> **Core Rule: No buyer = no deal.**

AMARA OS is a backend intelligence system for real estate acquisition.
It identifies repeat cash buyers, matches buy boxes to deals, enforces
profit minimums, and improves itself through observed outcomes.

---

## Core Rules

| Rule | Value |
|------|-------|
| SFR Min Assignment Fee | $10,000 |
| SFR Target Assignment Fee | $15,000+ |
| Land Min Spread | $100,000 |
| Land Target Spread | $500,000 – 8 figures |
| MAO Formula | `Buyer Price − Repairs − Assignment Fee` |
| 70% ARV Rule | NOT used |

---

## Quick Start

```bash
# Calculate MAO for an SFR deal
python amara.py mao sfr --buyer-price 200000 --repairs 30000

# Calculate MAO and check against seller asking price
python amara.py mao sfr --buyer-price 200000 --repairs 30000 --seller-asking 155000

# Calculate land spread
python amara.py mao land --buyer-price 1000000 --acquisition 400000

# Full deal analysis
python amara.py analyze sfr --deal-id DEAL-0001 --arv 250000 --buyer-price 200000 --repairs 30000 --seller-asking 160000

# Quick go/no-go screen
python amara.py screen sfr --buyer-price 200000 --repairs 30000 --seller-asking 155000

# Add a new buyer
python amara.py buyer new

# List all buyers
python amara.py buyer list

# Search buyers for a market
python amara.py vault search buyers "Dallas"

# View hot ZIP corridors
python amara.py corridors hot

# Print system workflow
python amara.py workflow
```

---

## Vault Structure

```
buyers/           — Buyer profiles and buy boxes
deals/            — SFR deal files
land/             — Land / dead paper deal files
markets/          — Market snapshots
zip-corridors/    — ZIP corridor activity tracking
playbooks/        — SFR and Land acquisition playbooks
observations/     — Market and deal observations (system memory)
deal-results/     — Closed deal records + post-mortems
system/           — Core logic modules
```

---

## System Workflow

1. Find buyers
2. Build buy boxes
3. Identify hot ZIP corridors
4. Find distressed properties
5. Analyze deals
6. Match buyers
7. Send offers
8. Record outcomes
9. Update knowledge

---

## Learning Protocol

After every deal closes:

1. Record deal result → `deal-results/`
2. Identify pricing gaps
3. Update buyer buy box → `buyers/`
4. Update market observations → `observations/`
5. Adjust future MAO logic

**Learned data always overrides assumptions.**

---

## Core Modules

| File | Purpose |
|------|---------|
| `system/config.py` | Rules, minimums, constants |
| `system/mao_calculator.py` | MAO formula engine |
| `system/deal_analyzer.py` | Deal viability scoring |
| `system/buyer_matcher.py` | Buy box matching engine |
| `system/vault.py` | Vault read/write I/O |
| `system/learning_protocol.py` | Post-deal learning |
| `system/zip_corridor.py` | ZIP corridor tracking |

---

## Playbooks

- `playbooks/SFR_PLAYBOOK.md` — Full SFR wholesale workflow
- `playbooks/LAND_PLAYBOOK.md` — Land / dead paper workflow

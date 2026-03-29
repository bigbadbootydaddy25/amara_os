# AMARA OS — Instructions for Claude

## Read This First

This is a buyer-first real estate intelligence system.
The markdown vault is your memory. Always read it before acting.

---

## Core Rules (Never Break)

1. **No buyer = no deal.** Confirm a matched buyer exists before analyzing or pursuing any property.
2. **SFR minimum assignment fee: $10,000.** Target: $15,000+.
3. **Land minimum spread: $100,000.** Target: $500,000+.
4. **MAO formula:** `MAO = Buyer Price − Repairs − Assignment Fee`
5. **Do NOT use the 70% ARV rule.**
6. **Do NOT build UI.**
7. **Do NOT build a voice system.**
8. **Focus only on the intelligence layer.**

---

## Vault = System Memory

Every buyer, deal, observation, and outcome lives in markdown files.
Always read relevant vault files before making decisions.
Always write back to the vault after decisions are made.

```
buyers/           — Who buys. What they pay. Where they buy.
deals/            — Active and closed SFR deals.
land/             — Land and dead paper deals.
markets/          — City and metro snapshots.
zip-corridors/    — ZIP-level activity and buyer demand.
playbooks/        — Step-by-step workflows.
observations/     — Market intelligence. What you've learned.
deal-results/     — Closed deal records and post-mortems.
system/           — Core logic modules (Python).
```

---

## How to Create a Buyer

Use `buyers/TEMPLATE.md`. File name: `BUY-XXXX_Name.md`

Required fields:
- Name, Entity
- ZIP Codes they buy in
- Buy Box: price range, property type, condition, strategy
- Deal activity (12mo / 24mo)
- Notes on behavior and preferences

---

## How to Create a Deal

Use `deals/TEMPLATE.md`. File name: `DEAL-XXXX_Address.md`

Required fields:
- Address, ZIP, Price (seller asking)
- Repairs estimate
- Buyer Match (link to buyer file)
- MAO calculation
- Assignment fee target
- Status

MAO must be calculated before the deal file is created.
Buyer must be matched before status moves past `analyzing`.

---

## How to Create an Observation

Use `observations/TEMPLATE.md`. File name: `OBS-XXXX_Date_Topic.md`

Required fields:
- Market (city / ZIP / corridor)
- Insight (what was observed)
- Impact (how it changes decisions)
- Action (what gets updated in the vault)

Observations must trigger updates. If the Action field is empty, the observation is incomplete.

---

## MAO Quick Reference

```
Buyer Price (what investor pays):   $
Repairs (conservative estimate):  - $
Assignment Fee (target $15,000):  - $15,000
─────────────────────────────────────────
MAO:                                $
```

Never offer above MAO. Never go under contract without a confirmed buyer.

---

## Learning Protocol (Run After Every Closed Deal)

1. Record result in `deal-results/`
2. Calculate pricing gap (projected vs actual fee)
3. Update buyer's deal history and buy box if needed
4. Write a market observation in `observations/`
5. Note any MAO calibration needed for that corridor

---

## System Skills

### PropStream Operator
Playbook: `playbooks/PROPSTREAM_PLAYBOOK.md`
Module: `system/propstream_operator.py`

How to invoke:
- Use when identifying cash buyers by ZIP or pulling distressed property lists
- Always verify buyer-first before creating deal stubs from PropStream exports
- Log every PropStream session to `observations/` before ending the session
- Do not create buyer files from single-transaction records — 2+ cash purchases required
- Do not create deal files without a confirmed buyer match in that ZIP

### Comp Intelligence + Fast Underwriting
Playbooks:
- `playbooks/comps/sfr_comp_reading.md` — investor comp read, buyer price determination
- `playbooks/comps/land_comp_logic.md` — 4-signal land demand framework
- `playbooks/underwriting/sfr_fast_math.md` — MAO decision tree, 60-second rule
- `playbooks/underwriting/land_ldp.md` — 7-step LDP formula, spread tiers
Module: `system/comp_intelligence.py`

How to invoke:
- Use for any deal evaluation — SFR or land
- All evaluations must complete in under 60 seconds logic time
- SFR flow: read comps → set buyer price → run fast math → go / negotiate / no-go
- Land flow: score 4 signals → run LDP → apply signal-adjusted spread threshold → go / no-go
- Speed > perfection. Do not overanalyze. Do not add steps that don't change the decision.
- **Enforced minimums — never override:**
  - SFR assignment fee: $10,000 hard floor
  - Land spread: $100,000 hard floor

### Video-to-Playbook Learning
Playbook: `playbooks/VIDEO_TO_PLAYBOOK.md`
Module: `system/video_to_playbook.py`

How to invoke:
- Use when a training video transcript is provided
- Do NOT act on video titles, descriptions, or summaries alone — transcript required
- Run `system/video_to_playbook.py` → `process_transcript()` on the raw text
- Output goes to `playbooks/` and an observation is logged automatically
- Vault rules in CLAUDE.md always override extracted video content
- Extracted playbooks are immediately active as operating procedures

---

## What Claude Should Never Do

- Pursue a deal without a matched buyer
- Use 70% ARV as a proxy for MAO
- Accept an assignment fee below $10,000 on SFR
- Accept a land spread below $100,000
- Build UI or voice features
- Leave observation Action fields blank
- Ignore vault data in favor of assumptions
- Act on a video transcript without running it through the Video-to-Playbook skill
- Create buyer vault files from PropStream records with fewer than 2 transactions

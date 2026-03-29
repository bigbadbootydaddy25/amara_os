# Playbook: Video-to-Playbook Learning

## Purpose
Convert training video transcripts into reusable markdown playbooks stored in the vault.
Claude does not assume knowledge from video alone. All learning flows through transcripts
and extracted structured workflows. Extracted playbooks become operating procedures.

---

## Core Rules

- Claude must never act on a video title or description alone. Only transcripts count.
- Every processed transcript produces exactly one output: a markdown playbook file in `playbooks/`.
- Extracted playbooks are treated as operating procedures — they govern future decisions in that domain.
- If a transcript contains conflicting instructions vs. existing vault rules (e.g., use 70% ARV), vault rules win. Note the conflict in the playbook file.
- Raw transcripts are not stored in the vault. Only the extracted, structured playbook is kept.

---

## Step-by-Step Workflow

### Step 1 — Receive Transcript
Accepted input formats:
- Plain text paste (copied from YouTube auto-captions, Otter.ai, Rev, Descript, etc.)
- `.txt` file containing timestamped or clean transcript
- Paragraph dump from a summary tool

**Not accepted:**
- Video URL alone (no transcript = no processing)
- Summary written by someone else without the source transcript
- Audio file (must be converted to text first)

### Step 2 — Parse the Transcript

Run `system/video_to_playbook.py` — `parse_transcript()` function.

The parser looks for:
- **Process signals**: "first", "next", "then", "step", "before you", "after you", "always", "never", "make sure"
- **Rule signals**: "you should always", "never do", "the key is", "the rule is", "most important", "critical"
- **Data signals**: dollar amounts, percentages, ZIP codes, property types, timelines
- **Vocabulary signals**: domain-specific terms (ARV, MAO, wholesaling, subject-to, novation, etc.)

### Step 3 — Classify the Content

Determine the playbook category:

| Category | Keywords Found | Output File |
|----------|---------------|-------------|
| Deal Analysis | MAO, ARV, repairs, offer, spread | `playbooks/[TOPIC]_PLAYBOOK.md` |
| Buyer Acquisition | cash buyer, buy box, investor | `playbooks/[TOPIC]_PLAYBOOK.md` |
| Seller Outreach | motivated seller, cold call, script | `playbooks/[TOPIC]_PLAYBOOK.md` |
| Market Research | comps, Zillow, PropStream, MLS | `playbooks/[TOPIC]_PLAYBOOK.md` |
| Contract / Legal | assignment, double close, title | `playbooks/[TOPIC]_PLAYBOOK.md` |
| Negotiation | negotiating, counter, price reduction | `playbooks/[TOPIC]_PLAYBOOK.md` |
| General / Other | default | `playbooks/[TOPIC]_PLAYBOOK.md` |

### Step 4 — Extract Structured Content

Extract in this order:

1. **Core concept** — what is this video teaching?
2. **Step-by-step process** — numbered workflow if present
3. **Rules and principles** — anything framed as "always", "never", "the key", "most important"
4. **Data points** — numbers, percentages, price ranges, timelines
5. **Warnings and red flags** — what not to do
6. **Vocabulary** — domain terms defined in the video

### Step 5 — Check Against Vault Rules

Before writing the playbook, cross-check extracted content against CLAUDE.md:

| Conflict Check | Vault Rule |
|---------------|-----------|
| Does the video use 70% ARV? | CLAUDE.md: forbidden. Note in playbook. |
| Does the video suggest a fee below $10k? | CLAUDE.md: minimum $10k. Note in playbook. |
| Does the video skip buyer confirmation? | CLAUDE.md: buyer-first is non-negotiable. |

If conflict found: include a `## Vault Conflicts` section in the playbook with the discrepancy noted and the vault rule that takes precedence.

### Step 6 — Write the Playbook File

File naming: `playbooks/[TOPIC]_PLAYBOOK.md`

Examples:
- `playbooks/SUBJECT_TO_PLAYBOOK.md`
- `playbooks/COLD_CALLING_SELLERS_PLAYBOOK.md`
- `playbooks/NOVATION_AGREEMENT_PLAYBOOK.md`
- `playbooks/COMPING_PROPERTIES_PLAYBOOK.md`

Required sections in output playbook:

```markdown
# Playbook: [Topic]

## Source
- Video title: [title if known]
- Transcript date processed: [date]
- Confidence level: high / medium / low

## Core Concept
[1–2 sentence summary of what this playbook teaches]

## Step-by-Step Process
[Numbered workflow extracted from transcript]

## Rules and Principles
[Bulleted list of stated rules and best practices]

## Data Points and Benchmarks
[Numbers, percentages, price ranges extracted]

## Red Flags / What Not To Do
[Warnings extracted from transcript]

## Vocabulary
[Domain terms defined in the video]

## Vault Conflicts
[Any instructions that conflict with CLAUDE.md — vault rule wins]

## Raw Notes
[Any useful detail that didn't fit above]
```

### Step 7 — Log the Extraction as an Observation

After writing the playbook, create an observation in `observations/`:

```
Market: System (meta-learning)
Insight: Processed transcript from [title]. New playbook: [filename].
Impact: [Topic] workflow now standardized in vault.
Action: [filename] is now an active operating procedure for [domain].
```

---

## Quality Standards

A playbook is **complete** if:
- [ ] It has a clear Step-by-Step Process section
- [ ] Rules and principles are explicitly stated (not inferred)
- [ ] Vault conflicts are checked and noted
- [ ] An observation was written linking to it
- [ ] It can be followed by someone with no prior knowledge of the video

A playbook is **incomplete** if:
- The transcript was too short or too vague to extract a process
- The content is purely motivational with no actionable steps
- It duplicates an existing playbook without adding new information

If incomplete: write a brief stub file with a note explaining why it couldn't be fully extracted, and flag for human review.

---

## Transcript Quality Guide

| Transcript Quality | Characteristics | Expected Output |
|-------------------|----------------|-----------------|
| High | Timestamped, clean, full video | Complete playbook |
| Medium | Auto-captions, some errors | Playbook with notes on unclear sections |
| Low | Partial, heavily garbled | Stub with flag for review |
| Unusable | Less than 500 words / no process content | No playbook — log observation with reason |

---

## Vault Integration

Once a playbook is written, it is active immediately.
Claude reads `playbooks/` as part of system memory.
New playbooks override assumed knowledge — always.

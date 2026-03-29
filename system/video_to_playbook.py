"""
AMARA OS — Video-to-Playbook Converter
Processes training video transcripts into vault-ready markdown playbooks.

Claude does not assume knowledge from video alone.
All learning flows through transcripts → extraction → vault.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from system.vault import write_vault_file, next_id


# ─── Confidence Levels ────────────────────────────────────────────────────────

CONFIDENCE_HIGH = "high"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_LOW = "low"


# ─── Signal Patterns ─────────────────────────────────────────────────────────

PROCESS_SIGNALS = [
    r"\bfirst\b", r"\bsecond\b", r"\bthird\b", r"\bnext\b", r"\bthen\b",
    r"\bstep \d", r"\b#\d\b", r"\bafter (that|you|this)\b",
    r"\bbefore you\b", r"\bstart by\b", r"\bfinally\b", r"\blast(ly)?\b",
]

RULE_SIGNALS = [
    r"\balways\b", r"\bnever\b", r"\bthe key (is|to)\b", r"\bthe rule is\b",
    r"\bmost important\b", r"\bcritical(ly)?\b", r"\bmake sure\b",
    r"\byou (must|need to|should)\b", r"\bdo not\b", r"\bdon['']t\b",
]

DATA_SIGNALS = [
    r"\$[\d,]+",                          # dollar amounts
    r"\d+[\.,]?\d*\s*%",                  # percentages
    r"\b\d{5}\b",                         # ZIP codes
    r"\b\d+[\-–]\d+\s*days?\b",           # day ranges
    r"\b\d+[\-–]\d+\s*(k|K|thousand)\b",  # price ranges
]

DOMAIN_VOCABULARY = {
    "arv": "After Repair Value — retail value of a property after renovation",
    "mao": "Maximum Allowable Offer — highest price to offer: Buyer Price - Repairs - Fee",
    "assignment fee": "Profit made by wholesaler when assigning a contract to an end buyer",
    "double close": "Two back-to-back closings: A→B then B→C, wholesaler is B",
    "novation": "Contract replacement strategy — take over property with seller's agreement",
    "subject-to": "Purchasing a property subject to the existing mortgage",
    "pre-foreclosure": "Property where owner has received a Notice of Default but not yet lost it",
    "nod": "Notice of Default — first step in foreclosure process",
    "equity": "Difference between market value and mortgage/lien balance",
    "absentee owner": "Owner whose mailing address differs from the property address",
    "skip trace": "Process of finding contact information for a property owner",
    "daisy chain": "Multiple wholesalers assigning the same contract — avoid",
    "emd": "Earnest Money Deposit",
    "poc": "Proof of Cash / Proof of Funds",
    "comps": "Comparable sales used to estimate ARV",
}

# ─── Vault Conflict Rules ─────────────────────────────────────────────────────

VAULT_CONFLICT_PATTERNS = [
    {
        "pattern": r"70\s*%\s*(of\s+)?arv",
        "vault_rule": "CLAUDE.md: Do NOT use the 70% ARV rule. Use MAO = Buyer Price − Repairs − Fee.",
        "flag": "70% ARV rule detected",
    },
    {
        "pattern": r"\$[5-9],?000\s*(assignment|fee)|assignment fee.{0,30}\$[5-9],?000",
        "vault_rule": "CLAUDE.md: SFR minimum assignment fee is $10,000. Never go below.",
        "flag": "Assignment fee below $10k mentioned",
    },
    {
        "pattern": r"find (the|a) deal first|deal.{0,20}before.{0,20}buyer",
        "vault_rule": "CLAUDE.md: Buyer-first always. No buyer = no deal.",
        "flag": "Deal-first logic detected — buyer-first rule applies",
    },
]


# ─── Data Structures ──────────────────────────────────────────────────────────

@dataclass
class TranscriptAnalysis:
    """Result of parsing a raw transcript."""
    word_count: int
    process_sentences: list[str] = field(default_factory=list)
    rule_sentences: list[str] = field(default_factory=list)
    data_points: list[str] = field(default_factory=list)
    vocabulary_hits: list[str] = field(default_factory=list)
    vault_conflicts: list[dict] = field(default_factory=list)
    confidence: str = CONFIDENCE_LOW

    def has_process(self) -> bool:
        return len(self.process_sentences) >= 3

    def has_rules(self) -> bool:
        return len(self.rule_sentences) >= 1

    def is_usable(self) -> bool:
        return self.word_count >= 500 and (self.has_process() or self.has_rules())


@dataclass
class ExtractedPlaybook:
    """Structured content ready to be written as a markdown playbook."""
    topic: str
    category: str
    video_title: str
    confidence: str
    core_concept: str
    steps: list[str]
    rules: list[str]
    data_points: list[str]
    red_flags: list[str]
    vocabulary: dict[str, str]
    vault_conflicts: list[dict]
    raw_notes: str


# ─── Parser ───────────────────────────────────────────────────────────────────

def parse_transcript(transcript: str) -> TranscriptAnalysis:
    """
    Analyze a raw transcript for extractable content.
    Returns TranscriptAnalysis with classified sentences and conflict flags.
    """
    text = transcript.strip()
    words = text.split()
    word_count = len(words)
    sentences = re.split(r"(?<=[.!?])\s+", text)

    process_sentences = []
    rule_sentences = []
    data_points = []
    vocab_hits = []
    conflicts = []

    for sentence in sentences:
        s_lower = sentence.lower()

        # Process signals
        for pattern in PROCESS_SIGNALS:
            if re.search(pattern, s_lower):
                process_sentences.append(sentence.strip())
                break

        # Rule signals
        for pattern in RULE_SIGNALS:
            if re.search(pattern, s_lower):
                rule_sentences.append(sentence.strip())
                break

        # Data signals
        for pattern in DATA_SIGNALS:
            matches = re.findall(pattern, sentence, re.IGNORECASE)
            data_points.extend(matches)

        # Vault conflicts
        for conflict in VAULT_CONFLICT_PATTERNS:
            if re.search(conflict["pattern"], s_lower, re.IGNORECASE):
                conflicts.append({
                    "sentence": sentence.strip(),
                    "flag": conflict["flag"],
                    "vault_rule": conflict["vault_rule"],
                })

    # Vocabulary hits
    for term in DOMAIN_VOCABULARY:
        if term in text.lower():
            vocab_hits.append(term)

    # Confidence scoring
    if word_count >= 2000 and len(process_sentences) >= 5:
        confidence = CONFIDENCE_HIGH
    elif word_count >= 800 and (len(process_sentences) >= 2 or len(rule_sentences) >= 2):
        confidence = CONFIDENCE_MEDIUM
    else:
        confidence = CONFIDENCE_LOW

    return TranscriptAnalysis(
        word_count=word_count,
        process_sentences=list(dict.fromkeys(process_sentences)),  # dedupe
        rule_sentences=list(dict.fromkeys(rule_sentences)),
        data_points=list(dict.fromkeys(data_points)),
        vocabulary_hits=vocab_hits,
        vault_conflicts=conflicts,
        confidence=confidence,
    )


def classify_category(transcript: str) -> str:
    """Determine the playbook category from transcript content."""
    t = transcript.lower()
    if any(kw in t for kw in ["mao", "max allowable", "repairs", "arv", "after repair"]):
        return "Deal Analysis"
    if any(kw in t for kw in ["cash buyer", "buy box", "investor list", "buyer list"]):
        return "Buyer Acquisition"
    if any(kw in t for kw in ["cold call", "motivated seller", "direct mail", "outreach", "script"]):
        return "Seller Outreach"
    if any(kw in t for kw in ["comps", "comparable", "zillow", "propstream", "mls", "redfin"]):
        return "Market Research"
    if any(kw in t for kw in ["assignment contract", "double close", "title", "novation", "subject-to", "sub2"]):
        return "Contract / Legal"
    if any(kw in t for kw in ["negotiat", "counter offer", "price reduction", "lowball"]):
        return "Negotiation"
    return "General"


def extract_playbook(
    transcript: str,
    video_title: str = "",
    topic_override: str = "",
) -> ExtractedPlaybook | None:
    """
    Full extraction pipeline: parse → classify → extract → check conflicts.
    Returns ExtractedPlaybook or None if transcript is unusable.
    """
    analysis = parse_transcript(transcript)

    if not analysis.is_usable():
        return None

    category = classify_category(transcript)
    topic = topic_override or (video_title.replace(" ", "_").upper() if video_title else category.upper().replace(" ", "_"))

    # Extract steps: find numbered or signaled process sentences
    steps = []
    for i, sentence in enumerate(analysis.process_sentences[:15], 1):
        # Clean up sentence
        clean = re.sub(r"^\d+[\.\)]\s*", "", sentence).strip()
        if clean:
            steps.append(f"{i}. {clean}")

    # Extract rules
    rules = [s for s in analysis.rule_sentences[:10] if len(s) > 20]

    # Red flags: sentences with "never", "don't", "avoid", "mistake", "wrong"
    red_flag_patterns = [r"\bnever\b", r"\bdon['']t\b", r"\bavoid\b", r"\bmistake\b", r"\bwrong\b", r"\bdo not\b"]
    red_flags = []
    sentences = re.split(r"(?<=[.!?])\s+", transcript)
    for s in sentences:
        for p in red_flag_patterns:
            if re.search(p, s.lower()):
                red_flags.append(s.strip())
                break

    # Vocabulary: only terms that appeared in this transcript
    vocab = {
        term: DOMAIN_VOCABULARY[term]
        for term in analysis.vocabulary_hits
        if term in DOMAIN_VOCABULARY
    }

    # Raw notes: data points and any leftover content
    raw_notes = ""
    if analysis.data_points:
        raw_notes += "Data points extracted:\n"
        for dp in sorted(set(analysis.data_points))[:20]:
            raw_notes += f"- {dp}\n"

    # Simple core concept extraction: first 2–3 sentences of transcript
    lead_sentences = re.split(r"(?<=[.!?])\s+", transcript.strip())[:3]
    core_concept = " ".join(lead_sentences)[:400]

    return ExtractedPlaybook(
        topic=topic,
        category=category,
        video_title=video_title or "(title not provided)",
        confidence=analysis.confidence,
        core_concept=core_concept,
        steps=steps,
        rules=rules[:10],
        data_points=list(set(analysis.data_points))[:20],
        red_flags=list(dict.fromkeys(red_flags))[:10],
        vocabulary=vocab,
        vault_conflicts=analysis.vault_conflicts,
        raw_notes=raw_notes,
    )


# ─── Vault Writer ─────────────────────────────────────────────────────────────

def write_playbook_to_vault(playbook: ExtractedPlaybook) -> Path:
    """
    Write an ExtractedPlaybook to the playbooks/ vault folder.
    Returns path of created file.
    """
    today = date.today().isoformat()
    filename = f"{playbook.topic}_PLAYBOOK.md"

    lines = [
        f"# Playbook: {playbook.topic.replace('_', ' ').title()}",
        "",
        "## Source",
        f"- Video title: {playbook.video_title}",
        f"- Category: {playbook.category}",
        f"- Transcript processed: {today}",
        f"- Confidence level: {playbook.confidence}",
        "",
        "## Core Concept",
        "",
        playbook.core_concept or "(not extracted — see raw notes)",
        "",
    ]

    # Steps
    lines += ["## Step-by-Step Process", ""]
    if playbook.steps:
        lines += playbook.steps
    else:
        lines += ["(No clear step-by-step process found in transcript)"]
    lines.append("")

    # Rules
    lines += ["## Rules and Principles", ""]
    if playbook.rules:
        for r in playbook.rules:
            lines.append(f"- {r}")
    else:
        lines += ["(No explicit rules extracted)"]
    lines.append("")

    # Data Points
    lines += ["## Data Points and Benchmarks", ""]
    if playbook.data_points:
        for dp in playbook.data_points:
            lines.append(f"- {dp}")
    else:
        lines += ["(No specific data points extracted)"]
    lines.append("")

    # Red Flags
    lines += ["## Red Flags / What Not To Do", ""]
    if playbook.red_flags:
        for rf in playbook.red_flags:
            lines.append(f"- {rf}")
    else:
        lines += ["(No red flags extracted)"]
    lines.append("")

    # Vocabulary
    lines += ["## Vocabulary", ""]
    if playbook.vocabulary:
        for term, definition in playbook.vocabulary.items():
            lines.append(f"- **{term.upper()}**: {definition}")
    else:
        lines += ["(No domain vocabulary extracted)"]
    lines.append("")

    # Vault Conflicts
    lines += ["## Vault Conflicts", ""]
    if playbook.vault_conflicts:
        for conflict in playbook.vault_conflicts:
            lines += [
                f"**Flag:** {conflict['flag']}",
                f"> Transcript said: \"{conflict['sentence']}\"",
                f"> Vault rule: {conflict['vault_rule']}",
                "",
            ]
    else:
        lines += ["None — no conflicts with CLAUDE.md detected."]
    lines.append("")

    # Raw Notes
    if playbook.raw_notes:
        lines += ["## Raw Notes", "", playbook.raw_notes]

    content = "\n".join(lines)
    path = write_vault_file("playbooks", filename, content)
    return path


def log_extraction_observation(
    playbook: ExtractedPlaybook,
    playbook_filename: str,
) -> Path:
    """
    Write an observation to the vault recording the learning event.
    Required after every successful extraction.
    """
    obs_id = next_id("OBS", "observations")
    today = date.today().isoformat()
    filename = f"{obs_id}_{today}_VideoLearning_{playbook.topic[:30]}.md"

    content = f"# Video Learning — {playbook.topic.replace('_', ' ').title()}\n\n"
    content += f"## Market\n\n- System (meta-learning)\n\n"
    content += f"## Insight\n\n"
    content += f"- Processed transcript: {playbook.video_title}\n"
    content += f"- Category: {playbook.category}\n"
    content += f"- Confidence: {playbook.confidence}\n"
    content += f"- Steps extracted: {len(playbook.steps)}\n"
    content += f"- Rules extracted: {len(playbook.rules)}\n"
    content += f"- Vault conflicts found: {len(playbook.vault_conflicts)}\n\n"
    content += f"## Impact\n\n"
    content += f"- New playbook added: `playbooks/{playbook_filename}`\n"
    content += f"- {playbook.category} workflow now standardized in vault.\n\n"
    content += f"## Action\n\n"
    content += f"- `playbooks/{playbook_filename}` is now an active operating procedure for {playbook.category}.\n"
    if playbook.vault_conflicts:
        content += f"- {len(playbook.vault_conflicts)} vault conflict(s) noted — vault rules take precedence.\n"
    content += "\n---\n\n<!-- AMARA OS Extended Fields -->\n\n"
    content += f"## Identity\n- **ID:** {obs_id}\n- **Date:** {today}\n- **Type:** market\n- **Related Deal:**\n- **Related Buyer:**\n"

    path = write_vault_file("observations", filename, content)
    return path


# ─── Main Entry Point ─────────────────────────────────────────────────────────

def process_transcript(
    transcript: str,
    video_title: str = "",
    topic_override: str = "",
) -> dict:
    """
    Full pipeline: transcript in → playbook file + observation out.

    Returns:
        {
            "success": bool,
            "playbook_path": Path | None,
            "observation_path": Path | None,
            "confidence": str,
            "reason": str,
        }
    """
    playbook = extract_playbook(transcript, video_title, topic_override)

    if playbook is None:
        analysis = parse_transcript(transcript)
        reason = (
            f"Transcript too short ({analysis.word_count} words) or no extractable process found."
            if analysis.word_count < 500
            else "Transcript did not contain enough structured process content to build a playbook."
        )
        return {
            "success": False,
            "playbook_path": None,
            "observation_path": None,
            "confidence": CONFIDENCE_LOW,
            "reason": reason,
        }

    playbook_path = write_playbook_to_vault(playbook)
    obs_path = log_extraction_observation(playbook, playbook_path.name)

    return {
        "success": True,
        "playbook_path": playbook_path,
        "observation_path": obs_path,
        "confidence": playbook.confidence,
        "reason": f"Playbook written: {playbook_path.name}. Observation logged: {obs_path.name}.",
    }

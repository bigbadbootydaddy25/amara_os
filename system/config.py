"""
AMARA OS — Core Configuration
System rules, minimums, and constants. Do not override without justification.
"""

# ─── Deal Type Minimums ───────────────────────────────────────────────────────

SFR_MIN_ASSIGNMENT_FEE = 10_000       # Hard floor — never go below
SFR_TARGET_ASSIGNMENT_FEE = 15_000   # Preferred target

LAND_MIN_SPREAD = 100_000             # Hard floor for land / dead paper
LAND_TARGET_SPREAD = 500_000          # Preferred — aim for 6–8 figure spreads

# ─── MAO Formula ─────────────────────────────────────────────────────────────
# MAO = Buyer Price - Repairs - Assignment Fee
# DO NOT use 70% ARV rule.

# ─── Deal Types ───────────────────────────────────────────────────────────────

DEAL_TYPES = ["SFR", "MFR", "Land", "Commercial", "Mobile"]

ASSET_TYPE_SFR = "SFR"
ASSET_TYPE_MFR = "MFR"
ASSET_TYPE_LAND = "Land"
ASSET_TYPE_COMMERCIAL = "Commercial"
ASSET_TYPE_MOBILE = "Mobile"

# ─── Vault Paths ──────────────────────────────────────────────────────────────

VAULT_BUYERS = "buyers"
VAULT_DEALS = "deals"
VAULT_LAND = "land"
VAULT_MARKETS = "markets"
VAULT_ZIP_CORRIDORS = "zip-corridors"
VAULT_PLAYBOOKS = "playbooks"
VAULT_OBSERVATIONS = "observations"
VAULT_DEAL_RESULTS = "deal-results"
VAULT_SYSTEM = "system"

# ─── System Workflow Order ────────────────────────────────────────────────────

WORKFLOW_STEPS = [
    "1. Find buyers",
    "2. Build buy boxes",
    "3. Identify hot ZIP corridors",
    "4. Find distressed properties",
    "5. Analyze deals",
    "6. Match buyers",
    "7. Send offers",
    "8. Record outcomes",
    "9. Update knowledge",
]

# ─── Learning Protocol ────────────────────────────────────────────────────────

LEARNING_STEPS = [
    "1. Record deal result",
    "2. Identify pricing gaps",
    "3. Update buyer buy box",
    "4. Update market observations",
    "5. Adjust future MAO logic",
]

# ─── Core Rule: Buyer-First ───────────────────────────────────────────────────
# No buyer = no deal. Always verify buyer before pursuing a property.

BUYER_FIRST = True

# ─── Deal Status Values ───────────────────────────────────────────────────────

DEAL_STATUS_PROSPECTING = "prospecting"
DEAL_STATUS_ANALYZING = "analyzing"
DEAL_STATUS_OFFER_SENT = "offer_sent"
DEAL_STATUS_UNDER_CONTRACT = "under_contract"
DEAL_STATUS_CLOSED = "closed"
DEAL_STATUS_DEAD = "dead"

DEAL_STATUSES = [
    DEAL_STATUS_PROSPECTING,
    DEAL_STATUS_ANALYZING,
    DEAL_STATUS_OFFER_SENT,
    DEAL_STATUS_UNDER_CONTRACT,
    DEAL_STATUS_CLOSED,
    DEAL_STATUS_DEAD,
]

# ─── Buyer Status Values ──────────────────────────────────────────────────────

BUYER_STATUS_ACTIVE = "active"
BUYER_STATUS_PAUSED = "paused"
BUYER_STATUS_INACTIVE = "inactive"

# ─── Activity Levels ──────────────────────────────────────────────────────────

ACTIVITY_HOT = "hot"
ACTIVITY_WARM = "warm"
ACTIVITY_COLD = "cold"
ACTIVITY_UNKNOWN = "unknown"

# All path constants and configuration
from pathlib import Path

QUICKCASH_ROOT = Path("/home/user/amara_os/amara-aegis-quickcash")
QUICKCASH_AEGIS_OUTPUTS = QUICKCASH_ROOT / "data" / "aegis_neurons"
AMARA_BRAIN_AEGIS_ROOT = Path("/home/user/amara_os/AMARA_BRAIN/AEGIS_Neuron_Network")
MAIN_PROJECT_ROOT = Path("/home/user/amara_os")
PORT = 8088

# Expected QuickCash output files
EXPECTED_QUICKCASH_FILES = {
    "strike_board": QUICKCASH_AEGIS_OUTPUTS / "houston_tax_sale_strike_board.csv",
    "strike_brief": QUICKCASH_AEGIS_OUTPUTS / "houston_tax_sale_strike_brief.md",
    "buyer_demand_needed": QUICKCASH_AEGIS_OUTPUTS / "buyer_demand_needed.md",
    "buyer_verification_tasks": QUICKCASH_AEGIS_OUTPUTS / "buyer_verification_tasks.md",
    "openclaw_buyer_research": QUICKCASH_AEGIS_OUTPUTS / "openclaw_buyer_research_tasks.md",
    "payoff_verification": QUICKCASH_AEGIS_OUTPUTS / "payoff_verification_needed.md",
    "title_risk": QUICKCASH_AEGIS_OUTPUTS / "title_risk_checklist.md",
}

EXPECTED_BUYER_TARGET_FILES = {
    "downtown_commercial": QUICKCASH_AEGIS_OUTPUTS / "buyer_targets" / "downtown_commercial_buyers.csv",
    "tidwell_auto": QUICKCASH_AEGIS_OUTPUTS / "buyer_targets" / "tidwell_commercial_auto_buyers.csv",
    "infill_77018": QUICKCASH_AEGIS_OUTPUTS / "buyer_targets" / "77018_infill_builders.csv",
    "buyer_summary": QUICKCASH_AEGIS_OUTPUTS / "buyer_targets" / "buyer_target_summary.md",
}

# AMARA_BRAIN output paths
EVENTS_DIR = AMARA_BRAIN_AEGIS_ROOT / "events"
REPORTS_DIR = AMARA_BRAIN_AEGIS_ROOT / "reports"
SOURCE_LOGS_DIR = AMARA_BRAIN_AEGIS_ROOT / "source_logs"
TAX_SALE_STRIKES_DIR = AMARA_BRAIN_AEGIS_ROOT / "tax_sale_strikes"
BUYER_DEMAND_DIR = AMARA_BRAIN_AEGIS_ROOT / "buyer_demand"
OPENCLAW_TASKS_DIR = AMARA_BRAIN_AEGIS_ROOT / "openclaw_tasks"
DAILY_MONEY_BRIEFS_DIR = AMARA_BRAIN_AEGIS_ROOT / "daily_money_briefs"
FAILED_NEURONS_DIR = AMARA_BRAIN_AEGIS_ROOT / "failed_neurons"
STATUS_DIR = AMARA_BRAIN_AEGIS_ROOT / "status"
EVENT_LOG_PATH = EVENTS_DIR / "event_log.jsonl"

# Known strike board properties (from completed QuickCash run)
KNOWN_STRIKE_BOARD = [
    {"rank": 1, "name": "BENDANMAR LIMITED - 1307 Prairie St", "address": "1307 Prairie St, Houston TX", "entity": "BENDANMAR LIMITED", "status": "SOURCE_NEEDED"},
    {"rank": 2, "name": "BENDANMAR LIMITED - 415 Caroline St", "address": "415 Caroline St, Houston TX", "entity": "BENDANMAR LIMITED", "status": "SOURCE_NEEDED"},
    {"rank": 3, "name": "800 Tidwell Rd", "address": "800 Tidwell Rd, Houston TX", "entity": "USER_PROVIDED_UNVERIFIED", "status": "SOURCE_NEEDED"},
    {"rank": 4, "name": "813 W 30TH ST", "address": "813 W 30th St, Houston TX", "entity": "USER_PROVIDED_UNVERIFIED", "status": "SOURCE_NEEDED"},
    {"rank": 5, "name": "1516 W 34TH ST", "address": "1516 W 34th St, Houston TX", "entity": "USER_PROVIDED_UNVERIFIED", "status": "SOURCE_NEEDED"},
]

CONTAMINATION_STRINGS = [
    "TEST_DATA_NOT_REAL", "FAKE", "SAMPLE", "DEMO", "456 OAK", "789 ELM"
]

from functools import lru_cache
from pathlib import Path

_PERSONA_PATH = Path(__file__).resolve().parent / "amara_system.md"


@lru_cache
def load_persona() -> str:
    return _PERSONA_PATH.read_text(encoding="utf-8")

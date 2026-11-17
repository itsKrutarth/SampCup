"""Precomputed schedules, one per team count (made by tools/export_schedules.py)."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent / "schedule_data"
MIN_TEAMS, MAX_TEAMS = 32, 42


@lru_cache
def load_template(n_teams: int) -> dict[str, Any]:
    if not MIN_TEAMS <= n_teams <= MAX_TEAMS:
        raise ValueError(f"schedules exist for {MIN_TEAMS}-{MAX_TEAMS} teams, not {n_teams}")
    return json.loads((DATA_DIR / f"teams_{n_teams}.json").read_text())

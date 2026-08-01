"""
imaginAI — Stage Protection: Rate Limiting & Safety Net Service
Manages per-visitor daily video limits (4 videos / 24h) and site-wide global daily limits (20 videos / day).
Uses JSON storage in backend/data/ for simple, file-based persistence without database dependencies.
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

VISITOR_LIMIT_FILE = DATA_DIR / "visitor_limits.json"
GLOBAL_LIMIT_FILE = DATA_DIR / "global_limits.json"

# Limits Configuration
MAX_VISITOR_VIDEOS_PER_DAY = 4
MAX_GLOBAL_VIDEOS_PER_DAY = 20
VISITOR_WINDOW_SECONDS = 86400  # 24 hours


# ── File I/O Helpers ─────────────────────────────────────────────────────────

def _load_json(file_path: Path) -> dict:
    if not file_path.exists():
        return {}
    try:
        return json.loads(file_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_json(file_path: Path, data: dict) -> None:
    try:
        file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[RateLimit Warning] Failed to save {file_path.name}: {e}")


# ── Visitor & Global Check Functions ─────────────────────────────────────────

def check_and_increment_rate_limits(visitor_id: str) -> tuple[bool, str]:
    """
    Check both visitor limit and global daily limit.
    If allowed, increment counters and return (True, "").
    If restricted, return (False, "Arabic error message").
    """
    now_ts = time.time()
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # 1. Check Global Daily Limit
    global_data = _load_json(GLOBAL_LIMIT_FILE)
    if global_data.get("date") != today_str:
        global_data = {"date": today_str, "count": 0}

    current_global_count = int(global_data.get("count", 0))

    if current_global_count >= MAX_GLOBAL_VIDEOS_PER_DAY:
        return (
            False,
            f"وصل النظام التجريبي للحد الأقصى اليومي ({MAX_GLOBAL_VIDEOS_PER_DAY} فيديو لكامل الموقع). يرجى العودة غداً!",
        )

    # 2. Check Per-Visitor Limit (24 Hours sliding window)
    visitor_data = _load_json(VISITOR_LIMIT_FILE)
    visitor_info = visitor_data.get(visitor_id, {"timestamps": []})
    
    # Filter timestamps within the last 24 hours
    recent_timestamps = [ts for ts in visitor_info.get("timestamps", []) if now_ts - ts < VISITOR_WINDOW_SECONDS]

    if len(recent_timestamps) >= MAX_VISITOR_VIDEOS_PER_DAY:
        return (
            False,
            f"وصلت للحد المسموح اليوم ({MAX_VISITOR_VIDEOS_PER_DAY} فيديوهات لكل جهاز خلال 24 ساعة). يرجى العودة غداً!",
        )

    # 3. Record new generation event
    recent_timestamps.append(now_ts)
    visitor_data[visitor_id] = {"timestamps": recent_timestamps, "last_updated": today_str}
    global_data["count"] = current_global_count + 1

    _save_json(VISITOR_LIMIT_FILE, visitor_data)
    _save_json(GLOBAL_LIMIT_FILE, global_data)

    print(f"[RateLimit] Approved job for visitor '{visitor_id[:8]}...'. Global today: {global_data['count']}/{MAX_GLOBAL_VIDEOS_PER_DAY}")
    return (True, "")

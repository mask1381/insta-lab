"""
تنظیمات مرکزی Insta Lab — ماشینِ کانال-اگنوستیک اینستاگرام.

هیچ هویتی (برند/یوزرنیم/لینک) سخت‌کد نیست؛ همه با setter ها از batch می‌آیند.
توکن‌ها و سشن فقط از Environment (GitHub Secrets) خوانده می‌شوند.
"""

import os
import re
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parent
BASE_DIR = PKG_DIR.parent
DATA_DIR = BASE_DIR / "data"

# ─────────────────────────────────────────
# مسیرهای داده — generic
# ─────────────────────────────────────────
SENT_IDS_PATH = DATA_DIR / "sent_ids.json"
STATE_PATH = DATA_DIR / "state.json"
DICTIONARY_PATH = DATA_DIR / "character_dictionary.csv"
TAG_STATS_PATH = DATA_DIR / "tag_stats.csv"

# ─────────────────────────────────────────
# نام این گره (branch) — از batch می‌آید؛ در کد هرگز ثابت نیست
# ─────────────────────────────────────────
_BRANCH = ""

def set_branch(branch: str) -> None:
    """نام شاخه/گره این اجرا — از batch (channel)."""
    global _BRANCH
    _BRANCH = str(branch or "").strip()

def get_branch() -> str:
    return _BRANCH


# ─────────────────────────────────────────
# تلگرام (ارسال) — از env / batch
# ─────────────────────────────────────────
TG_API_ID = os.getenv("TG_API_ID", "").strip()
TG_API_HASH = os.getenv("TG_API_HASH", "").strip()
TG_SESSION_STRING = os.getenv("TG_SESSION_STRING", "").strip()
TG_CHAT_ID = os.getenv("TG_CHAT_ID", "").strip()

# اینستاگرام — رویه‌ی امنیتیِ دانلود (همه اختیاری)
IG_PROXY_URL = os.getenv("IG_PROXY_URL", "").strip()
CURL_CFFI_IMPERSONATE = os.getenv("CURL_CFFI_IMPERSONATE", "chrome124").strip().strip()
IG_COOKIE = os.getenv("IG_COOKIE", "").strip()  # (اختیاری) کوکی‌های لاگین برای نرخ بالاتر

# ─────────────────────────────────────────
# سیم‌کشی یک‌جا از batch — قلبِ کانال-اگنوستیک
# ─────────────────────────────────────────
def env_config(batch: dict | None) -> dict:
    """از batch: branch، تارگت، فوتر/برند. خروجی: کپی کوچکِ مرجع برای ران."""
    batch = batch or {}
    set_branch(batch.get("branch") or batch.get("channel") or "")
    if batch.get("target_chat_id"):
        global TG_CHAT_ID
        TG_CHAT_ID = str(batch["target_chat_id"])

    from insta_lab import caption
    caption.set_footer(str(batch.get("footer_html") or batch.get("footer") or ""))
    caption.set_brand_tag(str(batch.get("brand_tag") or ""))

    return {
        "dry": bool(batch.get("dry")),
        "target_chat_id": str(batch.get("target_chat_id") or TG_CHAT_ID),
    }

# ───── زمان‌بندی (Scheduled Messages) ─────
SCHED_TZ = "Asia/Tehran"
SCHED_LEAD_MIN = 90
SCHED_HORIZON_H = 24
SCHED_QUEUE_SAFE_CAP = 95
SCHED_RUN_CAP = 50
SCHED_MIN_GAP_MIN = 30
SCHED_SAME_SLOT_TOL_MIN = 5
SCHED_SHIFT_STEP_MIN = 5
SCHED_SHIFT_MAX_MIN = 15

# ─────────────────────────────────────────
# رسانه / تلگرام
# ─────────────────────────────────────────
MAX_TG_CAPTION_LEN = 1024   # سقف خود تلگرام برای caption
ALBUM_MAX = 10              # سقف آلبوم تلگرام
PAUSE_BETWEEN = 4           # ثانیه مکث بین آلبوم‌های یک پست
DOWNLOAD_TIMEOUT = 300      # ثانیه، برای دانلود CDN

# ─────────────────────────────────────────
# رفتار «انسانی» + سقف‌ها — با env قابل تغییر
# ─────────────────────────────────────────
def _env_bool(name, default):
    v = os.getenv(name)
    return default if v is None or v.strip() == "" else v.strip().lower() in ("1", "true", "yes", "on")

def _env_int(name, default):
    try:
        return int(os.getenv(name, "").strip())
    except ValueError:
        return default

HUMAN_PACING = _env_bool("HUMAN_PACING", True)


def _env_float_list(name, default):
    """مثل '40-80' → (40, 80)؛ یا عدد تکی → (x, x)."""
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        parts = [float(x) for x in str(raw).replace(",", "-").split("-") if x.strip()]
        if len(parts) == 1:
            return (parts[0], parts[0])
        return (min(parts[:2]), max(parts[:2]))
    except ValueError:
        return default


def random_in_range(rng, rng_obj, lo_hi):
    """یک مقدار تصادفی در بازه (lo, hi) — برای مکثِ انسانی."""
    lo, hi = lo_hi
    if lo == hi:
        return lo
    return rng.uniform(lo, hi)

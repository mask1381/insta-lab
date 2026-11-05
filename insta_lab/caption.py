"""
موتور کپشن Insta Lab — کانال-اگنوستیک.

پایه: «کپشنِ اصلیِ پست» (از batch، دست‌نخورده). بعد (اختیاری، از batch):
- برداشت هشتگ‌ها اگر خواسته شد (بدون هویت)
- برندتگ (set_brand_tag)
- فوتر (set_footer)

اصل: این ماشین هیچ واژه/برندی از خودش ندارد؛ همه از batch می‌آیند یا نیستند.
"""

from __future__ import annotations

import re

from insta_lab import config

# پیش‌فرض‌های چیدمان — همه با setter از batch عوض می‌شوند
_FOOTER = ""
_BRAND_TAG = ""


def set_footer(footer: str) -> None:
    global _FOOTER
    _FOOTER = str(footer or "").strip()


def set_brand_tag(tag: str) -> None:
    global _BRAND_TAG
    _BRAND_TAG = (str(tag or "").strip().lstrip("#"))


def get_brand_tag() -> str:
    return _BRAND_TAG


def extract_hashtags(caption: str) -> list[str]:
    """هشتگ‌های داخل کپشن اصلی (بدون تغییر) — برای حالت «فقط هشتگ»."""
    if not caption:
        return []
    return re.findall(r"#[\w؀-ۿ]+", caption)


def trim_caption(caption: str, limit: int = None) -> str:
    """تا سقف تلگرام کوتاه می‌کند؛ از داده‌ی اصلی بیشتر کوتاه نمی‌شود."""
    limit = limit or config.MAX_TG_CAPTION_LEN
    caption = (caption or "").strip()
    if len(caption) > limit:
        caption = caption[:limit - 1].rstrip() + "…"
    return caption


def build_caption(original: str, only_tags: bool = False) -> str:
    """کپشن نهایی:
    - body دست‌نخورده، ولی تا جا شدن برای برند+فوتر بریده می‌شود (سقف ۱۰۲۴).
    - only_tags=True → فقط هشتگ‌های موجود در آن (بدون متن).
    - برندتگ و فوتر (اگر batch داده باشد) در پایان و هرگز بریده نمی‌شوند.
    """
    limit = config.MAX_TG_CAPTION_LEN
    suffix = _FOOTER
    if _BRAND_TAG:
        suffix = ("#" + _BRAND_TAG) + ("\n\n" + suffix if suffix else "")

    if only_tags:
        body = " ".join(extract_hashtags(original))
    else:
        body = (original or "").strip()

    # سهم برند+فوتر (با جداکننده‌ی \n\n) را از سقف کم می‌کنیم تا هرگز بریده نشوند
    suffix_cost = len(suffix) + (2 if body and suffix else 0)
    body = trim_caption(body, limit=max(0, limit - suffix_cost))

    text = body + ("\n\n" + suffix if body and suffix else suffix)
    return text[:limit] if text else ""

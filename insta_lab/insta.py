"""
منطقِ هر پست اینستاگرام — منبع «اینستا» در این ماشین؛ بدون هیچ هویت کانالی.

ورودی هر پست (از batch):
    {"idx": int, "shortcode": "…", "caption": "…", "media_items": [{"url","type"}], ...}

قواعد همه از batch (per_post_rules) می‌آیند:
    {"skip_video": bool, "crop_bottom_pct": float, "only_tags": bool, ...}
هیچ قاعده‌ی کانالی (skipped hashtags خاصِ کانال و...) اینجا نیست.
"""

from __future__ import annotations

import os
import shutil
import tempfile

from insta_lab import caption as cap
from insta_lab import media


def slice_media(post: dict, rules: dict | None = None) -> list:
    """اسلایدهای این پیج: drop_first / drop_last از قواعد پیج."""
    items = list(post.get("media_items") or [])
    r = rules or {}
    try:
        df = max(0, int(r.get("drop_first") or 0))
    except (TypeError, ValueError):
        df = 0
    try:
        dl = max(0, int(r.get("drop_last") or 0))
    except (TypeError, ValueError):
        dl = 0
    if df:
        items = items[df:]
    if dl and len(items) > dl:
        items = items[:-dl]
    return items


def evaluate(post: dict, rules: dict | None = None) -> dict:
    """پست را ارزیابی می‌کند → {"ready": bool, "skip": str|None, "caption": str|None, ...}"""
    r = rules or {}
    if cap.is_ad(post.get("caption") or ""):
        return {"ready": False, "skip": "ad"}
    media_items = slice_media(post, r)
    if not media_items:
        return {"ready": False, "skip": "no_media"}
    has_video = any((i.get("type") or "").lower() == "video" for i in media_items)
    if has_video and bool(r.get("skip_video")):
        return {"ready": False, "skip": "video"}
    return {"ready": True}


def prepare(post: dict, rules: dict | None = None) -> dict:
    """ارزیابی + ساخت کپشن. هنوز دانلود نمی‌کند (سریع‌ترین رد)."""
    out = evaluate(post, rules)
    if out["ready"]:
        r = rules or {}
        out["caption"] = cap.build_caption(post.get("caption") or "", only_tags=bool(r.get("only_tags")))
    return out


def materialize(post: dict, rules: dict | None = None, workdir: str = "") -> list:
    """دانلود + پردازش رسانه‌ها. خروجی: لیست مسیر فایل‌ها."""
    r = rules or {}
    media_items = slice_media(post, r)
    files, workdir = media.download_media_direct(media_items, workdir)
    pct = r.get("crop_bottom_pct")
    if pct:
        files = [media.crop_bottom_pct(f, float(pct)) for f in files]
    return files

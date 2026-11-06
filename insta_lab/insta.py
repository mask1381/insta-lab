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


def evaluate(post: dict, rules: dict | None = None) -> dict:
    """پست را ارزیابی می‌کند → {"ready": bool, "skip": str|None, "caption": str|None, ...}"""
    r = rules or {}
    media_items = list(post.get("media_items") or [])
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


def _num(v, lo=0, hi=60, default=0):
    try:
        n = float(v)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, n))


def materialize(post: dict, rules: dict | None = None, workdir: str = "") -> list:
    """دانلود + کراپ عکس + آماده‌سازی ویدیو (صدا / برش زمانی / کراپ پایین)."""
    r = rules or {}
    media_items = list(post.get("media_items") or [])
    files, workdir = media.download_media_direct(media_items, workdir)
    from insta_lab.mp4 import prepare_video

    # فقط آیتم‌های دارای url با فایل‌های دانلودشده هم‌ترتیب‌اند؛ شکست‌خورده‌ها پریده‌اند
    ok_items = [it for it in media_items if (it.get("url") or "").strip()]
    out = []
    for idx, path in enumerate(files):
        item = ok_items[idx] if idx < len(ok_items) else {}
        if str(path).lower().endswith((".mp4", ".mov", ".webm", ".m4v")):
            audio = None
            aurl = (item.get("audio_url") or item.get("audioUrl") or "").strip()
            if aurl:
                adest = os.path.join(workdir, f"aud_{idx}_{os.urandom(3).hex()}.m4a")
                try:
                    session = media.build_cffi_session()
                    media._download_binary(session, aurl, adest)
                    audio = adest
                except Exception:
                    audio = None
            out.append(prepare_video(
                path,
                crop_bottom_pct=r.get("crop_bottom_pct") or 0,
                trim_start_sec=_num(r.get("trim_start_sec")),
                trim_end_sec=_num(r.get("trim_end_sec")),
                audio_path=audio,
            ))
        else:
            out.append(media.crop_bottom_pct(path, float(r.get("crop_bottom_pct") or 0)))
    return out

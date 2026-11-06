"""
لایه‌ی رسانه — دانلود CDN اینستاگرام (مسیرِ بدون‌لاگین از Apify) + تبدیل webp→jpg + کراپ.

منبع این ماشین «اینستاگرام» است؛ اما هیچ شناسه/برند/قانون کانالی اینجا نیست.
media_items در batch می‌آید: [{"url": "https://scontent...", "type": "photo"|"video"}, ...]
این لینک‌های CDN از قبل امضاشده و عمومی‌اند (همان‌هایی که مرورگر می‌گیرد) —
پس فقط یک GET ساده، نیازی به لاگین/instaloader نیست.
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

from PIL import Image

from insta_lab import config

log = logging.getLogger(__name__)


def build_cffi_session():
    """سشن سخت‌شده: TLS/HTTP2 fingerprint مرورگر واقعی + پراکسی رزیدنشیالِ اختیاری."""
    from curl_cffi import requests as cffi_requests

    proxies = None
    if config.IG_PROXY_URL:
        proxies = {'http': config.IG_PROXY_URL, 'https': config.IG_PROXY_URL}

    session = cffi_requests.Session(
        impersonate=config.CURL_CFFI_IMPERSONATE or None,
        proxies=proxies,
        timeout=config.DOWNLOAD_TIMEOUT,
    )
    if config.IG_COOKIE:
        try:
            pairs = config.IG_COOKIE.split(";")
            for p in pairs:
                k, _, v = p.strip().partition("=")
                if k and v:
                    session.cookies.set(k, v)
        except Exception:
            pass
    return session


_BROWSER_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    ),
    'Accept': 'application/json, text/html;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}


def guess_ext(url: str, default: str = ".jpg") -> str:
    path = url.split("?")[0]
    ext = os.path.splitext(path)[1].lower()
    if ext in (".jpg", ".jpeg", ".png", ".gif", ".mp4", ".webp"):
        return ext
    return default


def _download_binary(session, url: str, dest: str) -> str:
    resp = session.get(url, headers=_BROWSER_HEADERS)
    resp.raise_for_status()
    with open(dest, "wb") as f:
        f.write(resp.content)
    return dest


def convert_webp_to_jpg(webp_path: str) -> str:
    """اینستاگرام عکس‌ها را webp سرو می‌کند؛ تلگرام webp را استیکر/فایل می‌گیرد نه عکس."""
    jpg_path = os.path.splitext(webp_path)[0] + ".jpg"
    try:
        with Image.open(webp_path) as img:
            if img.mode in ("RGBA", "P", "LA"):
                img = img.convert("RGB")
            img.save(jpg_path, "JPEG", quality=95)
        os.remove(webp_path)
        return jpg_path
    except Exception:
        return webp_path


def crop_bottom_pct(path: str, pct: float) -> str:
    """برشِ پایین عکس به اندازه‌ی pct (۰ تا ۱) — اختیاری، از batch/پروفایل. ویدیو را دست نمی‌زند."""
    if pct is None or pct <= 0 or pct >= 1:
        return path
    if str(path).lower().endswith((".mp4", ".mov", ".webm")):
        return path
    try:
        with Image.open(path) as img:
            w, h = img.size
            keep = int(h * (1 - pct))
            if keep >= 1:
                img.crop((0, 0, w, keep)).save(path, "JPEG", quality=90)
        return path
    except Exception:
        return path


def download_media_direct(media_items: list, workdir: str = "") -> tuple:
    """media_items → (files: list[str], workdir: str).

    هر آیتمی که دانلودش fail شود log.error می‌زند و از files حذف می‌شود.
    اگر هیچ فایلی دانلود نشود، files خالی برمی‌گردد — caller باید چک کند.
    Return: (files, workdir)
    """
    workdir = workdir or tempfile.mkdtemp(prefix="igjob_")
    session = build_cffi_session()
    files = []
    failures = 0

    for idx, item in enumerate(media_items):
        url = (item.get("url") or "").strip()
        mtype = (item.get("type") or "").lower()
        if not url:
            log.warning("item %d: no url, skipping", idx)
            failures += 1
            continue
        ext = ".mp4" if mtype == "video" else guess_ext(url)
        dest = os.path.join(workdir, f"ig_{idx}_{os.urandom(3).hex()}{ext}")
        try:
            _download_binary(session, url, dest)
            files.append(dest)
        except Exception as e:
            log.error("download failed for item %d url=%s: %s", idx, url, e)
            failures += 1

    if failures and not files:
        log.error("all %d downloads failed — returning empty file list", failures)
    elif failures:
        log.warning("%d of %d downloads failed — album will be partial", failures, len(media_items))

    files = [convert_webp_to_jpg(f) if f.lower().endswith(".webp") else f for f in files]
    return files, workdir

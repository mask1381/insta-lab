"""
موتور کپشن Insta Lab — کانال-اگنوستیک.

قالب، حذف تکه، تشخیص تبلیغ، انشا (تیتر/بدنه/نتیجه) همه از batch["caption"] می‌آیند.
فوتر و برند هم از batch.
"""
from __future__ import annotations

import html
import re

from insta_lab import config

_FOOTER = ""
_BRAND_TAG = ""
_CFG: dict = {}

DEFAULT_AD = [
    r"pre-?order", r"buy now", r"shop now", r"limited offer", r"%\s*off",
    r"giveaway", r"sponsored", r"affiliate", r"link in bio", r"use code",
    r"order now", r"available on", r"merch store",
    r"پیش.?خرید", r"تخفیف", r"کد تخفیف", r"اسپانسر", r"تبلیغ",
    r"لینک در بیو", r"فروشگاه رسمی", r"سفارش از",
]


def set_footer(footer: str) -> None:
    global _FOOTER
    _FOOTER = str(footer or "").strip()


def set_brand_tag(tag: str) -> None:
    global _BRAND_TAG
    _BRAND_TAG = (str(tag or "").strip().lstrip("#"))


def set_caption_cfg(cfg: dict | None) -> None:
    global _CFG
    _CFG = dict(cfg or {})


def get_brand_tag() -> str:
    return _BRAND_TAG


def extract_hashtags(caption: str) -> list[str]:
    if not caption:
        return []
    return re.findall(r"#[\w؀-ۿ]+", caption)


def trim_caption(caption: str, limit: int = None) -> str:
    limit = limit or config.MAX_TG_CAPTION_LEN
    caption = (caption or "").strip()
    if len(caption) > limit:
        caption = caption[:limit - 1].rstrip() + "…"
    return caption


def _esc(s: str) -> str:
    return html.escape(str(s or ""), quote=False)


def apply_strip(text: str) -> str:
    out = text or ""
    for pat in _CFG.get("strip") or []:
        if not pat:
            continue
        try:
            out = re.sub(str(pat), "", out, flags=re.I | re.M)
        except re.error:
            out = out.replace(str(pat), "")
    return re.sub(r"\n{3,}", "\n\n", out).strip()


def is_ad(text: str) -> bool:
    ad = _CFG.get("ad_detect") or {}
    if not ad.get("enabled"):
        return False
    blob = text or ""
    patterns = ad.get("patterns") or DEFAULT_AD
    for pat in patterns:
        if not pat:
            continue
        try:
            if re.search(str(pat), blob, flags=re.I):
                return True
        except re.error:
            if str(pat).lower() in blob.lower():
                return True
    return False


def split_essay(text: str) -> dict:
    tags = extract_hashtags(text)
    lines = []
    for ln in (text or "").splitlines():
        s = ln.strip()
        if not s:
            continue
        if re.fullmatch(r"(?:#[\w؀-ۿ]+\s*)+", s):
            continue
        lines.append(s)
    if not lines:
        return {"title": "", "body": "", "result": "", "hashtags": tags}
    title = lines[0]
    if len(lines) == 1:
        return {"title": title, "body": "", "result": "", "hashtags": tags}
    if len(lines) == 2:
        return {"title": title, "body": lines[1], "result": "", "hashtags": tags}
    return {
        "title": title,
        "body": "\n".join(lines[1:-1]),
        "result": lines[-1],
        "hashtags": tags,
    }


def _apply_tpl(tpl: str, value: str) -> str:
    if not value:
        return ""
    raw = tpl or "{value}"
    if "{title}" in raw or "{body}" in raw or "{result}" in raw or "{value}" in raw:
        return raw.replace("{title}", _esc(value)).replace("{body}", _esc(value)).replace("{result}", _esc(value)).replace("{value}", _esc(value))
    return f"{raw}{_esc(value)}" if raw else _esc(value)


def _suffix() -> str:
    suffix = _FOOTER
    if _BRAND_TAG:
        suffix = ("#" + _BRAND_TAG) + ("\n\n" + suffix if suffix else "")
    return suffix


def build_caption(original: str, only_tags: bool = False) -> str:
    limit = config.MAX_TG_CAPTION_LEN
    suffix = _suffix()
    cleaned = apply_strip(original or "")

    if only_tags:
        body = " ".join(extract_hashtags(cleaned))
        suffix_cost = len(suffix) + (2 if body and suffix else 0)
        body = trim_caption(body, limit=max(0, limit - suffix_cost))
        text = body + ("\n\n" + suffix if body and suffix else suffix)
        return text[:limit] if text else ""

    parts = split_essay(cleaned)
    tpl = _CFG.get("templates") or {}
    short_min = int(_CFG.get("short_min") or 80)
    short_mode = str(_CFG.get("short_mode") or "as_is")
    essay_len = len((parts["title"] + parts["body"] + parts["result"]).strip())

    layout = list(_CFG.get("layout") or ["title", "body", "result", "hashtags", "footer"])

    if essay_len < short_min:
        if short_mode == "tags_only":
            layout = ["hashtags", "footer"]
        elif short_mode == "title_only":
            layout = ["title", "hashtags", "footer"]
        elif short_mode == "as_is":
            body = cleaned
            suffix_cost = len(suffix) + (2 if body and suffix else 0)
            body = trim_caption(body, limit=max(0, limit - suffix_cost))
            text = body + ("\n\n" + suffix if body and suffix else suffix)
            return text[:limit] if text else ""

    blocks = []
    for key in layout:
        if key == "title":
            chunk = _apply_tpl(tpl.get("title") or "<b>{title}</b>", parts["title"])
        elif key == "body":
            chunk = _apply_tpl(tpl.get("body") or "{body}", parts["body"])
        elif key == "result":
            chunk = _apply_tpl(tpl.get("result") or "<i>{result}</i>", parts["result"])
        elif key == "hashtags":
            tags = parts["hashtags"]
            chunk = " ".join(tags) if tags else ""
        elif key == "footer":
            continue
        else:
            chunk = ""
        if chunk:
            blocks.append(chunk)

    body = "\n\n".join(blocks).strip()
    use_footer = "footer" in layout or not layout
    attached = suffix if use_footer else ""
    suffix_cost = len(attached) + (2 if body and attached else 0)
    body = trim_caption(body, limit=max(0, limit - suffix_cost))
    text = body + ("\n\n" + attached if body and attached else attached)
    return text[:limit] if text else ""

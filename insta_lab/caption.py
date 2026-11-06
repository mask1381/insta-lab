"""
موتور کپشن Insta Lab — کانال-اگنوستیک.

قالب، حذف تکه، تشخیص تبلیغ، انشا، هشتگ، چیدمان، متن ثابت همه از batch["caption"].
فوتر و برند از batch (و بلوک‌های layout).
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

TAG_RE = re.compile(r"#[^\s#]+")
HASHTAG_ONLY_RE = re.compile(r"(?:#[^\s#]+\s*)+")


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
    return TAG_RE.findall(caption)


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


def _strip_tags(text: str) -> str:
    out = TAG_RE.sub("", text or "")
    out = re.sub(r"[ \t]{2,}", " ", out)
    return re.sub(r"\n{3,}", "\n\n", out).strip()


def split_essay(text: str, mode: str | None = None) -> dict:
    tags = extract_hashtags(text)
    mode = mode or str(_CFG.get("split") or "lines")
    if mode == "as_is":
        return {"title": (text or "").strip(), "body": "", "result": "", "hashtags": tags}

    def keep(s: str) -> bool:
        s = s.strip()
        return bool(s) and not HASHTAG_ONLY_RE.fullmatch(s)

    if mode == "blank":
        chunks = [p.strip() for p in re.split(r"\n\s*\n", text or "") if keep(p)]
    elif mode == "sentence":
        blob = " ".join(ln.strip() for ln in (text or "").splitlines() if keep(ln)).strip()
        chunks = [s.strip() for s in re.split(r"(?<=[.!?؟۔])\s+", blob) if s.strip()] if blob else []
    else:
        chunks = [ln.strip() for ln in (text or "").splitlines() if keep(ln)]

    if not chunks:
        return {"title": "", "body": "", "result": "", "hashtags": tags}
    if len(chunks) == 1:
        return {"title": chunks[0], "body": "", "result": "", "hashtags": tags}
    if len(chunks) == 2:
        return {"title": chunks[0], "body": chunks[1], "result": "", "hashtags": tags}
    return {
        "title": chunks[0],
        "body": "\n".join(chunks[1:-1]),
        "result": chunks[-1],
        "hashtags": tags,
    }


def _apply_tpl(tpl: str, value: str, keys: tuple[str, ...], escape: bool = True) -> str:
    if not value:
        return ""
    raw = tpl or "{value}"
    v = _esc(value) if escape else str(value)
    used = False
    out = raw
    for k in (*keys, "value"):
        token = "{" + k + "}"
        if token in out:
            out = out.replace(token, v)
            used = True
    return out if used else f"{raw}{v}"


def _join(chunks: list[str]) -> str:
    sep = "\n" if str(_CFG.get("joiner") or "nlnl") == "nl" else "\n\n"
    return sep.join(x for x in chunks if x)


def _suffix() -> str:
    bits = []
    if _BRAND_TAG:
        bits.append("#" + _BRAND_TAG)
    if _FOOTER:
        bits.append(_FOOTER)
    return _join(bits)


def _attach(body: str, tail: str, limit: int) -> str:
    if not tail:
        return trim_caption(body, limit)
    sep = "\n" if str(_CFG.get("joiner") or "nlnl") == "nl" else "\n\n"
    extra = len(sep) if body else 0
    body = trim_caption(body, max(0, limit - len(tail) - extra))
    text = _join([body, tail]) if body else tail
    return text[:limit] if text else ""


def build_caption(original: str, only_tags: bool = False) -> str:
    limit = config.MAX_TG_CAPTION_LEN
    cleaned = apply_strip(original or "")
    extras = _CFG.get("extras") if isinstance(_CFG.get("extras"), dict) else {}
    tpl = _CFG.get("templates") if isinstance(_CFG.get("templates"), dict) else {}
    layout = list(_CFG.get("layout") or ["title", "body", "result", "hashtags", "brand", "footer"])

    if only_tags:
        return _attach(" ".join(extract_hashtags(cleaned)), _suffix(), limit)

    parts = split_essay(cleaned)
    policy = str(_CFG.get("tags") or "keep")
    if policy in ("extract", "drop"):
        parts["title"] = _strip_tags(parts["title"])
        parts["body"] = _strip_tags(parts["body"])
        parts["result"] = _strip_tags(parts["result"])
        if policy == "drop":
            parts["hashtags"] = []

    short_min = int(_CFG.get("short_min") or 80)
    short_mode = str(_CFG.get("short_mode") or "as_is")
    essay_len = len((parts["title"] + parts["body"] + parts["result"]).strip())

    if essay_len < short_min:
        if short_mode == "as_is":
            return _attach(cleaned, _suffix(), limit)
        if short_mode == "title_only":
            layout = ["title", "hashtags", "brand", "footer"]
        elif short_mode == "tags_only":
            layout = ["hashtags", "brand", "footer"]
        else:
            layout = list(_CFG.get("short_layout") or layout)

    blocks = []
    for key in layout:
        if key == "prefix":
            chunk = str(extras.get("prefix") or "")
        elif key == "title":
            chunk = _apply_tpl(tpl.get("title") or "<b>{title}</b>", parts["title"], ("title",))
        elif key == "body":
            chunk = _apply_tpl(tpl.get("body") or "{body}", parts["body"], ("body",))
        elif key == "result":
            chunk = _apply_tpl(tpl.get("result") or "<i>{result}</i>", parts["result"], ("result",))
        elif key == "hashtags":
            tags = parts["hashtags"]
            chunk = _apply_tpl(tpl.get("hashtags") or "{hashtags}", " ".join(tags), ("hashtags",), escape=False) if tags else ""
        elif key == "cta":
            chunk = _apply_tpl(tpl.get("cta") or "{cta}", str(extras.get("cta") or ""), ("cta",), escape=False)
        elif key == "extra":
            chunk = str(extras.get("extra") or "")
        elif key == "brand":
            chunk = ("#" + _BRAND_TAG) if _BRAND_TAG else ""
        elif key == "footer":
            chunk = _FOOTER
        else:
            chunk = ""
        if chunk:
            blocks.append((key, chunk))

    trail = _join([c for k, c in blocks if k in ("brand", "footer")])
    head = _join([c for k, c in blocks if k not in ("brand", "footer")])
    return _attach(head, trail, limit)

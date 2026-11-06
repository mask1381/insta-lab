"""
موتور کپشن Insta Lab — کانال-اگنوستیک.

پایه: کپشن پست از batch. چیدمان/تبلیغ/فوتر هم از batch می‌آید (همان قرارداد بات).
ماشین هویت ندارد.
"""

from __future__ import annotations

import html
import re

from insta_lab import config

_FOOTER = ""
_BRAND_TAG = ""
_CFG: dict = {}

DEFAULT_AD_PATTERNS = [
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


def get_brand_tag() -> str:
    return _BRAND_TAG


def set_caption_cfg(cfg) -> None:
    global _CFG
    _CFG = dict(cfg) if isinstance(cfg, dict) else {}


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


def is_ad_text(text: str) -> bool:
    if not _CFG:
        return False
    ad = _CFG.get("ad_detect") if isinstance(_CFG.get("ad_detect"), dict) else {}
    if ad.get("enabled") is False:
        return False
    patterns = ad.get("patterns")
    if not isinstance(patterns, list) or not patterns:
        patterns = DEFAULT_AD_PATTERNS
    blob = str(text or "")
    for pat in patterns:
        if not pat:
            continue
        try:
            if re.search(str(pat), blob, re.I):
                return True
        except re.error:
            if str(pat).lower() in blob.lower():
                return True
    return False


def _strip_tags(text: str) -> str:
    return re.sub(r"[ \t]{2,}", " ", re.sub(r"#[^\s#]+", "", text or "")).replace("\n\n\n", "\n\n").strip()


def _apply_strip(text: str, patterns) -> str:
    out = str(text or "")
    for pat in patterns or []:
        if not pat:
            continue
        try:
            out = re.sub(str(pat), "", out, flags=re.I | re.M)
        except re.error:
            out = out.replace(str(pat), "")
    return re.sub(r"\n{3,}", "\n\n", out).strip()


def _is_hashtag_only(s: str) -> bool:
    return bool(re.match(r"^(?:#[^\s#]+\s*)+$", (s or "").strip()))


def _split_essay(text: str, mode: str) -> dict:
    tags = extract_hashtags(text)
    cleaned = [l.strip() for l in (text or "").split("\n") if l.strip() and not _is_hashtag_only(l.strip())]
    if mode == "as_is":
        return {"title": (text or "").strip(), "body": "", "result": "", "hashtags": tags}
    chunks = cleaned
    if mode == "blank":
        chunks = [p.strip() for p in re.split(r"\n\s*\n", text or "") if p.strip() and not _is_hashtag_only(p.strip())]
    elif mode == "sentence":
        blob = " ".join(cleaned).strip()
        chunks = [s.strip() for s in re.split(r"(?<=[.!?؟۔])\s+", blob) if s.strip()] if blob else []
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


def _apply_tpl(tpl: str, value: str, keys, *, escape=True) -> str:
    if not value:
        return ""
    raw = tpl or "{value}"
    v = html.escape(value) if escape else str(value)
    out = raw
    used = False
    for k in list(keys) + ["value"]:
        token = "{" + k + "}"
        if token in out:
            out = out.replace(token, v)
            used = True
    return out if used else f"{raw}{v}"


def _plain(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s or "").strip()


def _has_footer(body: str, footer: str) -> bool:
    if not footer or not body:
        return False
    key = _plain(footer).split("\n", 1)[0].strip()
    return bool(key) and key in body


_GAMES = [
    ("WutheringWaves", re.compile(r"wuthering\s*waves|#wuwa\b", re.I)),
    ("GenshinImpact", re.compile(r"genshin|#gi\b(?![a-z])", re.I)),
    ("HonkaiStarRail", re.compile(r"star\s*rail|#hsr\b", re.I)),
    ("ZenlessZoneZero", re.compile(r"zenless|#zzz\b", re.I)),
]
_TOPIC_ORDER = ["Redeem_Code", "Clip", "Demo", "Guide", "Event", "Art", "News", "Leak"]
_TOPIC_RE = {
    "Redeem_Code": re.compile(r"#redeem|#code\b|redeem\s*code", re.I),
    "Clip": re.compile(r"#clip\b|\bextract\b|\bclip\b", re.I),
    "Demo": re.compile(r"#demo\b|character trailer|official trailer|\bdemo\b", re.I),
    "Guide": re.compile(r"#guide\b|creation guide", re.I),
    "Event": re.compile(r"#event\b|〓event|creator contest|#birthday\b", re.I),
    "Art": re.compile(r"#art\b|wallpaper|download\s*hd", re.I),
    "News": re.compile(r"#news\b|read full article|livestream recap", re.I),
    "Leak": re.compile(r"#leak\b|(?:^|\n)via\s+[A-Za-z]", re.I | re.M),
}
_CHAR_ALIASES = {
    "anastasyafeodorovnasnezhnaya": "Anastasya", "anastasya": "Anastasya",
    "tsaritsa": "Anastasya", "tsaritsas": "Anastasya",
    "furinadefontaine": "Furina", "furina": "Furina",
    "ilcapitano": "Capitano", "capitano": "Capitano",
    "kukishinobu": "KukiShinobu", "mitya": "Mitya", "danica": "Danica",
    "valeriy": "Valeriy", "noy": "Noy", "varka": "Varka", "lily": "Lily",
    "hiyuki": "Hiyuki", "suoming": "Suoming", "hsin": "Hsin",
    "sandrone": "Sandrone", "odette": "Odette", "qiqi": "Qiqi",
}
_JUNK = {
    "hoyoverse", "mihoyo", "kurogames", "instagram", "insta", "fyp", "viral",
    "explore", "anime", "game", "gaming", "waifu", "official", "livestream",
    "wuwalivestream", "wuwapc", "wuwa", "genshin", "gi", "honkai", "zzz", "hsr",
    "art", "leak", "news", "clip", "demo", "event", "guide", "birthday", "follow", "like",
    "genshinimpact", "wutheringwaves", "honkaistarrail", "zenlesszonezero", "honkaiimpact",
    "redeemcode", "redeem_code",
}


def _nk(tag: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (tag or "").lstrip("#").lower())


def shape_hub_caption(raw: str, topic_mode: str = "auto", aliases: dict | None = None) -> str:
    """قالب Hub: تیتر + Via + حداکثر ۳ هشتگ (موضوع، بازی، یک کاراکتر)."""
    als = {**_CHAR_ALIASES, **(aliases or {})}
    text = re.sub(r"^✦.*$", "", str(raw or ""), flags=re.M)
    text = re.sub(r"^↠.*$", "", text, flags=re.M)
    text = re.sub(r"follow us for more[^\n]*", "", text, flags=re.I)
    tags = [t.lstrip("#") for t in extract_hashtags(text)]
    lines = []
    for l in text.splitlines():
        s = l.strip()
        if not s or _is_hashtag_only(s) or s.startswith("✦") or s.startswith("↠"):
            continue
        lines.append(s)
    via = [l for l in lines if re.match(r"^(via |source:)", l, re.I)]
    body = [re.sub(r"#[^\s#]+", "", l).strip() for l in lines if not re.match(r"^(via |source:)", l, re.I)]
    body = [l for l in body if l and not re.match(r"^link in bio", l, re.I)]
    title = body[0] if body else ""
    rest = body[1:]
    blob = f"{title}\n{chr(10).join(rest)}\n{chr(10).join(via)}\n" + " ".join(f"#{t}" for t in tags)
    game = next((n for n, rx in _GAMES if rx.search(blob)), "")
    found = [n for n in _TOPIC_ORDER if _TOPIC_RE[n].search(blob)]
    hit = found[0] if found else ""
    mode = topic_mode or "auto"
    if mode == "official":
        topic = next((t for t in found if t != "Leak"), "") or "News"
    elif mode == "leak":
        topic = hit if hit and hit not in ("Leak", "News") else ("News" if hit == "News" else "Leak")
    else:
        topic = hit
    char = ""
    for t in tags:
        key = _nk(t)
        if key in _JUNK:
            continue
        if als.get(key):
            char = als[key]
            break
        pretty = t
        if len(pretty) > 22:
            parts = re.findall(r"[A-Z][a-z]{2,}", pretty)
            char = als.get(_nk(parts[0]), parts[0]) if parts else ""
            if char:
                break
        elif re.match(r"^[A-Z][A-Za-z]{2,21}$", pretty):
            char = pretty
            break
    out_tags = []
    if topic:
        out_tags.append(f"#{topic}")
    if game:
        out_tags.append(f"#{game}")
    if char and _nk(char) not in {_nk(game), _nk(topic)}:
        out_tags.append(f"#{char}")
    parts = [title] if title else []
    read = [l for l in rest if re.search(r"read full|youtube:", l, re.I)][-1:]
    mid = via + [l for l in rest if not re.search(r"read full|youtube:", l, re.I)]
    mid = [l for l in mid if l != title][:6]
    if read:
        mid.append(read[0])
    if mid:
        parts.append("\n".join(mid))
    if out_tags:
        parts.append(" ".join(out_tags))
    return "\n\n".join(p for p in parts if p).strip()


def build_caption(original: str, only_tags: bool = False, rules: dict | None = None) -> str:
    """کپشن نهایی طبق قرارداد بات (چیدمان) یا پاس‌ثرو + برند/فوتر."""
    limit = config.MAX_TG_CAPTION_LEN
    cfg = _CFG if isinstance(_CFG, dict) else {}
    if cfg.get("hub_policy") and not only_tags:
        body = shape_hub_caption(
            original or "",
            topic_mode=str((rules or {}).get("topic_mode") or "auto"),
            aliases=cfg.get("hub_aliases") if isinstance(cfg.get("hub_aliases"), dict) else None,
        )
        suffix = _FOOTER
        if _BRAND_TAG:
            suffix = ("#" + _BRAND_TAG) + (("\n\n" + suffix) if suffix else "")
        if _has_footer(body, _FOOTER):
            suffix = ("#" + _BRAND_TAG) if _BRAND_TAG else ""
        suffix_cost = len(suffix) + (2 if body and suffix else 0)
        body = trim_caption(body, limit=max(0, limit - suffix_cost))
        text = body + (("\n\n" + suffix) if body and suffix else suffix)
        return text[:limit] if text else ""
    layout = [x for x in (cfg.get("layout") or []) if isinstance(x, str)]

    if only_tags or not layout:
        suffix = _FOOTER
        if _BRAND_TAG:
            suffix = ("#" + _BRAND_TAG) + (("\n\n" + suffix) if suffix else "")
        if only_tags:
            body = " ".join(extract_hashtags(original))
        else:
            body = (original or "").strip()
        if _has_footer(body, _FOOTER):
            suffix = ("#" + _BRAND_TAG) if _BRAND_TAG else ""
        suffix_cost = len(suffix) + (2 if body and suffix else 0)
        body = trim_caption(body, limit=max(0, limit - suffix_cost))
        text = body + (("\n\n" + suffix) if body and suffix else suffix)
        return text[:limit] if text else ""

    cleaned = _apply_strip(original or "", cfg.get("strip") or [])
    brand = _BRAND_TAG
    footer = _FOOTER
    sep = "\n" if cfg.get("joiner") == "nl" else "\n\n"
    split_mode = cfg.get("split") if cfg.get("split") in ("lines", "blank", "sentence", "as_is") else "lines"
    parts = _split_essay(cleaned, split_mode)
    tags_mode = cfg.get("tags") or "keep"
    if tags_mode in ("extract", "drop"):
        parts["title"] = _strip_tags(parts["title"])
        parts["body"] = _strip_tags(parts.get("body") or "")
        parts["result"] = _strip_tags(parts.get("result") or "")
        if tags_mode == "drop":
            parts["hashtags"] = []
    essay_len = len(f"{parts.get('title') or ''}{parts.get('body') or ''}{parts.get('result') or ''}".strip())
    short_min = cfg.get("short_min")
    try:
        short_min = int(short_min)
    except (TypeError, ValueError):
        short_min = 80
    short_mode = cfg.get("short_mode") or "as_is"
    use_layout = list(layout)
    tpl = cfg.get("templates") if isinstance(cfg.get("templates"), dict) else {}
    extras = cfg.get("extras") if isinstance(cfg.get("extras"), dict) else {}

    if essay_len < short_min and short_mode == "as_is":
        suffix_bits = []
        if "brand" in layout and brand:
            suffix_bits.append("#" + brand)
        if "footer" in layout and footer and not _has_footer(cleaned, footer):
            suffix_bits.append(footer)
        attached = sep.join(suffix_bits)
        text = sep.join([x for x in (cleaned, attached) if x])
        return text[:limit]

    if essay_len < short_min:
        if short_mode == "title_only":
            use_layout = [x for x in ("title", "hashtags", "brand", "footer") if x in layout or x in ("title", "hashtags")]
        elif short_mode == "tags_only":
            use_layout = ["hashtags", "brand", "footer"]
        else:
            sl = [x for x in (cfg.get("short_layout") or []) if isinstance(x, str)]
            if sl:
                use_layout = sl

    blocks = []
    for key in use_layout:
        chunk = ""
        if key == "prefix":
            chunk = extras.get("prefix") or ""
        elif key == "title":
            chunk = _apply_tpl(tpl.get("title") or "<b>{title}</b>", parts.get("title") or "", ["title"])
        elif key == "body":
            chunk = _apply_tpl(tpl.get("body") or "{body}", parts.get("body") or "", ["body"])
        elif key == "result":
            chunk = _apply_tpl(tpl.get("result") or "<i>{result}</i>", parts.get("result") or "", ["result"])
        elif key == "hashtags":
            tags = parts.get("hashtags") or []
            chunk = _apply_tpl(tpl.get("hashtags") or "{hashtags}", " ".join(tags), ["hashtags"], escape=False) if tags else ""
        elif key == "cta":
            extra_cta = extras.get("cta") or ""
            chunk = _apply_tpl(tpl.get("cta") or "{cta}", extra_cta, ["cta"], escape=False) if extra_cta else ""
        elif key == "extra":
            chunk = extras.get("extra") or ""
        elif key == "brand":
            chunk = f"#{brand}" if brand else ""
        elif key == "footer":
            chunk = footer if footer and not _has_footer("\n".join(blocks), footer) else ""
        if chunk:
            blocks.append(chunk)
    return sep.join(blocks)[:limit]

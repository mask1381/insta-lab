"""
موتور کپشن Insta Lab — کانال-اگنوستیک.

پایه: کپشن پست از batch. چیدمان/تبلیغ/فوتر هم از batch می‌آید (همان قرارداد بات).
ماشین هویت ندارد.
"""

from __future__ import annotations

import html
import re
import unicodedata

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


def clip_html(html: str, limit: int) -> str:
    s = str(html or "")
    if len(s) <= limit:
        return _close_html(s)
    s = s[: max(0, limit - 96)]
    lt, gt = s.rfind("<"), s.rfind(">")
    if lt > gt:
        s = s[:lt]
    amp, semi = s.rfind("&"), s.rfind(";")
    if amp > semi:
        s = s[:amp]
    return _close_html(s)


def _close_html(html: str) -> str:
    open_tags: list[str] = []
    for m in re.finditer(r"</?([a-z][a-z0-9-]*)\b[^>]*>", html, re.I):
        name = m.group(1).lower()
        if name in ("br", "hr", "img"):
            continue
        if m.group(0).startswith("</"):
            for i in range(len(open_tags) - 1, -1, -1):
                if open_tags[i] == name:
                    open_tags.pop(i)
                    break
        else:
            open_tags.append(name)
    out = html
    while open_tags:
        out += f"</{open_tags.pop()}>"
    return out


def trim_caption(caption: str, limit: int = None) -> str:
    limit = limit or config.MAX_TG_CAPTION_LEN
    caption = (caption or "").strip()
    if len(caption) > limit:
        return clip_html(caption, limit)
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


_TOPIC_ORDER = ["Redeem_Code", "Clip", "Demo", "Guide", "Event", "Art", "News", "Leak"]
_TOPIC_RE = {
    "Redeem_Code": re.compile(r"#redeem|#code\b|redeem\s*code|\bcodes\b", re.I),
    "Clip": re.compile(r"#clip\b|\bextract\b", re.I),
    "Demo": re.compile(r"#demo\b|character trailer|official trailer", re.I),
    "Guide": re.compile(r"#guide\b|creation guide", re.I),
    "Event": re.compile(r"#event\b|〓event|creator contest|#birthday\b", re.I),
    "Art": re.compile(r"#art\b|wallpaper|download\s*hd", re.I),
    "News": re.compile(r"#news\b|read full article|livestream recap", re.I),
}
_JUNK = {
    "hoyoverse", "mihoyo", "kurogames", "instagram", "insta", "fyp", "viral",
    "explore", "anime", "game", "gaming", "waifu", "official", "livestream",
    "art", "leak", "news", "clip", "demo", "event", "guide", "birthday", "follow", "like",
}


def _nk(tag: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (tag or "").lstrip("#").lower())


def match_pack(text: str, items) -> str:
    compact = _nk(text)
    best, best_len = "", 0
    for it in items or []:
        if isinstance(it, str):
            tag, keys = it, [_nk(it)]
        else:
            tag = str(it.get("tag") or it.get("name") or "").lstrip("#")
            keys = [_nk(tag), *(_nk(k) for k in (it.get("keys") or it.get("aliases") or []))]
        for k in keys:
            if len(k) < 3 or k in _JUNK:
                continue
            if k in compact and len(k) > best_len:
                best, best_len = tag, len(k)
    return best


def _detect_topic(text: str, mode: str) -> str:
    others = [n for n in _TOPIC_ORDER if n != "Leak" and _TOPIC_RE.get(n) and _TOPIC_RE[n].search(text)]
    if mode == "official":
        return others[0] if others else "News"
    if others:
        return others[0]
    if re.search(r"#leak\b", text, re.I) or re.search(r"\b(leaked|datamine[ds]?)\b", text, re.I):
        return "Leak"
    credit = re.search(r"(?:^|\n)via\s+(?!official\b)[A-Za-z]{2,}", text, re.I | re.M) or re.search(
        r"(?:^|\n)source:\s*(?!official\b|wuthering waves official)", text, re.I | re.M
    )
    if mode == "leak" and credit:
        return "Leak"
    return ""


def hub_parts(raw: str, topic_mode: str = "auto", pack: dict | None = None, aliases: dict | None = None) -> dict:
    pack = pack or {}
    names = list(pack.get("names") or [])
    if aliases:
        names.extend({"tag": v, "keys": [k]} for k, v in aliases.items())
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
    game = match_pack(blob, pack.get("games") or [])
    topic = _detect_topic(blob, topic_mode or "auto")
    char = match_pack(f"{title}\n{' '.join(tags)}", names)
    out_tags = []
    if topic:
        out_tags.append(f"#{topic}")
    if game:
        out_tags.append(f"#{game}")
    if char and _nk(char) not in {_nk(game), _nk(topic)}:
        out_tags.append(f"#{char}")
    result_re = re.compile(r"read full|youtube:|redeem now|🔗", re.I)
    result_lines = [l for l in rest if result_re.search(l)]
    mid = via + [l for l in rest if not result_re.search(l) and l != title]
    return {
        "title": title,
        "body": "\n".join(mid[:8]).strip(),
        "result": result_lines[-1] if result_lines else "",
        "hashtags": out_tags,
    }


def shape_hub_caption(raw: str, topic_mode: str = "auto", pack: dict | None = None, aliases: dict | None = None) -> str:
    p = hub_parts(raw, topic_mode, pack, aliases)
    return "\n\n".join(x for x in (p["title"], p["body"], p["result"], " ".join(p["hashtags"])) if x).strip()


def _math_font(text: str, bold: bool) -> str:
    out = []
    for ch in text or "":
        o = ord(ch)
        if 65 <= o <= 90:
            out.append(chr((0x1D400 if bold else 0x1D434) + o - 65))
        elif 97 <= o <= 122:
            if not bold and ch == "h":
                out.append("\u210e")
            else:
                out.append(chr((0x1D41A if bold else 0x1D44E) + o - 97))
        elif bold and 48 <= o <= 57:
            out.append(chr(0x1D7CE + o - 48))
        else:
            out.append(ch)
    return "".join(out)


def _credit_only(body: str) -> bool:
    lines = [l.strip() for l in (body or "").splitlines() if l.strip()]
    return bool(lines) and all(re.match(r"^(via |source:)", l, re.I) for l in lines)


def style_title(text: str, font: str) -> str:
    t = (text or "").strip()
    if not t:
        return ""
    if font == "u_italic":
        return html.escape(_math_font(t, False))
    if font == "u_bold":
        return html.escape(_math_font(t, True))
    if font == "bold":
        return f"<b>{html.escape(t)}</b>"
    if font == "italic":
        return f"<i>{html.escape(t)}</i>"
    return html.escape(t)


def wrap_quote(text: str, mode: str) -> str:
    t = (text or "").strip()
    if not t:
        return ""
    inner = html.escape(t)
    if mode == "expand":
        return f"<blockquote expandable>{inner}</blockquote>"
    if mode == "quote":
        return f"<blockquote>{inner}</blockquote>"
    return inner


_CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af]")
_LATIN_TAG_RE = re.compile(r"[A-Za-z0-9_\u00C0-\u024F]+")
_PROFILE_KEYS = (
    "nfkc", "split_title", "raw_caption", "drop_text", "own_hashtags",
    "keep_lines", "strip_blocks", "strip_label", "tags_from_field", "result_field",
    "hashtag_fallback", "fallback_hashtag", "extra_hashtags", "blocked_hashtags",
    "blocked_patterns", "fixed_caption", "text_replace", "hashtag_mode", "max_hashtags",
)


def skip_caption_reason(raw: str, rules: dict | None = None) -> str:
    r = rules or {}
    text = str(raw or "")
    if r.get("nfkc"):
        text = unicodedata.normalize("NFKC", text)
    for pat in r.get("skip_if_caption_matches") or []:
        if not pat:
            continue
        try:
            m = re.search(str(pat), text, re.I | re.M)
        except re.error:
            m = None
        if m:
            return "caption_match"
    if r.get("skip_if_all_cjk"):
        plain = re.sub(r"#\w+|@[\w.]+|https?://\S+", " ", text)
        if _CJK_RE.search(plain) and not re.search(r"[A-Za-z]{2,}", plain):
            return "cjk"
    if r.get("skip_if_ad") and is_ad_text(text):
        return "ad"
    return ""


def _to_hashtag(name: str) -> str:
    parts = re.findall(r"[A-Za-z0-9]+", unicodedata.normalize("NFKD", name or ""))
    if not parts:
        return ""
    tag = "".join(p[:1].upper() + p[1:] for p in parts)
    return tag[:40] if len(tag) >= 2 else ""


def _latin_tag(h: str) -> str:
    m = _LATIN_TAG_RE.match((h or "").lstrip("#"))
    tag = m.group(0) if m else ""
    return tag if len(tag) >= 2 else ""


def _blocked_tag(tag: str, rules: dict) -> bool:
    key = re.sub(r"[^0-9a-z]", "", (tag or "").lstrip("#").lower())
    blocked = {str(b).lstrip("#").lower().replace("_", "") for b in (rules.get("blocked_hashtags") or [])}
    if key in blocked:
        return True
    for pat in rules.get("blocked_patterns") or []:
        if not pat:
            continue
        try:
            if re.search(str(pat), key, re.I):
                return True
        except re.error:
            continue
    return False


def _filter_tags(tags, rules: dict) -> list[str]:
    out, seen = [], set()
    for t in tags or []:
        tag = _latin_tag(str(t))
        key = tag.lower()
        if not key or key in seen or _blocked_tag(tag, rules):
            continue
        seen.add(key)
        out.append("#" + tag)
    for h in rules.get("extra_hashtags") or []:
        tag = _latin_tag(str(h)) or re.sub(r"[^A-Za-z0-9]", "", str(h).lstrip("#"))
        key = tag.lower()
        if tag and key not in seen:
            seen.add(key)
            out.append("#" + tag)
    capn = rules.get("max_hashtags")
    try:
        capn = int(capn)
    except (TypeError, ValueError):
        capn = 0
    if capn and capn > 0:
        out = out[:capn]
    return out


_FOLLOW_LINE = re.compile(
    r"(?im)^\s*(?:follow(?:\s+\w+){0,6}\s+@[\w.]+.*|follow\s+(?:us\s+)?for\s+more.*)\s*$"
)
_JUNK_LINE = re.compile(r"(?im)^\s*(?:[-–—.]+|💠+)\s*$")
_DETAIL_LABEL = re.compile(
    r"(?im)^\s*anime\s+de[a-z]{3,16}\b[^\n:]*:?\s*(.*)$"
)
_DEFAULT_RESULT = re.compile(r"read full|youtube:|redeem now|🔗|^\s*song\s*:", re.I)


def _strip_follow(text: str) -> str:
    return _FOLLOW_LINE.sub("", text or "")


def _loose_tag_tokens(line: str) -> list[str]:
    toks = [t.strip("#,;.") for t in (line or "").split() if t.strip("#,;.")]
    if len(toks) < 2:
        return []
    if all(re.fullmatch(r"[A-Za-z][A-Za-z0-9]{2,}", t) for t in toks):
        return toks
    return []


def _strip_end_tags(text: str) -> str:
    lines = []
    trail = re.compile(r"(?:[ \t]*#[^\s#]+)+[ \t]*$")
    for line in (text or "").split("\n"):
        head = trail.sub("", line)
        head = re.sub(r"#[^\s#]+", lambda m: m.group(0)[1:], head)
        lines.append(head)
    t = "\n".join(lines)
    t = re.sub(r"[ \t]+\n", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def _drop_block_lines(text: str, patterns) -> str:
    regs = []
    for p in patterns or []:
        try:
            regs.append(re.compile(str(p), re.I | re.M))
        except re.error:
            continue
    if not regs:
        return text
    kept = []
    for ln in (text or "").splitlines():
        if any(r.search(ln) for r in regs):
            continue
        kept.append(ln)
    return "\n".join(kept).strip()


def _keep_only_lines(text: str, patterns) -> str:
    regs = []
    for p in patterns or []:
        try:
            regs.append(re.compile(str(p), re.I))
        except re.error:
            continue
    if not regs:
        return text
    return "\n".join(ln.strip() for ln in (text or "").splitlines() if any(r.search(ln) for r in regs))


def profile_parts(raw: str, rules: dict | None = None, pack: dict | None = None) -> dict:
    r = rules or {}
    text = unicodedata.normalize("NFKC", str(raw or ""))
    text = _strip_follow(text)
    for pair in r.get("text_replace") or []:
        if not isinstance(pair, (list, tuple)) or len(pair) < 2:
            continue
        try:
            text = re.sub(str(pair[0]), str(pair[1]), text, flags=re.I | re.M)
        except re.error:
            continue
    title = body = result = ""
    tags: list[str] = []
    fixed = str(r.get("fixed_caption") or "").strip()
    if r.get("drop_text"):
        pass
    elif fixed:
        toks = fixed.split()
        if toks and all(t.startswith("#") for t in toks):
            tags = list(toks)
        else:
            body = fixed
    elif r.get("raw_caption"):
        body = _strip_end_tags(text)
        if r.get("split_title") is not False:
            lines = [l.strip() for l in body.splitlines() if l.strip() and not _JUNK_LINE.match(l)]
            if lines:
                title, body = lines[0], "\n".join(lines[1:]).strip()
                if len(title) > 80:
                    sent = re.match(r"(.{12,140}?[.!?؟])(?:\s+|$)", title)
                    if sent:
                        title, extra = sent.group(1).strip(), title[sent.end():].strip()
                        body = "\n".join(x for x in (extra, body) if x)
    else:
        body = _apply_strip(_drop_block_lines(text, r.get("strip_blocks")), [])
        if r.get("keep_lines"):
            body = _keep_only_lines(body, r.get("keep_lines"))
        body = _strip_end_tags(body)
        body = _DETAIL_LABEL.sub(lambda m: (m.group(1) or "").strip(), body).strip()
        body = "\n".join(ln for ln in body.splitlines() if not _JUNK_LINE.match(ln)).strip()
        split_on = r.get("split_title")
        if split_on is None:
            split_on = True
        if split_on and body:
            lines = [l.strip() for l in body.splitlines() if l.strip()]
            if lines:
                title, body = lines[0], "\n".join(lines[1:]).strip()
                if len(title) > 80:
                    sent = re.match(r"(.{12,140}?[.!?؟])(?:\s+|$)", title)
                    if sent:
                        title, extra = sent.group(1).strip(), title[sent.end():].strip()
                        body = "\n".join(x for x in (extra, body) if x)
        if body and r.get("strip_label"):
            try:
                body = re.sub(str(r["strip_label"]), "", body, count=1, flags=re.I).strip()
            except re.error:
                pass
    if body and not r.get("drop_text") and not fixed:
        body_lines = [ln for ln in body.splitlines()]
        if body_lines:
            loose = _loose_tag_tokens(body_lines[-1])
            if loose:
                tags.extend("#" + _to_hashtag(t) for t in loose)
                body_lines = body_lines[:-1]
                body = "\n".join(body_lines).strip()
        result_pat = r.get("result_field") or _DEFAULT_RESULT.pattern
        try:
            rf = re.compile(str(result_pat), re.I | re.M)
            keep, hit = [], ""
            for ln in body.splitlines():
                if rf.search(ln) and not hit:
                    hit = ln.strip()
                else:
                    keep.append(ln)
            result, body = hit, "\n".join(keep).strip()
        except re.error:
            pass
    own = r.get("own_hashtags") or r.get("raw_caption") or r.get("hashtag_mode") in ("own", "raw")
    collected = list(tags)
    take_own = own or (
        not r.get("tags_from_field")
        and r.get("hashtag_mode") not in ("pack", "none")
        and not r.get("drop_text")
        and not r.get("fixed_caption")
    )
    if take_own:
        collected.extend(extract_hashtags(text))
    tags = collected
    if not tags and r.get("tags_from_field"):
        try:
            m = re.search(str(r["tags_from_field"]), text, re.I | re.M)
        except re.error:
            m = None
        if m:
            h = _to_hashtag(m.group(1))
            if h:
                tags = tags + ["#" + h]
    if not tags and r.get("hashtag_fallback") in ("pack", "dictionary"):
        blob = f"{title}\n{body}\n{text}"
        game = match_pack(blob, (pack or {}).get("games") or [])
        char = match_pack(f"{title}\n{text}", (pack or {}).get("names") or [])
        tags = _filter_tags([f"#{x}" for x in (game, char) if x], r)
    if not tags and r.get("fallback_hashtag"):
        tags = ["#" + str(r["fallback_hashtag"]).lstrip("#")]
    tags = _filter_tags(tags, r) or tags
    body = "\n".join(ln for ln in body.splitlines() if not _JUNK_LINE.match(ln)).strip()
    return {"title": title, "body": body, "result": result, "hashtags": tags}


def uses_profile_caption(rules: dict | None, cfg: dict | None) -> bool:
    r = rules or {}
    c = cfg or {}
    if c.get("nexus_policy") or c.get("profile_caption"):
        return True
    return any(r.get(k) for k in _PROFILE_KEYS)


def style_result(text: str, mode: str) -> str:
    t = (text or "").strip()
    if not t:
        return ""
    if mode == "italic":
        return f"<i>{html.escape(t)}</i>"
    if mode in ("quote", "expand"):
        return wrap_quote(t, mode)
    return html.escape(t)


def build_caption(original: str, only_tags: bool = False, rules: dict | None = None) -> str:
    """..."""
    limit = config.MAX_TG_CAPTION_LEN
    cfg = _CFG if isinstance(_CFG, dict) else {}
    
    # اصلاح خط ۶۲۴ تا ۶۲۶
    layout = [x for x in (cfg.get("layout") or []) if isinstance(x, str)]
    
    rules = rules or {}
    
    # اصلاح خط ۶۲۷ تا ۶۲۹
    profiled = uses_profile_caption(rules, cfg) and not only_tags

    # اصلاح خط ۶۳۰ به بعد
    if only_tags or (not layout and not cfg.get("hub_policy") and not profiled):
        suffix = _FOOTER  # <--- این خط باید نسبت به if جلوتر باشه (۸ فاصله)
        
        if _BRAND_TAG:
            suffix = ("#" + _BRAND_TAG) + ("\n\n" + suffix) if suffix else ""
            
        if only_tags:
            hp = profile_parts(original or "", rules, cfg.get("hub_tags") if isinstance(cfg.get("hub_tags"), dict) else {})
            body = " ".join(hp.get("hashtags") or extract_hashtags(original))
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
    hub = bool(cfg.get("hub_policy")) and not only_tags
    if hub:
        hp = hub_parts(
            original or "",
            topic_mode=str((rules or {}).get("topic_mode") or "auto"),
            pack=cfg.get("hub_tags") if isinstance(cfg.get("hub_tags"), dict) else {},
            aliases=cfg.get("hub_aliases") if isinstance(cfg.get("hub_aliases"), dict) else None,
        )
        parts = {"title": hp["title"], "body": hp["body"], "result": hp["result"], "hashtags": hp["hashtags"]}
        if not layout:
            layout = ["title", "body", "result", "hashtags", "footer"]
    elif profiled:
        hp = profile_parts(
            original or "",
            rules,
            cfg.get("hub_tags") if isinstance(cfg.get("hub_tags"), dict) else {},
        )
        parts = {"title": hp["title"], "body": hp["body"], "result": hp["result"], "hashtags": hp["hashtags"]}
        if not layout:
            layout = ["title", "body", "result", "hashtags", "footer"]
    policy = hub or profiled
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

    if essay_len < short_min and short_mode == "as_is" and not policy:
        suffix_bits = []
        if "brand" in layout and brand:
            suffix_bits.append("#" + brand)
        if "footer" in layout and footer and not _has_footer(cleaned, footer):
            suffix_bits.append(footer)
        attached = sep.join(suffix_bits)
        text = sep.join([x for x in (cleaned, attached) if x])
        return text[:limit]

    if essay_len < short_min and not policy:
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
            font = str(cfg.get("title_font") or "as_is")
            if font != "as_is":
                chunk = style_title(parts.get("title") or "", font)
            else:
                chunk = _apply_tpl(tpl.get("title") or "<b>{title}</b>", parts.get("title") or "", ["title"])
        elif key == "body":
            quote = str(cfg.get("body_quote") or "off")
            body_txt = parts.get("body") or ""
            if quote != "off" and body_txt:
                chunk = wrap_quote(body_txt, quote)
            else:
                chunk = _apply_tpl(tpl.get("body") or "{body}", body_txt, ["body"])
        elif key == "result":
            rstyle = str(cfg.get("result_style") or "italic")
            chunk = style_result(parts.get("result") or "", rstyle)
        elif key == "hashtags":
            tags = parts.get("hashtags") or []
            joined = " ".join(tags)
            if tags and cfg.get("nexus_policy") and "{hashtags}" in (tpl.get("hashtags") or "{hashtags}") and "blockquote" not in (tpl.get("hashtags") or ""):
                chunk = f"<blockquote>💠 {joined}</blockquote>"
            else:
                chunk = _apply_tpl(tpl.get("hashtags") or "{hashtags}", joined, ["hashtags"], escape=False) if tags else ""
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
    return clip_html(sep.join(blocks), limit)

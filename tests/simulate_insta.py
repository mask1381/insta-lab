#!/usr/bin/env python3
"""Simulation harness for insta-lab. No network, no Telegram.

Tests the full delivery matrix:
 - evaluate() با skip_video
 - evaluate() با no_media
 - dry-run: schedule_send صدا زده نشود
 - dedup: پست تکراری skip شود
 - split_balanced: n=15 → [8,7]
 - caption.build_caption: برند + فوتر درست
 - caption.build_caption با only_tags
Run:  python tests/simulate_insta.py
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# ─── Recorders ───────────────────────────────────────────────────────────────
CALLS: list[dict] = []
FAILS: list[str] = []

def _rec(fn_name):
    def inner(*a, **k):
        CALLS.append({"what": fn_name, "args": list(a), "kwargs": k})
        return ["fake_id_1"]
    return inner

def _fail(label: str):
    FAILS.append(label)
    print(f"  FAIL {label}")

def _pass(label: str):
    print(f"  PASS {label}")

def check(label: str, cond: bool):
    if cond:
        _pass(label)
    else:
        _fail(label)

# ─── Mock network/Telegram ────────────────────────────────────────────────────
import insta_lab.sender as send_mod
send_mod.schedule_send = _rec("schedule_send")

import scripts.process_batch as pb_mod
pb_mod.say = lambda chat, text: True

from scripts.process_batch import AckSink

class MockSink(AckSink):
    def __init__(self):
        super().__init__("chat", "sim-batch-1")
    def _send(self, text): pass

# ─── Helpers ──────────────────────────────────────────────────────────────────
def clear():
    CALLS.clear()
    FAILS.clear()

def _make_post(shortcode="abc", has_media=True, has_video=False):
    media_items = []
    if has_media:
        if has_video:
            media_items.append({"url": "https://cdn.ig/v.mp4", "type": "video"})
        else:
            media_items.append({"url": "https://cdn.ig/p.jpg", "type": "photo"})
    return {
        "idx": 0,
        "shortcode": shortcode,
        "caption": "Hello #anime #art world",
        "media_items": media_items,
    }

# ─── Tests ───────────────────────────────────────────────────────────────────
def t_evaluate_no_media():
    print("[1] evaluate: no_media → not ready")
    from insta_lab.insta import evaluate
    res = evaluate(_make_post(has_media=False), {})
    check("ready=False", res["ready"] is False)
    check("skip=no_media", res.get("skip") == "no_media")

def t_evaluate_skip_video():
    print("[2] evaluate: skip_video=True + video → skipped")
    from insta_lab.insta import evaluate
    post = _make_post(has_video=True)
    res = evaluate(post, {"skip_video": True})
    check("ready=False for video", res["ready"] is False)
    check("skip=video", res.get("skip") == "video")

def t_evaluate_video_allowed():
    print("[3] evaluate: skip_video=False + video → ready")
    from insta_lab.insta import evaluate
    post = _make_post(has_video=True)
    res = evaluate(post, {"skip_video": False})
    check("ready=True when video allowed", res["ready"] is True)

def t_caption_basic():
    print("[4] caption: build_caption passthrough")
    import insta_lab.caption as cap
    cap.set_footer("")
    cap.set_brand_tag("")
    result = cap.build_caption("Hello #anime #art world")
    check("caption contains original text", "Hello" in result)
    check("caption length <= 1024", len(result) <= 1024)

def t_caption_only_tags():
    print("[5] caption: only_tags=True → فقط هشتگ")
    import insta_lab.caption as cap
    cap.set_footer("")
    cap.set_brand_tag("")
    result = cap.build_caption("Hello #anime #art world", only_tags=True)
    check("contains #anime", "#anime" in result)
    check("does not contain 'Hello'", "Hello" not in result)

def t_caption_brand_footer():
    print("[6] caption: brand_tag + footer اضافه می‌شوند")
    import insta_lab.caption as cap
    cap.set_brand_tag("MyChannel")
    cap.set_footer("🔗 t.me/mychannel")
    result = cap.build_caption("Test post #anime")
    check("brand tag present", "#MyChannel" in result)
    check("footer present", "t.me/mychannel" in result)
    check("length <= 1024", len(result) <= 1024)
    # reset
    cap.set_brand_tag("")
    cap.set_footer("")

def t_split_balanced():
    print("[7] split_balanced: 15 → [8, 7]")
    from insta_lab.sender import split_balanced
    result = split_balanced(list(range(15)))
    check("two chunks", len(result) == 2)
    check("first chunk = 8", len(result[0]) == 8)
    check("second chunk = 7", len(result[1]) == 7)

def t_split_balanced_small():
    print("[8] split_balanced: 5 → [5] (یک chunk)")
    from insta_lab.sender import split_balanced
    result = split_balanced(list(range(5)))
    check("one chunk for 5", len(result) == 1)
    check("chunk has 5", len(result[0]) == 5)

def t_split_balanced_empty():
    print("[9] split_balanced: empty → []")
    from insta_lab.sender import split_balanced
    result = split_balanced([])
    check("empty input → empty output", result == [])

def t_dry_run_no_send():
    print("[10] dry_run=True → schedule_send صدا زده نشود")
    clear()
    batch = {
        "posts": [_make_post("dry1")],
        "dry": True,
        "target_chat_id": "-100test",
        "post_rules": {},
    }
    sink = MockSink()
    from scripts.process_batch import run
    run(batch, sink)
    sends = [c for c in CALLS if c["what"] == "schedule_send"]
    check("no schedule_send in dry mode", len(sends) == 0)
    check("ack sent=1", sink.counts.get("sent", 0) == 1)

def t_dedup():
    print("[11] dedup: shortcode تکراری → skip")
    clear()
    batch = {
        "posts": [_make_post("dup1"), _make_post("dup1")],
        "dry": False,
        "sent": ["ig:dup1"],   # قبلاً فرستاده شده
        "target_chat_id": "-100test",
        "post_rules": {},
    }
    sink = MockSink()

    # mock materialize تا دانلود واقعی نشود
    import insta_lab.insta as insta_mod
    _orig_mat = insta_mod.materialize
    insta_mod.materialize = lambda post, rules, workdir: (["fake.jpg"], workdir)

    from scripts.process_batch import run
    run(batch, sink)
    insta_mod.materialize = _orig_mat

    sends = [c for c in CALLS if c["what"] == "schedule_send"]
    check("dup1 skipped (already in sent)", sink.counts.get("skipped", 0) >= 1)

def t_no_posts():
    print("[12] empty posts → return 0")
    clear()
    batch = {"posts": [], "dry": True, "target_chat_id": "-100test"}
    sink = MockSink()
    from scripts.process_batch import run
    rc = run(batch, sink)
    check("rc == 0", rc == 0)
    sends = [c for c in CALLS if c["what"] == "schedule_send"]
    check("no sends", len(sends) == 0)

# ─── Runner ───────────────────────────────────────────────────────────────────
def run_all():
    print("=" * 60)
    print("  insta-lab simulation harness")
    print("=" * 60)
    for fn in [
        t_evaluate_no_media, t_evaluate_skip_video, t_evaluate_video_allowed,
        t_caption_basic, t_caption_only_tags, t_caption_brand_footer,
        t_split_balanced, t_split_balanced_small, t_split_balanced_empty,
        t_dry_run_no_send, t_dedup, t_no_posts,
    ]:
        try:
            fn()
        except Exception as e:
            _fail(f"{fn.__name__} raised {type(e).__name__}: {e}")
        print()

    print("=" * 60)
    total = 12
    failed = len(FAILS)
    print(f"  Results: {total - failed}/{total} passed")
    if FAILS:
        print("  FAILED:", ", ".join(FAILS))
    print("=" * 60)
    return 1 if FAILS else 0

if __name__ == "__main__":
    sys.exit(run_all())

#!/usr/bin/env python3
"""یک batch از اینستا-ماشین را اجرا می‌کند.

ریپو عمومی است: stdout فقط شمارنده می‌گیرد؛ جزئیات به گروه خصوصی می‌رود.
با بات به این شکل حرف می‌زند (همان پروتکلِ ack که بات می‌فهمد):
  /ack <batch> <idx> <sent|skipped|failed> <code|-> <when|->
  /ack <batch> done
KIND و ACK_VERB دو شناسه‌ی ماشین‌اند (رجیستری بات از این ماشین انتظار دارد).
تمام قواعد پست (skip_video/crop/only_tags و...) از batch می‌آید — هیچ هویتی اینجا نیست.
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import time
from datetime import datetime, timezone

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))

LOG_BUF = io.StringIO()

KIND = "insta"
ACK_VERB = "ig"
SEND_GAP_SECONDS = 5.0   # فاصله‌ی واقعی بین دو پست
ACK_GAP = 1.2            # فاصله بین پیام‌های ack
LOG_TAIL = 3000


def log(msg: str) -> None:
    LOG_BUF.write(f"{datetime.now():%H:%M:%S} {msg}\n")


# ─────────────────────────────────────────
# تلگرام — اتصال باز برای هر عملیات
# ─────────────────────────────────────────
async def _connect():
    from telethon import TelegramClient
    from telethon.sessions import StringSession

    return TelegramClient(
        StringSession(os.environ["TG_SESSION_STRING"].strip()),
        int(os.environ["TG_API_ID"].strip()),
        os.environ["TG_API_HASH"].strip(),
    )


async def _resolve(client, chat_id):
    value = int(chat_id) if str(chat_id).lstrip("-").isdigit() else chat_id
    try:
        return await client.get_input_entity(value)
    except ValueError:
        await client.get_dialogs()
        return await client.get_input_entity(value)


async def _fetch_batch(chat_id, message_id):
    client = await _connect()
    try:
        await client.connect()
        entity = await _resolve(client, chat_id)
        msg = await client.get_messages(entity, ids=int(message_id))
        if not msg or not msg.media:
            raise RuntimeError("batch message not found")
        data = await client.download_media(msg, file=bytes)
        return json.loads(data.decode("utf-8"))
    finally:
        await client.disconnect()


async def _say(chat_id, text):
    client = await _connect()
    try:
        await client.connect()
        entity = await _resolve(client, chat_id)
        await client.send_message(entity, str(text)[:4000], parse_mode=None)
    finally:
        await client.disconnect()


def say(chat_id, text) -> bool:
    from telethon.errors import FloodWaitError

    for _ in range(3):
        try:
            asyncio.run(_say(chat_id, str(text)[:4000]))
            return True
        except FloodWaitError as e:
            time.sleep(min(e.seconds + 1, 60))
        except Exception as e:
            print(f"say failed: {type(e).__name__}")
            time.sleep(3)
    return False


# ─────────────────────────────────────────
# ack — همان قالبِ offline_sender که بات می‌فهمد
# ─────────────────────────────────────────
class AckSink:
    def __init__(self, chat, batch_id):
        self.chat = chat
        self.batch_id = batch_id
        self.counts = {"sent": 0, "skipped": 0, "failed": 0}
        self.aborted = False

    def ack(self, idx, status, code="-", when="-"):
        self.counts[status] += 1
        say(self.chat, f"/ack {self.batch_id} {idx} {status} {code or '-'} {when or '-'}")
        time.sleep(ACK_GAP)

    def sent_ids(self, item_ids: list) -> None:
        pass  # per-post ack ذیلِ همین قالب می‌رود؛ این برای سازگاریِ ذخیره است

    def blob(self, kind: str, data) -> None:
        raw = json.dumps(data, separators=(",", ":")).replace(" ", "\\u0020")
        for i in range(0, len(raw), 3000):
            say(self.chat, f"/ack {self.batch_id} blob {kind} {raw[i:i + 3000]}")
            time.sleep(ACK_GAP)


def fmt_when(dt) -> str:
    if not dt:
        return "now"
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%MZ")


# ─────────────────────────────────────────
# ارسال یک پست
# ─────────────────────────────────────────
def _run_quiet(fn, *args, **kwargs):
    """stdout/stderr گرفته می‌شود (ریپو عمومی)؛ -> (result, log, error)."""
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            return fn(*args, **kwargs), buf.getvalue(), None
    except KeyboardInterrupt:
        raise
    except BaseException as e:
        return None, buf.getvalue(), e


def make_when(now, idx, gap_min):
    """زمان ارسال این پست: now + idx*gap (اختیاری؛ gap_min از batch)."""
    if not gap_min:
        return None
    return now + __import__("datetime").timedelta(minutes=gap_min * (idx + 1))


def rules_for(batch: dict, post: dict) -> dict:
    """قواعد موتور < پروفایل پیج < قواعد خود پست."""
    r = dict(batch.get("post_rules") or {})
    profs = batch.get("profiles") or {}
    name = post.get("profile")
    if name and isinstance(profs.get(name), dict):
        p = profs[name]
        for k in ("skip_video", "only_tags", "crop_bottom_pct", "drop_first", "drop_last"):
            if p.get(k) is not None:
                r[k] = p[k]
    pr = post.get("rules")
    if isinstance(pr, dict):
        for k, v in pr.items():
            if v is not None:
                r[k] = v
    return r


def send_one(post, rules, target, when, workdir) -> tuple:
    """یک پست = ارزیابی + دانلود + ارسال. -> (status, code, real_when)."""
    from insta_lab.insta import evaluate, materialize
    from insta_lab.sender import schedule_send

    check = evaluate(post, rules)
    if not check["ready"]:
        return ("skipped", check.get("skip", "-"), None)

    from insta_lab.caption import build_caption
    caption = build_caption(post.get("caption") or "", only_tags=bool((rules or {}).get("only_tags")))

    packed = materialize(post, rules, workdir)
    # materialize لیست فایل برمی‌گرداند؛ تست‌ها گاهی (files, workdir) می‌دهند
    files = packed[0] if isinstance(packed, tuple) else packed
    if not files:
        return ("skipped", "no_media", None)
    if isinstance(files, (str, bytes)):
        files = [files]

    ids = schedule_send(target, files, caption, when)
    if not ids:
        return ("failed", "send", None)
    return ("sent", "-", when)


def post_key(post: dict) -> str:
    """شناسه‌ی یکتا برای dedup — shortcode به‌عنوان هویتِ پست (از batch)."""
    sc = post.get("shortcode") or post.get("id") or post.get("code")
    return f"ig:{sc}" if sc else ""


def run(batch: dict, sink: AckSink) -> int:
    from insta_lab import config
    from insta_lab.state import SentStore

    ref = config.env_config(batch)
    dry_run = bool(batch.get("dry"))
    target = ref["target_chat_id"]
    posts = batch.get("posts") or []
    send = batch.get("send") if isinstance(batch.get("send"), dict) else {}
    gap_min = int(send.get("gap_min") or batch.get("schedule_gap_min") or 0)

    if not target:
        raise RuntimeError("target_chat_id در batch ست نشده است")
    if not posts:
        log("هیچ پستی در batch نیست")
        return 0

    sent = SentStore(initial_ids=batch.get("sent"), sink=sink, dry_run=dry_run)

    now = datetime.now(timezone.utc)
    workdir = tempfile.mkdtemp(prefix="insta_")
    try:
        for idx, post in enumerate(posts):
            pos_idx = post.get("idx", idx)
            # dedup: shortcode قبلاً فرستاده‌شده = ردِ بی‌صدا (force از ارسال دستی رد می‌کند)
            key = post_key(post)
            if key and key in sent and not batch.get("force") and not post.get("force"):
                sink.ack(pos_idx, "skipped", "duplicate", "-")
                continue

            if dry_run:
                check = {"ready": True} if post.get("media_items") else {"ready": False, "skip": "no_media"}
                if check.get("ready"):
                    sink.ack(pos_idx, "sent", "-", "dry")
                else:
                    sink.ack(pos_idx, "skipped", check.get("skip"), "-")
                continue

            when = None
            if post.get("when"):
                try:
                    when = datetime.fromisoformat(str(post["when"]).replace("Z", "+00:00"))
                    if when.tzinfo is None:
                        when = when.replace(tzinfo=timezone.utc)
                except Exception:
                    when = make_when(now, idx, gap_min)
            else:
                when = make_when(now, idx, gap_min)
            try:
                status, code, real_when = send_one(post, rules_for(batch, post), target, when, workdir)
            except Exception as e:
                log(f"post {pos_idx} crashed: {type(e).__name__}: {e}")
                status, code, real_when = "failed", type(e).__name__[:40], None
            sink.ack(pos_idx, status, code, fmt_when(real_when))
            time.sleep(SEND_GAP_SECONDS if status == "sent" else 0.2)
            if status == "sent" and key:
                sent.add(key)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    sent.save()
    return 0


def main() -> int:
    sys.stdout.reconfigure(line_buffering=True)
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch-id", required=True)
    ap.add_argument("--message-id", required=True)
    args = ap.parse_args()

    for k in ("TG_API_ID", "TG_API_HASH", "TG_SESSION_STRING", "BATCH_CHAT_ID"):
        if not os.environ.get(k, "").strip():
            print(f"missing env: {k}")
            return 1
    chat = os.environ["BATCH_CHAT_ID"].strip()

    try:
        batch = asyncio.run(_fetch_batch(chat, args.message_id))
        if batch.get("batch_id") != args.batch_id or batch.get("kind") != KIND:
            raise RuntimeError("bad batch")
    except Exception as e:
        print(f"batch load failed: {type(e).__name__}")
        say(chat, f"❌ {args.batch_id} could not load: {type(e).__name__}: {str(e)[:300]}")
        return 1

    print(f"batch loaded: posts={len(batch.get('posts') or [])} dry={bool(batch.get('dry'))}")
    sink = AckSink(chat, args.batch_id)
    err = None
    try:
        rc = run(batch, sink)
    except BaseException as e:
        if isinstance(e, KeyboardInterrupt):
            raise
        err = e
        rc = 1

    if batch.get("dry") or err is not None:
        if err is not None:
            head = f"🧾 {args.batch_id} ❌ {type(err).__name__}: {str(err)[:300]}"
        else:
            head = f"🧾 {args.batch_id} (dry)"
        tail = LOG_BUF.getvalue()[-LOG_TAIL:]
        if tail:
            for i in range(0, len(tail), 3800):
                say(chat, f"{head}\n{tail[i:i + 3800]}")
                time.sleep(ACK_GAP)
    say(chat, f"/ack {args.batch_id} done")
    c = sink.counts
    print(f"finished: sent={c['sent']} skipped={c['skipped']} failed={c['failed']} "
          f"aborted={sink.aborted} error={type(err).__name__ if err else None}")
    return rc


if __name__ == "__main__":
    sys.exit(main())

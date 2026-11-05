"""
ارسال به تلگرام — اینستا-لَب (کانال-اگنوستیک).

- آلبوم‌های متوازن حداکثر ۱۰ فایل، کپشن روی اولِ هر آلبوم.
- زمان‌بندی با schedule (اختیاری) یا ارسالِ فوری (when=None).
- تلاش دوباره + مدیریت FloodWait.
"""

from __future__ import annotations

import asyncio
import io
import os
import time
from datetime import datetime, timedelta, timezone

from insta_lab import config


def _utc(when: datetime) -> datetime:
    if when.tzinfo is None:
        raise ValueError("schedule time must be timezone-aware")
    return when.astimezone(timezone.utc)


def _ids(res) -> list[int]:
    items = res if isinstance(res, (list, tuple)) else [res]
    return [int(m.id) for m in items if m is not None and getattr(m, "id", None) is not None]


def split_balanced(items: list, max_size: int = None) -> list:
    """۱۵ → ۸+۷ ، ۲۳ → ۸+8+7 ؛ دسته‌ی آخر تک‌افتاده نمی‌شود."""
    if not items:
        return []
    max_size = max_size or config.ALBUM_MAX
    n = len(items)
    parts = -(-n // max_size)          # ceil
    base, extra = divmod(n, parts)
    out, start = [], 0
    for i in range(parts):
        size = base + (1 if i < extra else 0)
        out.append(items[start:start + size])
        start += size
    return out


def _is_media(fp: str) -> bool:
    return fp.lower().endswith((".jpg", ".jpeg", ".png", ".mp4"))


async def _send(client, entity, files, caption, when):
    """ارسال یک آلبوم (<10) یا تک‌فایل؛ با caption روی پیام اول و schedule اختیاری."""
    if len(files) > 1:
        caps = [caption] + [""] * (len(files) - 1)
        return await client.send_file(entity, files, caption=caps, parse_mode="html",
                                      schedule=_utc(when) if when else None, supports_streaming=True)
    return await client.send_file(entity, files[0], caption=caption, parse_mode="html",
                                  schedule=_utc(when) if when else None, supports_streaming=True)


async def _send_scheduled(chat_id, files, caption, when) -> list[int]:
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    from telethon.errors import FloodWaitError

    client = TelegramClient(
        StringSession(config.TG_SESSION_STRING.strip()),
        int(config.TG_API_ID.strip()),
        config.TG_API_HASH.strip(),
    )
    await client.connect()
    try:
        entity_v = int(chat_id) if str(chat_id).lstrip("-").isdigit() else chat_id
        try:
            entity = await client.get_input_entity(entity_v)
        except ValueError:
            await client.get_dialogs()
            entity = await client.get_input_entity(entity_v)

        ids: list[int] = []
        albums = split_balanced(files)
        if not albums:
            return ids
        for i, batch_files in enumerate(albums):
            if i > 0:
                await asyncio.sleep(config.PAUSE_BETWEEN)
            try:
                res = await _send(client, entity, batch_files, caption,
                                  when + timedelta(minutes=i) if when else None)
            except FloodWaitError as e:
                await asyncio.sleep(min(e.seconds + 1, 300))
                res = await _send(client, entity, batch_files, caption,
                                  when + timedelta(minutes=i) if when else None)
            ids.extend(_ids(res))
        return ids
    finally:
        await client.disconnect()


def schedule_send(chat_id: str, files: list, caption: str, when: datetime | None = None) -> list[int]:
    """ارسال زمان‌بندی‌شده/فوری. when=None → همین‌الان. برمی‌گرداند message_id ها."""
    if not files:
        return []
    return asyncio.run(_send_scheduled(chat_id, files, caption, when))

"""متادیتای MP4 و نرمال‌سازی برای تلگرام (moov جلو + استریم صدا)."""
from __future__ import annotations

import logging
import os
import shutil
import struct
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)


def _which_ff() -> tuple[str | None, str | None]:
    return shutil.which("ffmpeg"), shutil.which("ffprobe")


def _read_box(f, end):
    start = f.tell()
    if start + 8 > end:
        return None
    hdr = f.read(8)
    if len(hdr) < 8:
        return None
    size, typ = struct.unpack(">I4s", hdr)
    if size == 1:
        wide = f.read(8)
        if len(wide) < 8:
            return None
        size = struct.unpack(">Q", wide)[0]
        hdr_len = 16
    elif size == 0:
        size = end - start
        hdr_len = 8
    else:
        hdr_len = 8
    if size < hdr_len:
        return None
    return start, size, typ, hdr_len


def _walk(f, start, end, wanted):
    f.seek(start)
    while f.tell() + 8 <= end:
        box = _read_box(f, end)
        if not box:
            break
        bstart, size, typ, hdr_len = box
        payload = bstart + hdr_len
        nxt = bstart + size
        if nxt > end or nxt <= bstart:
            break
        if typ in wanted:
            yield typ, payload, nxt
        if typ in (b"moov", b"trak", b"mdia", b"minf", b"stbl"):
            yield from _walk(f, payload, nxt, wanted)
        f.seek(nxt)


def inspect_mp4(path: str) -> dict:
    info = {"duration": 0.0, "w": 0, "h": 0, "has_audio": False, "ok": False}
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            for typ, payload, nxt in _walk(f, 0, size, {b"mvhd", b"tkhd", b"hdlr"}):
                f.seek(payload)
                data = f.read(max(0, nxt - payload))
                if typ == b"mvhd" and len(data) >= 20:
                    ver = data[0]
                    if ver == 1 and len(data) >= 32:
                        ts = struct.unpack(">I", data[20:24])[0]
                        dur = struct.unpack(">Q", data[24:32])[0]
                    else:
                        ts, dur = struct.unpack(">II", data[12:20])
                    if ts:
                        info["duration"] = dur / ts
                    info["ok"] = True
                elif typ == b"tkhd" and len(data) >= 84:
                    # width/height are 16.16 at end of tkhd
                    if data[0] == 1 and len(data) >= 96:
                        w, h = struct.unpack(">II", data[88:96])
                    elif len(data) >= 84:
                        w, h = struct.unpack(">II", data[76:84])
                    else:
                        w = h = 0
                    w, h = w >> 16, h >> 16
                    if w >= info["w"] and h >= info["h"] and w > 1 and h > 1:
                        info["w"], info["h"] = w, h
                elif typ == b"hdlr" and b"soun" in data:
                    info["has_audio"] = True
    except Exception as e:
        log.warning("inspect_mp4 failed %s: %s", path, e)
    return info


def ffprobe_info(path: str) -> dict | None:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    try:
        out = subprocess.check_output(
            [
                ffprobe, "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=width,height,duration:format=duration",
                "-of", "default=noprint_wrappers=1", path,
            ],
            text=True, timeout=30,
        )
        audio = subprocess.check_output(
            [ffprobe, "-v", "error", "-select_streams", "a", "-show_entries", "stream=codec_type",
             "-of", "csv=p=0", path],
            text=True, timeout=30,
        )
        meta = {"duration": 0.0, "w": 0, "h": 0, "has_audio": bool(audio.strip()), "ok": True}
        for line in out.splitlines():
            if "=" not in line:
                continue
            k, _, v = line.partition("=")
            if k in ("width", "height") and v.replace(".", "", 1).isdigit():
                meta["w" if k == "width" else "h"] = int(float(v))
            elif k == "duration":
                try:
                    meta["duration"] = float(v)
                except ValueError:
                    pass
        return meta
    except Exception as e:
        log.warning("ffprobe failed %s: %s", path, e)
        return None


def video_meta(path: str) -> dict:
    probed = ffprobe_info(path)
    if probed and (probed.get("w") or probed.get("duration")):
        return probed
    return inspect_mp4(path)


def normalize_video(path: str) -> str:
    """moov را جلو می‌آورد تا تلگرام duration/ابعاد/صدا را ببیند. بدون ffmpeg همان فایل."""
    if not path.lower().endswith(".mp4"):
        return path
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        log.warning("ffmpeg missing — sending raw mp4 (Telegram may drop audio/size)")
        return path
    out = str(Path(path).with_name(Path(path).stem + "_tg.mp4"))
    cmd = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-i", path, "-map", "0:v:0", "-map", "0:a?",
        "-c", "copy", "-movflags", "+faststart", out,
    ]
    try:
        subprocess.check_call(cmd, timeout=120)
        if os.path.getsize(out) > 1000:
            return out
    except Exception as e:
        log.warning("ffmpeg remux copy failed, trying aac: %s", e)
    cmd[-6:-2] = ["-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart"]
    # rebuild properly
    cmd = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-i", path, "-map", "0:v:0", "-map", "0:a?",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", out,
    ]
    try:
        subprocess.check_call(cmd, timeout=180)
        if os.path.getsize(out) > 1000:
            return out
    except Exception as e:
        log.error("ffmpeg normalize failed %s: %s", path, e)
    return path

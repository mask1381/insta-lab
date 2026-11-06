"""متادیتای MP4، صدا، کراپ، برش زمانی، و faststart برای تلگرام."""
from __future__ import annotations

import logging
import os
import shutil
import struct
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)


def ffmpeg_bin() -> str | None:
    return shutil.which("ffmpeg")


def ffprobe_bin() -> str | None:
    return shutil.which("ffprobe")


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
    ffprobe = ffprobe_bin()
    if not ffprobe:
        return None
    try:
        out = subprocess.check_output(
            [
                ffprobe, "-v", "error",
                "-show_entries", "stream=codec_type,width,height,duration:format=duration",
                "-of", "default=noprint_wrappers=1", path,
            ],
            text=True, timeout=30,
        )
        meta = {"duration": 0.0, "w": 0, "h": 0, "has_audio": False, "ok": True}
        for line in out.splitlines():
            if "=" not in line:
                continue
            k, _, v = line.partition("=")
            if k == "codec_type" and v.strip() == "audio":
                meta["has_audio"] = True
            elif k == "width" and v.replace(".", "", 1).isdigit():
                meta["w"] = int(float(v))
            elif k == "height" and v.replace(".", "", 1).isdigit():
                meta["h"] = int(float(v))
            elif k == "duration":
                try:
                    d = float(v)
                    if d > meta["duration"]:
                        meta["duration"] = d
                except ValueError:
                    pass
        return meta
    except Exception as e:
        log.warning("ffprobe failed %s: %s", path, e)
        return None


def video_meta(path: str) -> dict:
    probed = ffprobe_info(path)
    if probed and (probed.get("w") or probed.get("duration") or probed.get("has_audio")):
        return probed
    return inspect_mp4(path)


def crop_frac(pct) -> float:
    try:
        p = float(pct or 0)
    except (TypeError, ValueError):
        return 0.0
    if p > 1:
        p = p / 100.0
    if p <= 0 or p >= 0.45:
        return 0.0
    return p


def _run_ff(cmd: list, timeout: int = 180) -> bool:
    try:
        subprocess.check_call(cmd, timeout=timeout)
        return True
    except Exception as e:
        log.warning("ffmpeg failed: %s", e)
        return False


def prepare_video(
    path: str,
    *,
    crop_bottom_pct: float = 0,
    trim_start_sec: float = 0,
    trim_end_sec: float = 0,
    audio_path: str | None = None,
) -> str:
    """ویدیوی اینستا را برای تلگرام آماده می‌کند: صدا، moov جلو، کراپ پایین، برش زمانی.

    اینستا اغلب mp4 تکه‌تکه/بدون moov جلو می‌دهد؛ تلگرام آن را 1×1 و بی‌صدا پخش می‌کند.
    اگر Apify فقط ویدیوی DASH بدون صدا داده باشد، audio_path جدا mux می‌شود.
    """
    if not str(path).lower().endswith((".mp4", ".mov", ".webm", ".m4v")):
        return path
    ffmpeg = ffmpeg_bin()
    if not ffmpeg:
        log.warning("ffmpeg missing — Telegram may drop audio")
        return path

    start = max(0.0, float(trim_start_sec or 0))
    end_cut = max(0.0, float(trim_end_sec or 0))
    frac = crop_frac(crop_bottom_pct)
    meta = video_meta(path)
    dur = float(meta.get("duration") or 0)
    keep = None
    if dur > 0:
        keep = max(0.2, dur - start - end_cut)
        if keep >= dur - 0.05 and start <= 0:
            keep = None

    need_filter = frac > 0 or start > 0 or end_cut > 0 or audio_path
    out = str(Path(path).with_name(Path(path).stem + "_tg.mp4"))
    cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error"]
    if start > 0:
        cmd += ["-ss", f"{start:.3f}"]
    cmd += ["-i", path]
    if audio_path and os.path.isfile(audio_path):
        if start > 0:
            cmd += ["-ss", f"{start:.3f}"]
        cmd += ["-i", audio_path]
    if keep:
        cmd += ["-t", f"{keep:.3f}"]

    vf = []
    if frac > 0:
        vf.append(f"crop=iw:ih*(1-{frac:.4f}):0:0")
        vf.append("scale=trunc(iw/2)*2:trunc(ih/2)*2")
    maps = ["-map", "0:v:0"]
    if audio_path and os.path.isfile(audio_path):
        maps += ["-map", "1:a:0?"]
    else:
        maps += ["-map", "0:a:0?"]

    if vf or audio_path or need_filter:
        cmd += maps
        if vf:
            cmd += ["-vf", ",".join(vf), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20"]
        else:
            cmd += ["-c:v", "copy"]
        cmd += ["-c:a", "aac", "-b:a", "160k", "-ac", "2", "-ar", "44100", "-movflags", "+faststart", out]
        if _run_ff(cmd, timeout=240) and os.path.getsize(out) > 1000:
            got = video_meta(out)
            if got.get("has_audio"):
                return out
            log.warning("prepared video still has no audio: %s", out)

    # remux + faststart: ویدیوی اینستا اغلب moov ته فایل دارد و تلگرام آن را 1×1 بی‌صدا می‌فرستد
    for extra in (
        ["-c", "copy", "-movflags", "+faststart", out],
        ["-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out],
    ):
        cmd = [
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-i", path, "-map", "0:v:0", "-map", "0:a:0?",
            *extra,
        ]
        if _run_ff(cmd, timeout=180) and os.path.getsize(out) > 1000 and video_meta(out).get("has_audio"):
            return out

    src = out if os.path.isfile(out) and os.path.getsize(out) > 1000 else path
    silent_out = str(Path(path).with_name(Path(path).stem + "_tga.mp4"))
    cmd = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-i", src,
        "-f", "lavfi", "-t", "3600", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy", "-c:a", "aac", "-shortest", "-movflags", "+faststart", silent_out,
    ]
    if _run_ff(cmd, timeout=180) and os.path.getsize(silent_out) > 1000:
        return silent_out
    log.error("prepare_video failed, sending raw %s", path)
    return path


def normalize_video(path: str) -> str:
    return prepare_video(path)

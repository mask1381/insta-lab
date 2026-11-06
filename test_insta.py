"""تستِ آفلاینِ Insta Lab — بدون توکن، بدون تلگرام، بدون شبکه.
اجرا:  python test_insta.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from insta_lab import caption, config
from insta_lab.sender import split_balanced
from insta_lab.insta import evaluate, prepare
from scripts.process_batch import post_key

failures = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  {detail}" if detail and not cond else ""))
    if not cond:
        failures.append(name)


def test_caption():
    caption.set_caption_cfg({})
    caption.set_footer("")
    caption.set_brand_tag("")
    out = caption.build_caption("hello #art #good")
    assert out == "hello #art #good", repr(out)
    # فقط هشتگ
    out2 = caption.build_caption("hello #art #good", only_tags=True)
    assert out2 == "#art #good", repr(out2)
    # سقف ۱۰۲۴ + برند + فوتر
    caption.set_brand_tag("Wall")
    caption.set_footer("FOOTER")
    out3 = caption.build_caption("#" + "X" * 1200)
    assert len(out3) <= caption.config.MAX_TG_CAPTION_LEN if hasattr(caption, "config") else True
    assert out3.endswith("FOOTER")
    assert "#Wall" in out3
    caption.set_brand_tag("")
    caption.set_footer("")
    print("test_caption OK")


def test_split_balanced():
    assert [len(x) for x in split_balanced(list(range(15)))] == [8, 7]
    assert [len(x) for x in split_balanced(list(range(23)))] == [8, 8, 7]
    assert [len(x) for x in split_balanced(list(range(3)))] == [3]
    assert split_balanced([]) == []
    print("test_split_balanced OK")


def test_evaluate():
    # بدون رسانه = رد
    assert evaluate({"media_items": []})["skip"] == "no_media"
    # ویدئو وقتی skip_video=True = رد
    assert evaluate({"media_items": [{"url": "u", "type": "video"}]}, {"skip_video": True})["skip"] == "video"
    # عکس = آماده
    assert evaluate({"media_items": [{"url": "u", "type": "photo"}]})["ready"] is True
    # prepare کپشن می‌سازد
    cap = prepare({"caption": "c #t", "media_items": [{"url": "u", "type": "photo"}]})
    assert cap["ready"] and "c #t" in cap["caption"]
    print("test_evaluate OK")


def test_post_key():
    assert post_key({"shortcode": "abc"}) == "ig:abc"
    assert post_key({"id": "xyz"}) == "ig:xyz"
    assert post_key({}) == ""
    print("test_post_key OK")


def test_caption_layout_and_ads():
    caption.set_brand_tag("")
    caption.set_footer("TREE")
    caption.set_caption_cfg({
        "layout": ["title", "body", "result", "hashtags", "brand", "footer"],
        "short_layout": ["title", "hashtags", "footer"],
        "short_mode": "as_is",
        "short_min": 80,
        "split": "lines",
        "tags": "keep",
        "joiner": "nlnl",
        "templates": {"title": "<b>{title}</b>", "body": "{body}", "result": "<i>{result}</i>", "hashtags": "{hashtags}"},
        "extras": {},
        "ad_detect": {"enabled": True, "patterns": ["giveaway", "buy now"]},
        "strip": [],
    })
    short = caption.build_caption("OH MY GOD\n\n#WutheringWaves")
    assert "OH MY GOD" in short and "TREE" in short and "#WutheringWaves" in short
    long = caption.build_caption("Lily is cute\n\nA long essay about the livestream that goes on and on about Shorekeeper and the community reaction to the story.\n\n#WutheringWaves")
    assert "<b>Lily is cute</b>" in long
    assert caption.is_ad_text("Create a stage for a chance to win giveaway tickets")
    assert not caption.is_ad_text("3.8 BANNERS\n\n#WutheringWaves")
    caption.set_caption_cfg({})
    caption.set_footer("")
    print("test_caption_layout_and_ads OK")


def test_crop_skips_video():
    from insta_lab.media import crop_bottom_pct
    from insta_lab.mp4 import crop_frac
    assert crop_bottom_pct("x.mp4", 0.2) == "x.mp4"
    assert crop_frac(10) == 0.1
    assert crop_frac(0.2) == 0.2
    assert crop_frac(0) == 0
    print("test_crop_skips_video OK")


def test_prepare_video_ffmpeg():
    import shutil, subprocess, tempfile
    from pathlib import Path
    from insta_lab.mp4 import prepare_video, video_meta, ffmpeg_bin
    ff = ffmpeg_bin()
    if not ff:
        print("test_prepare_video_ffmpeg SKIP (no ffmpeg)")
        return
    d = Path(tempfile.mkdtemp())
    vo = d / "vo.mp4"
    wa = d / "wa.mp4"
    au = d / "a.aac"
    subprocess.check_call([
        ff, "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "testsrc=size=320x240:rate=10", "-t", "3",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", str(vo),
    ])
    subprocess.check_call([
        ff, "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100", "-t", "3",
        "-c:a", "aac", str(au),
    ])
    subprocess.check_call([
        ff, "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "testsrc=size=640x360:rate=10",
        "-f", "lavfi", "-i", "sine=frequency=330:sample_rate=44100",
        "-t", "4", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
        "-shortest", str(wa),
    ])
    silent = Path(prepare_video(str(vo)))
    muxed = Path(prepare_video(str(vo), audio_path=str(au)))
    cropped = Path(prepare_video(str(wa), crop_bottom_pct=10, trim_start_sec=0.5, trim_end_sec=0.5))
    ms, mm, mc = video_meta(str(silent)), video_meta(str(muxed)), video_meta(str(cropped))
    assert ms.get("has_audio"), ms
    assert mm.get("has_audio"), mm
    assert mc.get("has_audio"), mc
    assert mc.get("h") and mc["h"] < 360, mc
    assert 2.0 <= float(mc.get("duration") or 0) <= 3.6, mc
    print("test_prepare_video_ffmpeg OK")


def test_env_config():
    config.env_config({
        "branch": "Chan", "target_chat_id": "123",
        "footer_html": "F", "brand_tag": "B",
    })
    assert config.get_branch() == "Chan"
    assert config.TG_CHAT_ID == "123"
    assert caption.get_brand_tag() == "B"
    print("test_env_config OK")


if __name__ == "__main__":
    test_caption()
    test_caption_layout_and_ads()
    test_split_balanced()
    test_evaluate()
    test_post_key()
    test_crop_skips_video()
    test_prepare_video_ffmpeg()
    test_env_config()
    print()
    print("ALL TESTS PASSED") if not failures else print(f"{len(failures)} FAILURE(S): {failures}")
    sys.exit(1 if failures else 0)

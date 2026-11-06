"""تستِ آفلاینِ Insta Lab — بدون توکن، بدون تلگرام، بدون شبکه.
اجرا:  python test_insta.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from insta_lab import caption, config
from insta_lab.sender import split_balanced
from insta_lab.insta import evaluate, prepare, apply_media_drops
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


def test_hub_shape():
    from insta_lab.caption import shape_hub_caption, set_caption_cfg, set_footer, build_caption
    pack = {
        "games": [{"tag": "GenshinImpact", "keys": ["genshinimpact", "genshin"]}, {"tag": "WutheringWaves", "keys": ["wutheringwaves", "wuwa"]}],
        "names": [{"tag": "Anastasya", "keys": ["anastasya", "tsaritsa"]}, {"tag": "Mitya", "keys": ["mitya"]}],
    }
    leak = shape_hub_caption(
        "ANASTASYA FREEZING\n\nVia Seele\n\n#genshinimpact #hoyoverse #tsaritsa #danica",
        topic_mode="leak", pack=pack,
    )
    assert "#Leak" in leak and "#GenshinImpact" in leak and "#Anastasya" in leak, leak
    assert "#hoyoverse" not in leak.lower() and "#Danica" not in leak
    no_via = shape_hub_caption("LILY GACHA ANIMATION\n#WutheringWaves", topic_mode="leak", pack=pack)
    assert "#Leak" not in no_via, no_via
    missing = shape_hub_caption("ANASTASYA FREEZING\nVia Seele\n#genshinimpact", topic_mode="leak", pack={"games": pack["games"], "names": []})
    assert "#Anastasya" not in missing
    official = shape_hub_caption(
        "Version 3.8 Livestream Recap\nSource: Wuthering Waves Official\n✦ Status\n#WutheringWaves",
        topic_mode="official", pack=pack,
    )
    assert "#News" in official and "#Leak" not in official, official
    clip = shape_hub_caption("Mitya extract 1\n#Clip #GenshinImpact #Mitya", pack=pack)
    assert "#Clip" in clip and "#Mitya" in clip
    set_caption_cfg({
        "hub_policy": True,
        "hub_tags": pack,
        "layout": ["title", "body", "result", "hashtags", "footer"],
        "title_font": "u_italic",
        "body_quote": "quote",
        "result_style": "italic",
        "joiner": "nlnl",
        "tags": "extract",
    })
    set_footer("FOOTER")
    out = build_caption("LILY GACHA ANIMATION\n#WutheringWaves #wuwa #kurogames", rules={"topic_mode": "auto"})
    assert out.endswith("FOOTER") and "#WutheringWaves" in out and "#kurogames" not in out.lower()
    assert "#Lily" not in out
    assert "𝐿𝐼𝐿𝑌" in out or "\U0001d441" in out
    news = build_caption(
        "Version 3.8 Livestream Recap\nRead Full Article: https://x.com/a\n#WutheringWaves",
        rules={"topic_mode": "official"},
    )
    assert "<i>Read Full Article:" in news and news.count("Read Full Article") == 1
    leak_html = build_caption("ANASTASYA FREEZING\nVia Seele\n#genshinimpact", rules={"topic_mode": "leak"})
    assert "<blockquote>Via Seele</blockquote>" in leak_html
    assert "#Leak" in leak_html
    set_caption_cfg({})
    set_footer("")
    print("test_hub_shape OK")


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
    cropped = Path(prepare_video(str(wa), crop_side="both", crop_pct=10, trim_start_sec=0.5, trim_end_sec=0.5))
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


def test_nexus_profile():
    caption.set_footer("THE LABS")
    caption.set_caption_cfg({
        "nexus_policy": True,
        "layout": ["title", "body", "result", "hashtags", "footer"],
        "title_font": "bold",
        "body_quote": "expand",
        "result_style": "italic",
        "joiner": "nlnl",
        "tags": "extract",
    })
    rules = {
        "nfkc": True,
        "split_title": True,
        "tags_from_field": r"^[ \t]*anime[ \t]*:[ \t]*(.+)$",
        "result_field": r"^[ \t]*song[ \t]*:",
        "skip_if_all_cjk": True,
        "skip_if_caption_matches": [r"BEST ANIME TO WATCH FOR BEGINNERS"],
    }
    raw = "Peak Romance anime moment\nPlot: Kyoko Hori is perfect.\nAnime: Horimiya\nSong: Winter Wonderland\n#RomanceAnime #AnimeCouple"
    out = caption.build_caption(raw, rules=rules)
    assert "<b>Peak Romance anime moment</b>" in out, out
    assert "<blockquote expandable>" in out and "Kyoko Hori" in out, out
    assert "<i>Song: Winter Wonderland</i>" in out, out
    assert "#Horimiya" in out and "#RomanceAnime" not in out, out
    assert "THE LABS" in out
    jp = "日本語だけのキャプション です"
    assert evaluate({"caption": jp, "media_items": [{"url": "u", "type": "photo"}]}, rules)["skip"] == "cjk"
    spam = "BEST ANIME TO WATCH FOR BEGINNERS\nTVアニメ"
    assert evaluate({"caption": spam, "media_items": [{"url": "u", "type": "photo"}]}, rules)["skip"] == "caption_match"
    items = apply_media_drops([{"u": 1}, {"u": 2}, {"u": 3}, {"u": 4}], {"drop_first": 1, "drop_last": 1})
    assert [x["u"] for x in items] == [2, 3]
    news = caption.build_caption(
        "Mushoku Tensei takes 1\n• It beat Re:Zero.\nFollow for more @24hranimenews\nMushokuTenseiJoblessReincarnation ReZero LightNovels AnimeNews",
        rules={"split_title": True, "own_hashtags": True, "blocked_patterns": [r"animenews$"]},
    )
    assert "<b>Mushoku Tensei takes 1</b>" in news, news
    assert "Follow" not in news and "@24hranimenews" not in news, news
    assert "#MushokuTenseiJoblessReincarnation" in news and "#ReZero" in news, news
    assert "AnimeNews" not in news.replace("THE LABS", "")
    amv = caption.build_caption(
        "He's so crazy\nAnime Details ✨:\nFirefly Wedding is an anime.\n#hotarunoyomeiri #fireflywedding #animeedit",
        rules={"split_title": True, "own_hashtags": True, "extra_hashtags": ["AMV"], "blocked_hashtags": ["anime", "animeedit", "edit"], "blocked_patterns": ["edit$"]},
    )
    typo = caption.build_caption(
        "Senju is here\nAnime Depscrition ✨:\nTokyo Revengers is an anime.\n#tokyorevengers",
        rules={"split_title": True, "own_hashtags": True},
    )
    assert "Senju is here" in typo and "Depscrition" not in typo, typo
    assert "Tokyo Revengers is an anime." in typo
    yami = caption.build_caption(
        "Remember when Captain Yami casually lifted Dante in his FULL BODY DEVIL TRANSFORMATION? Bro was facing a devil-powered monster.\nDante had 100% devil power.\n#blackclover #yami",
        rules={"raw_caption": True, "split_title": True, "own_hashtags": True},
    )
    assert "<b>Remember when Captain Yami" in yami, yami
    assert "DEVIL TRANSFORMATION?" in yami
    assert "Bro was facing" in yami
    assert yami.find("Bro was facing") > yami.find("</b>"), yami
    assert "so crazy" in amv and "Anime Details" not in amv, amv
    assert "Firefly Wedding is an anime." in amv, amv
    assert "#AMV" in amv and "#hotarunoyomeiri" in amv and "#animeedit" not in amv.lower()
    caption.set_caption_cfg({})
    caption.set_footer("")
    print("test_nexus_profile OK")


if __name__ == "__main__":
    test_caption()
    test_caption_layout_and_ads()
    test_split_balanced()
    test_evaluate()
    test_post_key()
    test_crop_skips_video()
    test_hub_shape()
    test_nexus_profile()
    test_prepare_video_ffmpeg()
    test_env_config()
    print()
    print("ALL TESTS PASSED") if not failures else print(f"{len(failures)} FAILURE(S): {failures}")
    sys.exit(1 if failures else 0)

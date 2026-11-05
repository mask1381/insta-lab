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
    test_split_balanced()
    test_evaluate()
    test_post_key()
    test_env_config()
    print()
    print("ALL TESTS PASSED") if not failures else print(f"{len(failures)} FAILURE(S): {failures}")
    sys.exit(1 if failures else 0)

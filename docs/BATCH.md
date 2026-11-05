# BATCH.md — قراردادِ batch برای ماشینِ insta

این ریپو **عمومی** است. هیچ هویت کانال (برند/یوزرنیم/CTA/لینک) در کد نیست؛
همه‌چیز در batch می‌آید. این سند «تک‌منبعِ چیزی‌ست که بات می‌فرستد».

## ۱) شناسه‌ها

```
batch["kind"]  == "insta"              # ثابت KIND در scripts/process_batch.py
ack: /ack <batch_id> <idx> <status>...  # پروتکل ack (بخش ۵)
```

> منبعِ این ماشین «اینستاگرام» است. کانال‌ها اسم ماشین نیستند.
> پست‌ها داخل خودِ batch می‌آیند (بیرون‌رفتنیِ Apify : لینک‌های CDN).

## ۲) فیلدهای پایه

| فیلد | نوع | یعنی چه |
|---|---|---|
| `batch_id` | str | شناسه‌ی batch (در ack ها برمی‌گردد) |
| `kind` | str | باید `insta` باشد |
| `dry` | bool | فقط برنامه + کپشن + لاگ؛ هیچ ارسالی/تغییری |
| `branch` | str | نام گره‌ی این اجرا (اختیاری) |
| `target_chat_id` | str/int | کانال مقصد ارسال (الزامی) |
| `footer_html` | str | فوتر کپشن (اختیاری) |
| `brand_tag` | str | برندتگ انتهای هشتگ‌ها (اختیاری) |
| `sent` | list[str] | شناسه‌های ارسال‌شده‌ی قبلی (برای dedup) |
| `posts` | list[dict] | پست‌های اینستاگرام — هر پست پایین تعریف می‌شود |
| `post_rules` | dict | قواعد پردازشِ مشترک همه‌ی پست‌ها |
| `schedule_gap_min` | int | فاصله‌ی دقیقه از now برای ارسال پست‌ها (بدون = فوری) |

## ۳) هر پست (`posts[]`)

| فیلد | نوع | یعنی چه |
|---|---|---|
| `idx` | int | شماره‌ی پست (در ack ها برمی‌گردد) — اختیاری، وگرنه ترتیبِ حلقه |
| `shortcode` | str | کد پست اینستاگرام (هویتِ dedup — `ig:<shortcode>`) |
| `caption` | str | کپشن اصلیِ پست (دست‌نخورده، بریده تا سقف) |
| `media_items` | list[dict] | هر مورد: `{"url": "...", "type": "photo"|"video"}` (لینک CDN) |

## ۴) قواعد پردازش (`post_rules`)

همه‌ی پست‌ها با یک `post_rules` مشترک پردازش می‌شوند (مخصوص کانال نیست):

| کلید | پیش‌فرض | یعنی چه |
|---|---|---|
| `skip_video` | false | پست‌های ویدیویی نادیده گرفته شوند |
| `only_tags` | false | کپشن فقط هشتگ‌های داخل پست، بدون متن |
| `crop_bottom_pct` | 0 | برشِ پایینِ هر عکس (۰ تا ۱) — مثلاً ۰.۱۵ |

## ۵) ack به گروه

```
/ack <batch_id> <idx> sent     <->   <when>        ارسال شد (when = schedule یا now)
/ack <batch_id> <idx> skipped  <code> <->           رد شد (no_media/video/duplicate/rule)
/ack <batch_id> <idx> failed   <err>  <->           ارسال ناموفق (دانلود/فلاود)
/ack <batch_id> done                                   پایانِ قابل‌اعتماد
```

- `when` به‌صورت UTC: `YYYYMMDDTHHMMZ` یا `now` (اگر فوری).
- dedup: shortcodeِ قبلاً اعلام‌شده در `sent` → `skipped duplicate` بدون دانلود.
- dry-run: هر پست آماده، ack «sent» با when="dry" می‌گیرد؛ لاگ به گروه می‌رود؛ هیچ‌چیز ارسال نمی‌شود.

## ۶) قرارداد کپشن

کپشن = کپشنِ اصلیِ پست (یا فقط هشتگ‌هایش) + (اختیاری) برندتگ + فوتر.
سقف ۱۰۲۴ کاراکتر؛ اگر اصلی‌تر باشد، **بدنه** بریده می‌شود تا جا برای برند/فوتر —
برند/فوتر هرگز بریده نمی‌شوند. واژگان فقط از batch و data عمومی.

## ۷) اسرار (Secrets)

فقط در env/GitHub Actions: `TG_API_ID`, `TG_API_HASH`, `TG_SESSION_STRING`, `BATCH_CHAT_ID` (الزامی)؛
`IG_PROXY_URL`, `CURL_CFFI_IMPERSONATE`, `IG_COOKIE` (اختیاری). هیچ‌کدام در batch نیست.

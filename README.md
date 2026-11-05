# Insta Lab — ماشینِ اینستاگرام

ماشینِ کانال-اگنوستیک برای ارسالِ پست‌های اینستاگرام (از batch) به کانالِ تلگرام.

- **هیچ** نام کانال/برند/CTA/لینک در این ریپو (عمومی) نیست — همه از batch می‌آید.
- پست‌ها داخل batch: `media_items` (لینک CDN) + کپشن اصلی + shortcode.
- دانلودِ مستقیم CDN با سشنِ سخت‌شده (curl_cffi) — بدون لاگین، بدون instaloader.
- کپشن = اصلی (یا فقط هشتگ) + برند + فوتر (از batch)، همیشه ≤۱۰۲۴ و برند/فوتر محفوظ.
- ack به گروه: `/ack <batch> <idx> <sent|skipped|failed> <code> <when>` + `/ack <batch> done`.

اجرا:  `scripts/process_batch.py --batch-id … --message-id …` (توسط GitHub Actions)؛
تست آفلاین:  `python test_insta.py` — بدون توکن/شبکه.

قرارداد کامل batch در [docs/BATCH.md](docs/BATCH.md).

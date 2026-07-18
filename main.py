"""
آرامکس۲۴ — تولید و انتشار خودکار روزانه مقاله (نسخه GitHub Actions)
======================================================================
برخلاف نسخه قبلی (سرور دائمی + APScheduler)، این نسخه یک‌بار اجرا می‌شود
و خارج می‌شود. زمان‌بندی روزانه را خود GitHub Actions (cron) انجام می‌دهد.

مراحل هر اجرا:
  1) خواندن state.json برای فهمیدن کلمه کلیدی نوبت امروز
  2) ساخت مقاله کامل با Claude API
  3) انتشار مستقیم در وردپرس (status=publish)
  4) اطلاع‌رسانی به تلگرام
  5) ذخیره state.json به‌روزشده (workflow آن را دوباره commit می‌کند)

در صورت بروز خطا، کد خروجی غیرصفر برمی‌گرداند تا در تب Actions گیت‌هاب
به‌صورت ❌ قرمز دیده شود، و همچنین پیام خطا به تلگرام ارسال می‌شود.
"""

import os
import sys
import json
import re
import logging
from datetime import datetime, timezone

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()  # فقط برای اجرای محلی؛ در GitHub Actions فایل .env وجود ندارد و بی‌اثر است
except ImportError:
    pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("aramax24-publisher")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE_DIR, "state.json")
KEYWORDS_FILE = os.path.join(BASE_DIR, "keywords.json")


def env(name, required=True, default=None):
    val = os.environ.get(name, default)
    if required and not val:
        raise RuntimeError(f"متغیر محیطی {name} تنظیم نشده است (باید در GitHub Secrets اضافه شود).")
    return val


ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY")
TELEGRAM_BOT_TOKEN = env("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = env("TELEGRAM_CHAT_ID")
WP_BASE_URL = env("WP_BASE_URL").rstrip("/")
WP_USERNAME = env("WP_USERNAME")
WP_APP_PASSWORD = env("WP_APP_PASSWORD")
MODEL_NAME = os.environ.get("CLAUDE_MODEL") or "claude-sonnet-5"


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def send_telegram(text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(
            url,
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            },
            timeout=15,
        )
        r.raise_for_status()
    except Exception as e:
        log.error(f"ارسال پیام تلگرام ناموفق بود: {e}")


def pick_today_keyword():
    keywords = load_json(KEYWORDS_FILE, [])
    if not keywords:
        raise RuntimeError("فایل keywords.json خالی است یا پیدا نشد.")

    state = load_json(STATE_FILE, {"day_index": 0})
    idx = state["day_index"] % len(keywords)
    item = keywords[idx]

    state["day_index"] = idx + 1
    save_json(STATE_FILE, state)
    return item


def build_prompt(item: dict) -> str:
    return f"""تو یک متخصص سئوی فارسی و تولید محتوا برای سایت خدمات تعمیرات ساختمان و تأسیسات
(aramax24.ir) در غرب تهران هستی.

یک مقاله وبلاگ کامل، حرفه‌ای و آماده انتشار فوری برای کلمه کلیدی زیر بنویس. این محتوا
مستقیم و بدون بازبینی انسانی منتشر می‌شود، پس نباید هیچ placeholder یا متن ناقص داشته باشد.

کلمه کلیدی: {item['keyword']}
دسته‌بندی سایت: {item['category']}
لینک داخلی که باید با anchor text طبیعی حداقل یک‌بار در متن استفاده شود: {item['related_link']}
لینک آرشیو دسته‌بندی (در صورت وجود و متفاوت از placeholder، حتماً هم به این لینک بده): {item.get('category_archive_link', '')}

الزامات محتوا:
- مقدمه، فهرست مطالب، حداقل ۴ تا ۶ زیرعنوان H2/H3، جدول در صورت لزوم، جمع‌بندی
- ۵ تا ۶ سوال متداول (FAQ) در پایان
- طول حدود ۱۲۰۰ تا ۱۸۰۰ کلمه، لحن حرفه‌ای و قابل‌فهم
- **هیچ قیمت یا رقم دقیقی حدس نزن و ننویس.** به‌جای جدول قیمت با اعداد، بنویس که
  «هزینه بسته به نوع خرابی و مدل دستگاه متفاوت است؛ برای برآورد دقیق با کارشناسان
  آرامکس۲۴ تماس بگیرید» و لینک تماس با ما را بگذار: https://aramax24.ir/contact-us/
- Meta Title زیر ۶۰ کاراکتر، Meta Description زیر ۱۵۵ کاراکتر
- اسکیمای JSON-LD کامل از نوع Article و FAQPage با تاریخ امروز ({datetime.now().strftime('%Y-%m-%d')})

خروجی را دقیقاً و فقط به‌صورت یک JSON با این ساختار بده، بدون هیچ متن اضافه قبل یا بعدش:
{{
  "title": "...",
  "slug": "...",
  "meta_title": "...",
  "meta_description": "...",
  "content_html": "<h2>...</h2><p>...</p> ... (بدنه کامل مقاله به HTML، شامل FAQ)",
  "schema_jsonld": {{ ... }}
}}"""


def generate_article(item: dict) -> dict:
    log.info(f"در حال ساخت مقاله برای کلمه کلیدی: {item['keyword']}")
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": MODEL_NAME,
            "max_tokens": 8000,
            "messages": [{"role": "user", "content": build_prompt(item)}],
        },
        timeout=280,
    )
if resp.status_code >= 400:
        log.error(f"پاسخ خطای Anthropic: {resp.text}")
    resp.raise_for_status()
    data = resp.json()

    text_block = next(b for b in data["content"] if b["type"] == "text")
    raw = text_block["text"]

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", raw)
        if not match:
            raise RuntimeError("خروجی Claude به‌صورت JSON قابل‌پارس نبود.")
        return json.loads(match.group(0))


def publish_to_wordpress(article: dict) -> str:
    schema_script = (
        f'<script type="application/ld+json">'
        f'{json.dumps(article["schema_jsonld"], ensure_ascii=False)}</script>'
    )
    full_content = article["content_html"] + "\n" + schema_script

    resp = requests.post(
        f"{WP_BASE_URL}/wp-json/wp/v2/posts",
        auth=(WP_USERNAME, WP_APP_PASSWORD),
        json={
            "title": article["title"],
            "slug": article["slug"],
            "content": full_content,
            "status": "publish",
            "excerpt": article.get("meta_description", ""),
        },
        timeout=60,
    )
    resp.raise_for_status()
    post = resp.json()
    return post.get("link", f"{WP_BASE_URL}/?p={post.get('id')}")


def main():
    now = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")
    try:
        item = pick_today_keyword()
        article = generate_article(item)
        link = publish_to_wordpress(article)

        send_telegram(
            f"✅ <b>مقاله جدید منتشر شد</b>\n"
            f"🕘 {now}\n"
            f"📂 دسته: {item['category']}\n"
            f"📝 عنوان: {article['title']}\n"
            f"🔗 {link}"
        )
        log.info(f"مقاله با موفقیت منتشر شد: {link}")
        return 0

    except Exception as e:
        log.exception("خطا در فرآیند روزانه")
        send_telegram(
            f"❌ <b>خطا در تولید/انتشار مقاله روزانه</b>\n"
            f"🕘 {now}\n"
            f"جزئیات: {str(e)[:500]}\n\n"
            f"لطفاً لاگ اجرای Action در گیت‌هاب را بررسی کنید."
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())

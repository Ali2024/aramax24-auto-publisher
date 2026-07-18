"""
Aramax24 Auto Publisher
Version 2.0
NVIDIA Build + WordPress + Telegram
"""

import os
import re
import json
import time
import logging
from datetime import datetime, timezone

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from openai import OpenAI

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

log = logging.getLogger("aramax24")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

STATE_FILE = os.path.join(BASE_DIR, "state.json")
KEYWORDS_FILE = os.path.join(BASE_DIR, "keywords.json")


def env(name, required=True, default=None):
    value = os.getenv(name, default)

    if required and not value:
        raise RuntimeError(f"Environment variable '{name}' not found.")

    return value


NVIDIA_API_KEY = env("NVIDIA_API_KEY")

NVIDIA_MODEL = env(
    "NVIDIA_MODEL",
    required=False,
    default="nvidia/nemotron-3-ultra-253b-v1"
)

WP_BASE_URL = env("WP_BASE_URL").rstrip("/")

WP_USERNAME = env("WP_USERNAME")

WP_APP_PASSWORD = env("WP_APP_PASSWORD")

TELEGRAM_BOT_TOKEN = env("TELEGRAM_BOT_TOKEN")

TELEGRAM_CHAT_ID = env("TELEGRAM_CHAT_ID")


client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=NVIDIA_API_KEY,
)


retry = Retry(
    total=5,
    connect=5,
    read=5,
    backoff_factor=2,
    status_forcelist=[
        429,
        500,
        502,
        503,
        504
    ]
)

session = requests.Session()

adapter = HTTPAdapter(max_retries=retry)

session.mount("https://", adapter)

session.mount("http://", adapter)


def load_json(path, default):

    if not os.path.exists(path):
        return default

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):

    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )


def slugify(text):

    text = text.strip()

    text = re.sub(r"\s+", "-", text)

    return text


def send_telegram(message):

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    try:

        session.post(
            url,
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": False
            },
            timeout=30
        )

    except Exception as e:

        log.error(e)


def pick_today_keyword():

    keywords = load_json(KEYWORDS_FILE, [])

    state = load_json(
        STATE_FILE,
        {
            "day_index": 0
        }
    )

    idx = state["day_index"] % len(keywords)

    state["day_index"] = idx + 1

    save_json(
        STATE_FILE,
        state
    )

    return keywords[idx]
    def build_prompt(item):

    today = datetime.now().strftime("%Y-%m-%d")

    return f"""
تو یک متخصص حرفه‌ای سئو، نویسنده فنی و کارشناس تاسیسات ساختمان هستی.

برای سایت aramax24.ir یک مقاله کاملاً حرفه‌ای تولید کن.

موضوع:
{item["keyword"]}

دسته:
{item["category"]}

لینک داخلی:
{item["related_link"]}

لینک دسته:
{item["category_archive_link"]}

قوانین:

- مقاله کاملاً فارسی
- حداقل 1500 کلمه
- کاملاً یونیک
- مناسب RankMath
- دارای H2 و H3
- دارای جدول
- دارای لیست بولت
- دارای FAQ
- دارای نتیجه گیری
- دارای CTA
- لینک داخلی را طبیعی استفاده کن.
- اگر لینک دسته وجود داشت از آن نیز استفاده کن.
- هیچ Placeholder ننویس.
- هیچ Markdown ننویس.
- فقط HTML.

در انتها فقط JSON زیر را برگردان.

{{
"title":"",
"slug":"",
"meta_title":"",
"meta_description":"",
"content_html":"",
"schema_jsonld":{{}}
}}
"""


def repair_json(text):

    m = re.search(r"\{[\s\S]*\}", text)

    if m:
        text = m.group(0)

    text = text.replace("```json", "")

    text = text.replace("```", "")

    return json.loads(text)


def generate_article(item):

    log.info(item["keyword"])

    completion = client.chat.completions.create(

        model=NVIDIA_MODEL,

        temperature=0.5,

        top_p=0.9,

        max_tokens=4000,

        messages=[
            {
                "role": "user",
                "content": build_prompt(item)
            }
        ]
    )

    text = completion.choices[0].message.content

    article = repair_json(text)

    if not article.get("slug"):

        article["slug"] = slugify(article["title"])

    if not article.get("meta_title"):

        article["meta_title"] = article["title"]

    if not article.get("meta_description"):

        article["meta_description"] = article["title"][:150]

    if not article.get("schema_jsonld"):

        article["schema_jsonld"] = {}

    return article
    def publish(article):

    schema = ""

    if article.get("schema_jsonld"):

        schema = (
            '<script type="application/ld+json">'
            + json.dumps(
                article["schema_jsonld"],
                ensure_ascii=False
            )
            + "</script>"
        )

    content = article["content_html"] + "\n" + schema

    MAX_SIZE = 50000

    if len(content) > MAX_SIZE:

        log.warning(
            f"Article too large ({len(content)} chars). Trimming..."
        )

        content = content[:MAX_SIZE]

    payload = {

        "title": article["title"],

        "slug": article["slug"],

        "status": "publish",

        "content": content,

        "excerpt": article["meta_description"]

    }

    url = f"{WP_BASE_URL}/wp-json/wp/v2/posts"

    for attempt in range(1, 4):

        try:

            log.info(
                f"Publishing... Attempt {attempt}"
            )

            r = session.post(

                url,

                auth=(
                    WP_USERNAME,
                    WP_APP_PASSWORD
                ),

                json=payload,

                timeout=180,

                headers={
                    "User-Agent": "Aramax24Bot/2.0"
                }

            )

            log.info(
                f"WordPress HTTP {r.status_code}"
            )

            if r.status_code >= 400:

                log.error(r.text)

            r.raise_for_status()

            post = r.json()

            log.info(
                "Publish successful."
            )

            return post["link"]

        except requests.exceptions.ConnectionError as e:

            log.error(e)

            if attempt == 3:
                raise

            time.sleep(10)

        except requests.exceptions.Timeout:

            log.error("Timeout")

            if attempt == 3:
                raise

            time.sleep(10)

        except Exception:

            raise
            def notify_success(item, article, link):

    message = f"""
✅ <b>مقاله جدید منتشر شد</b>

📝 {article["title"]}

📂 {item["category"]}

🔑 {item["keyword"]}

🔗 {link}
"""

    send_telegram(message)


def notify_error(error):

    send_telegram(
        f"❌ خطا در انتشار مقاله\n\n{str(error)[:3500]}"
    )


def main():

    started = time.time()

    try:

        item = pick_today_keyword()

        log.info(item["keyword"])

        article = generate_article(item)

        log.info(article["title"])

        link = publish(article)

        notify_success(
            item,
            article,
            link
        )

        elapsed = round(
            time.time() - started,
            1
        )

        log.info(
            f"Completed in {elapsed} sec"
        )

    except Exception as e:

        log.exception(e)

        notify_error(e)

        raise


if __name__ == "__main__":

    main()

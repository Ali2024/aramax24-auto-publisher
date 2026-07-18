"""
Aramax24 Auto Publisher
NVIDIA Build Edition
"""

import os
import re
import json
import time
import logging
from datetime import datetime

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


BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)


STATE_FILE = os.path.join(
    BASE_DIR,
    "state.json"
)


KEYWORDS_FILE = os.path.join(
    BASE_DIR,
    "keywords.json"
)


def env(name, required=True, default=None):

    value = os.getenv(
        name,
        default
    )

    if required and not value:
        raise RuntimeError(
            f"Missing environment variable: {name}"
        )

    return value



NVIDIA_API_KEY = env(
    "NVIDIA_API_KEY"
)


NVIDIA_MODEL = os.getenv(
    "NVIDIA_MODEL",
    "nvidia/nemotron-3-ultra-550b-a55b"
)


WP_BASE_URL = env(
    "WP_BASE_URL"
).rstrip("/")


WP_USERNAME = env(
    "WP_USERNAME"
)


WP_APP_PASSWORD = env(
    "WP_APP_PASSWORD"
)


TELEGRAM_BOT_TOKEN = env(
    "TELEGRAM_BOT_TOKEN"
)


TELEGRAM_CHAT_ID = env(
    "TELEGRAM_CHAT_ID"
)



client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=NVIDIA_API_KEY
)



session = requests.Session()


retry_strategy = Retry(

    total=5,

    backoff_factor=2,

    status_forcelist=[
        429,
        500,
        502,
        503,
        504
    ],

)


adapter = HTTPAdapter(
    max_retries=retry_strategy
)


session.mount(
    "https://",
    adapter
)


session.mount(
    "http://",
    adapter
)
def load_json(path, default):

    if not os.path.exists(path):
        return default

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as f:
        return json.load(f)



def save_json(path, data):

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )



def slugify(text):

    text = text.strip()

    text = re.sub(
        r"\s+",
        "-",
        text
    )

    text = re.sub(
        r"[^\w\-]",
        "",
        text,
        flags=re.UNICODE
    )

    return text.lower()



def pick_keyword():

    keywords = load_json(
        KEYWORDS_FILE,
        []
    )

    if not keywords:
        raise RuntimeError(
            "keywords.json خالی است"
        )


    state = load_json(
        STATE_FILE,
        {
            "day_index": 0
        }
    )


    index = (
        state["day_index"]
        %
        len(keywords)
    )


    item = keywords[index]


    state["day_index"] = index + 1


    save_json(
        STATE_FILE,
        state
    )


    return item




def send_telegram(message):

    url = (
        f"https://api.telegram.org/"
        f"bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    try:

        session.post(
            url,
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "HTML"
            },
            timeout=30
        )

    except Exception as e:

        log.error(
            f"Telegram error: {e}"
        )




def build_prompt(item):

    today = datetime.now().strftime(
        "%Y-%m-%d"
    )


    return f"""

تو یک متخصص ارشد سئو فارسی و نویسنده فنی حوزه تاسیسات ساختمان هستی.

برای سایت:

aramax24.ir

یک مقاله حرفه‌ای تولید کن.


موضوع مقاله:

{item["keyword"]}


دسته:

{item["category"]}


لینک داخلی:

{item["related_link"]}


لینک دسته:

{item.get("category_archive_link","")}



قوانین محتوا:

- زبان کاملاً فارسی
- مناسب موتور جستجو گوگل
- حداقل 1200 کلمه
- مقدمه جذاب
- فهرست مطالب
- 5 بخش H2
- چند H3 مرتبط
- جدول در صورت نیاز
- FAQ حداقل 5 سوال
- جمع بندی
- دعوت به تماس با آرامکس24
- هیچ قیمت دقیق ننویس
- هیچ اطلاعات ساختگی درباره قیمت نده
- HTML خروجی بده
- Markdown ممنوع


قوانین JSON بسیار مهم:

- خروجی فقط JSON باشد
- هیچ متن قبل یا بعد JSON ننویس
- از ``` استفاده نکن
- تمام کوتیشن‌ها escape شوند
- خط جدید خام داخل رشته‌ها قرار نده


ساختار خروجی:


{{
"title":"",
"slug":"",
"meta_title":"",
"meta_description":"",
"content_html":"",
"schema_jsonld":{{}}
}}



تاریخ:

{today}

"""


# main.py
import os, json, re, logging, sys
from datetime import datetime, timezone

import requests
from openai import OpenAI

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("publisher")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE_DIR, "state.json")
KEYWORDS_FILE = os.path.join(BASE_DIR, "keywords.json")


def env(name, required=True, default=None):
    v = os.getenv(name, default)
    if required and not v:
        raise RuntimeError(f"Missing env: {name}")
    return v

NVIDIA_API_KEY = env("NVIDIA_API_KEY")
WP_BASE_URL = env("WP_BASE_URL").rstrip("/")
WP_USERNAME = env("WP_USERNAME")
WP_APP_PASSWORD = env("WP_APP_PASSWORD")
TELEGRAM_BOT_TOKEN = env("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = env("TELEGRAM_CHAT_ID")

MODEL = os.getenv("NVIDIA_MODEL", "nvidia/nemotron-3-ultra-550b-a55b")

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=NVIDIA_API_KEY,
)

def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path,"r",encoding="utf-8") as f:
        return json.load(f)

def save_json(path,data):
    with open(path,"w",encoding="utf-8") as f:
        json.dump(data,f,ensure_ascii=False,indent=2)

def telegram(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id":TELEGRAM_CHAT_ID,"text":msg,"parse_mode":"HTML"},
            timeout=20,
        ).raise_for_status()
    except Exception as e:
        log.error(e)

def pick():
    kws=load_json(KEYWORDS_FILE,[])
    st=load_json(STATE_FILE,{"day_index":0})
    idx=st["day_index"]%len(kws)
    st["day_index"]=idx+1
    save_json(STATE_FILE,st)
    return kws[idx]

def prompt(item):
    return f"""
فقط یک JSON معتبر تولید کن.

کلمه کلیدی:
{item["keyword"]}

دسته:
{item["category"]}

حدود 1500 کلمه بنویس.

فرمت:
{{
"title":"",
"slug":"",
"meta_title":"",
"meta_description":"",
"content_html":"",
"schema_jsonld":{{}}
}}
"""

def generate(item):
    r=client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role":"system","content":"تو متخصص سئو و تولید محتوای فارسی هستی. فقط JSON معتبر خروجی بده."},
            {"role":"user","content":prompt(item)}
        ],
        temperature=0.6,
        top_p=0.9,
        max_tokens=12000
    )

    raw=r.choices[0].message.content.strip()

    try:
        return json.loads(raw)
    except:
        m=re.search(r"\{[\s\S]*\}",raw)
        if not m:
            raise RuntimeError(raw)
        return json.loads(m.group(0))

def publish(article):
    schema=f'<script type="application/ld+json">{json.dumps(article["schema_jsonld"],ensure_ascii=False)}</script>'
    content=article["content_html"]+"\n"+schema

    r=requests.post(
        f"{WP_BASE_URL}/wp-json/wp/v2/posts",
        auth=(WP_USERNAME,WP_APP_PASSWORD),
        json={
            "title":article["title"],
            "slug":article["slug"],
            "content":content,
            "status":"publish",
            "excerpt":article.get("meta_description","")
        },
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["link"]

def main():
    try:
        item=pick()
        log.info(item["keyword"])
        article=generate(item)
        link=publish(article)
        telegram(f"✅ {article['title']}\n{link}")
        return 0
    except Exception as e:
        log.exception(e)
        telegram(f"❌ {e}")
        return 1

if __name__=="__main__":
    sys.exit(main())

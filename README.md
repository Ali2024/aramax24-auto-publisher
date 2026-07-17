# راهنمای راه‌اندازی روی GitHub Actions

## چرا GitHub Actions بهتر از سرور دستی است؟

نیازی به VPS یا سرور همیشه-روشن ندارید؛ خود GitHub رایگان (تا سقف مصرف پلن رایگان) هر روز اسکریپت رو براتون اجرا می‌کنه و بعد خاموش می‌شه. فقط باید ریپازیتوری رو بسازید و رمزها رو به‌عنوان **GitHub Secrets** اضافه کنید.

---

## مرحله ۱: ساخت ریپازیتوری

1. یک ریپازیتوری جدید تو گیت‌هاب بسازید (می‌تونه **Private** باشه — پیشنهاد می‌کنم Private بذارید چون کلمات کلیدی و لینک‌های داخلی سایتتونه)
2. همه فایل‌های این پوشه (`telegram-publisher-gh/`) رو داخلش push کنید:

```bash
git init
git add .
git commit -m "اولیه: ربات انتشار خودکار مقاله"
git branch -M main
git remote add origin https://github.com/USERNAME/REPO_NAME.git
git push -u origin main
```

## مرحله ۲: ساخت ربات تلگرام و گرفتن Chat ID

(دقیقاً مثل قبل)
1. به [@BotFather](https://t.me/BotFather) پیام بدید، `/newbot` رو بزنید، توکن رو بگیرید
2. به ربات جدید یک پیام بفرستید
3. آدرس `https://api.telegram.org/bot<TOKEN>/getUpdates` رو باز کنید و مقدار `chat.id` رو پیدا کنید

## مرحله ۳: اضافه کردن Secrets در گیت‌هاب

تو ریپازیتوری: **Settings → Secrets and variables → Actions → New repository secret**

این ۶ secret رو یکی‌یکی اضافه کنید:

| نام Secret | مقدار |
|---|---|
| `ANTHROPIC_API_KEY` | کلید API از console.anthropic.com |
| `TELEGRAM_BOT_TOKEN` | توکن ربات از BotFather |
| `TELEGRAM_CHAT_ID` | Chat ID شما |
| `WP_BASE_URL` | `https://aramax24.ir` |
| `WP_USERNAME` | نام کاربری ادمین وردپرس |
| `WP_APP_PASSWORD` | Application Password (نه پسورد اصلی!) |

اختیاری — تو تب **Variables** (نه Secrets) می‌تونید `CLAUDE_MODEL` رو هم با مقدار `claude-sonnet-5` اضافه کنید؛ اگه اضافه نکنید، همین مقدار پیش‌فرضه.

## مرحله ۴: فعال‌سازی Actions

اگه ریپو private بود، معمولاً Actions به‌طور پیش‌فرض فعاله. برید به تب **Actions** ریپازیتوری و مطمئن شید ورک‌فلوی «Daily Article Publisher» دیده می‌شه.

## مرحله ۵: تست دستی (بدون صبر تا فردا)

1. تو تب **Actions**، روی ورک‌فلوی «Daily Article Publisher» کلیک کنید
2. دکمه **Run workflow** (سمت راست) رو بزنید
3. چند دقیقه صبر کنید؛ باید یه پیام تلگرام با لینک مقاله منتشرشده بگیرید
4. اگه خطا داد، روی اجرای قرمز کلیک کنید و لاگ رو ببینید (معمولاً یعنی یکی از Secrets اشتباه تنظیم شده)

## بعد از تست موفق

از فردا، خودش هر روز ساعت ۹ صبح (تهران) اجرا می‌شه، بدون نیاز به هیچ کاری از طرف شما. فقط منتظر پیام تلگرامتون بمونید.

---

## نکات مهم

- **شمارنده روز:** فایل `state.json` بعد از هر اجرا خودکار توسط خودِ Action commit و push می‌شه؛ یعنی وضعیت بین اجراها حفظ می‌مونه، دقیقاً مثل یه دیتابیس ساده داخل خود ریپو.
- **افزودن کلمات کلیدی بیشتر:** فایل `keywords.json` رو ویرایش و commit کنید.
- **توقف موقت:** کافیه تو تب Actions، ورک‌فلو رو Disable کنید.
- **تغییر ساعت انتشار:** خط `cron: "30 5 * * *"` رو تو فایل `.github/workflows/publish-daily.yml` عوض کنید (فرمت UTC، نه وقت تهران).
- **دسته «تجهیزات بهداشتی ساختمان»:** بعد از ساخت این دسته تو وردپرس، مقدار `__REPLACE_AFTER_CATEGORY_CREATED__` رو تو `keywords.json` با لینک واقعی جایگزین و commit کنید.
- **امنیت:** هیچ رمزی داخل کد یا فایل‌های commit‌شده نیست؛ همه از GitHub Secrets خونده می‌شه که رمزنگاری‌شده ذخیره می‌شن و حتی خود شما هم بعد از ثبت نمی‌تونید دوباره ببینیدشون (فقط می‌تونید override کنید).

## تست محلی (اختیاری، قبل از push)

اگه می‌خواید قبلش رو کامپیوترتون تست کنید:
```bash
pip install -r requirements.txt
cp .env.example .env   # و مقادیر رو پر کنید
python main.py
```

## عیب‌یابی

| مشکل | راه‌حل |
|---|---|
| Action اجرا نمی‌شود | چک کنید Actions برای ریپو فعاله (Settings → Actions → General) |
| خطای 401 از Anthropic/وردپرس | مقدار Secret مربوطه رو دوباره چک و ذخیره کنید |
| پیام تلگرام نمی‌رسد | Chat ID و توکن رو با curl دستی تست کنید |
| `git push` در مرحله آخر Action خطا می‌دهد | مطمئن شوید `permissions: contents: write` در فایل workflow حذف نشده باشد |

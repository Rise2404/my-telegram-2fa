import os
import hmac
import json
import urllib.request
import urllib.error
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse

app = FastAPI(title="2FA bot")
ROOT = Path(__file__).parent

# Секреты берутся ТОЛЬКО из переменных окружения (Vercel -> Settings -> Environment Variables).
BOT_TOKEN = os.environ.get("8729764409:AAEcEjalBoikiN8KrBaslawXJllXF0OxD1I", "")
WEBHOOK_SECRET = os.environ.get("https://my-t-2fa.vercel.app", "")
# Адрес не секретный, поэтому есть значение по умолчанию.
WEBAPP_URL = os.environ.get("WEBAPP_URL", "https://my-telegram-2fa.vercel.app")
STAR_PRICE = int(os.environ.get("STAR_PRICE", "50"))
API = "https://api.telegram.org/bot" + BOT_TOKEN

OPEN_TEXT = "Открыть 2FA"
ALLOWED_UPDATES = ["message", "pre_checkout_query", "callback_query"]


def tg(method, payload):
    if not BOT_TOKEN:
        return {"ok": False, "description": "BOT_TOKEN is not set"}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        API + "/" + method,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return {"ok": False, "description": exc.read().decode("utf-8", errors="replace")}
    except Exception as exc:
        return {"ok": False, "description": str(exc)}


@app.get("/")
def page():
    return FileResponse(ROOT / "index.html")


@app.get("/app.js")
def script():
    return FileResponse(ROOT / "app.js")


def configure():
    """Регистрирует вебхук, список команд и кнопку меню «Открыть 2FA»."""
    result = {}
    hook = {
        "url": WEBAPP_URL.rstrip("/") + "/api/telegram",
        "allowed_updates": ALLOWED_UPDATES,
    }
    if WEBHOOK_SECRET:
        hook["secret_token"] = WEBHOOK_SECRET
    result["setWebhook"] = tg("setWebhook", hook)
    result["setMyCommands"] = tg("setMyCommands", {
        "commands": [
            {"command": "start", "description": "Запуск и открыть 2FA"},
            {"command": "app", "description": "Открыть 2FA"},
            {"command": "pay", "description": "Поддержать звёздами"},
        ]
    })
    result["setChatMenuButton"] = tg("setChatMenuButton", {
        "menu_button": {
            "type": "web_app",
            "text": OPEN_TEXT,
            "web_app": {"url": WEBAPP_URL},
        }
    })
    return result


@app.on_event("startup")
def on_startup():
    if BOT_TOKEN:
        print("configure:", configure())


@app.get("/api/setup")
def setup(key: str = ""):
    # Откройте один раз: https://ВАШ-САЙТ/api/setup?key=WEBHOOK_SECRET
    if not WEBHOOK_SECRET or not hmac.compare_digest(key, WEBHOOK_SECRET):
        return JSONResponse({"ok": False, "error": "forbidden"}, status_code=403)
    return configure()


def open_app(chat_id):
    return tg("sendMessage", {
        "chat_id": chat_id,
        "text": "2FA Authenticator",
        "reply_markup": {
            "inline_keyboard": [
                [{"text": OPEN_TEXT, "web_app": {"url": WEBAPP_URL}}],
                [{"text": "Поддержать ⭐", "callback_data": "pay"}],
            ]
        },
    })


def send_invoice(chat_id):
    return tg("sendInvoice", {
        "chat_id": chat_id,
        "title": "Поддержка",
        "description": "Оплата Telegram Stars",
        "payload": "support",
        "provider_token": "",
        "currency": "XTR",
        "prices": [{"label": "Поддержать", "amount": STAR_PRICE}],
    })


def parse_command(text):
    """'/start@bot pay' -> ('start', 'pay'); обычный текст -> ('', '')."""
    if not text.startswith("/"):
        return "", ""
    parts = text.split(None, 1)
    command = parts[0][1:].split("@")[0].lower()
    arg = parts[1].strip().lower() if len(parts) > 1 else ""
    return command, arg


@app.post("/api/telegram")
async def telegram_webhook(request: Request):
    if WEBHOOK_SECRET:
        header = request.headers.get("x-telegram-bot-api-secret-token", "")
        if not hmac.compare_digest(header, WEBHOOK_SECRET):
            return JSONResponse({"ok": False}, status_code=401)
    update = await request.json()

    if "pre_checkout_query" in update:
        tg("answerPreCheckoutQuery", {
            "pre_checkout_query_id": update["pre_checkout_query"]["id"],
            "ok": True,
        })
        return {"ok": True}

    if "callback_query" in update:
        query = update["callback_query"]
        tg("answerCallbackQuery", {"callback_query_id": query["id"]})
        chat_id = ((query.get("message") or {}).get("chat") or {}).get("id")
        if chat_id and query.get("data") == "pay":
            send_invoice(chat_id)
        return {"ok": True}

    message = update.get("message") or {}
    chat_id = (message.get("chat") or {}).get("id")
    text = (message.get("text") or "").strip()
    if not chat_id:
        return {"ok": True}

    if message.get("successful_payment"):
        charge = message["successful_payment"].get("telegram_payment_charge_id", "")
        tg("sendMessage", {"chat_id": chat_id, "text": "Stars получены. Спасибо! " + charge})
        return {"ok": True}

    command, arg = parse_command(text)
    if command == "start":
        open_app(chat_id)
        if arg == "pay":
            send_invoice(chat_id)
    elif command == "pay":
        send_invoice(chat_id)
    elif command == "app":
        open_app(chat_id)
    elif text.lower() == OPEN_TEXT.lower():
        open_app(chat_id)
    return {"ok": True}

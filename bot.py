import os
import json
import urllib.request
import urllib.error
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse

app = FastAPI(title="2FA bot")
ROOT = Path(__file__).parent

BOT_TOKEN = os.environ.get("8729764409:AAEyPNZSzbEJgYjtdqaxWWIKhUeWa5vxVjE", "")
WEBHOOK_SECRET = os.environ.get("https://my-telegram-2fa.vercel.app", "")
WEBAPP_URL = os.environ.get("rise2fa_8f3k29x", "")
STAR_PRICE = int(os.environ.get("STAR_PRICE", "50"))
API = "https://api.telegram.org/bot" + BOT_TOKEN


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


@app.get("/")
def page():
    return FileResponse(ROOT / "index.html")


@app.get("/app.js")
def script():
    return FileResponse(ROOT / "app.js")


@app.on_event("startup")
def set_webhook():
    # Регистрирует вебхук автоматически, если заданы BOT_TOKEN и WEBAPP_URL
    if not BOT_TOKEN or not WEBAPP_URL:
        return
    payload = {
        "url": WEBAPP_URL.rstrip("/") + "/api/telegram",
        "allowed_updates": ["message", "pre_checkout_query"],
    }
    if WEBHOOK_SECRET:
        payload["secret_token"] = WEBHOOK_SECRET
    print("setWebhook:", tg("setWebhook", payload))


def open_app(chat_id):
    if not WEBAPP_URL:
        return tg("sendMessage", {
            "chat_id": chat_id,
            "text": "Страница 2FA на этом сервере: открой сайт бота в браузере. Для кнопки внутри Telegram задай WEBAPP_URL.",
        })
    return tg("sendMessage", {
        "chat_id": chat_id,
        "text": "2FA Authenticator",
        "reply_markup": {
            "inline_keyboard": [[
                {"text": "Открыть 2FA", "web_app": {"url": WEBAPP_URL}}
            ]]
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


@app.post("/api/telegram")
async def telegram_webhook(request: Request):
    if WEBHOOK_SECRET:
        header = request.headers.get("x-telegram-bot-api-secret-token", "")
        if header != WEBHOOK_SECRET:
            return JSONResponse({"ok": False}, status_code=401)
    update = await request.json()

    if "pre_checkout_query" in update:
        tg("answerPreCheckoutQuery", {
            "pre_checkout_query_id": update["pre_checkout_query"]["id"],
            "ok": True,
        })
        return {"ok": True}

    message = update.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    text = message.get("text") or ""

    if chat_id and text.startswith("/start"):
        open_app(chat_id)
        if "pay" in text:
            send_invoice(chat_id)
        return {"ok": True}
    if chat_id and text.startswith("/pay"):
        send_invoice(chat_id)
        return {"ok": True}
    if chat_id and text.startswith("/app"):
        open_app(chat_id)
        return {"ok": True}
    if chat_id and message.get("successful_payment"):
        charge = message["successful_payment"].get("telegram_payment_charge_id", "")
        tg("sendMessage", {"chat_id": chat_id, "text": "Stars получены. " + charge})
        return {"ok": True}
    return {"ok": True}

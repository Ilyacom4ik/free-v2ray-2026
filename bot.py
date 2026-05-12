#!/usr/bin/env python3
import os
import json
import random
import socket
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
from datetime import datetime

BOT_TOKEN = os.environ['TG_BOT_TOKEN']
API = f"https://api.telegram.org/bot{BOT_TOKEN}"

CHECK_TIMEOUT = 3
CHECK_WORKERS = 50
MAX_KEYS_PER_COUNTRY = 5  # максимум ключей на страну

def get_updates(offset=None):
    params = {"timeout": 30}
    if offset:
        params["offset"] = offset
    r = requests.get(f"{API}/getUpdates", params=params, timeout=35)
    return r.json().get("result", [])

def send_message(chat_id, text, reply_markup=None):
    data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    requests.post(f"{API}/sendMessage", json=data)

def answer_callback(callback_id, text=""):
    requests.post(f"{API}/answerCallbackQuery", json={
        "callback_query_id": callback_id,
        "text": text
    })

def load_keys():
    try:
        with open('subscriptions/keys_by_country.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {"lite": {}, "full": {}}

def parse_host_port(config):
    try:
        clean = config.split('#')[0].strip()
        parsed = urlparse(clean)
        return parsed.hostname, parsed.port
    except:
        return None, None

def check_key(config):
    host, port = parse_host_port(config)
    if not host or not port:
        return False
    try:
        sock = socket.create_connection((host, port), timeout=CHECK_TIMEOUT)
        sock.close()
        return True
    except:
        return False

def get_status():
    try:
        with open('subscriptions/FreeCFGHub.txt', 'r', encoding='utf-8') as f:
            lines = [l.strip() for l in f if l.strip().startswith(
                ('vless://', 'vmess://', 'trojan://', 'ss://', 'hysteria2://')
            )]
        total = len(lines)
        alive = 0
        with ThreadPoolExecutor(max_workers=CHECK_WORKERS) as ex:
            futures = {ex.submit(check_key, cfg): cfg for cfg in lines}
            for future in as_completed(futures):
                try:
                    if future.result():
                        alive += 1
                except:
                    pass
        updated = datetime.utcfromtimestamp(
            os.path.getmtime('subscriptions/FreeCFGHub.txt')
        ).strftime('%d.%m.%Y %H:%M UTC')
        return (
            f"📊 <b>Статус подписки</b>\n\n"
            f"📋 Всего ключей: {total}\n"
            f"✅ Отвечают (TCP): {alive}\n"
            f"❌ Не отвечают: {total - alive}\n\n"
            f"🕐 Обновлено: {updated}\n\n"
            f"📢 @FreeCFGHub"
        )
    except Exception as e:
        return f"❌ Ошибка: {e}"

def make_country_keyboard(list_type, keys_data):
    countries = sorted(keys_data.get(list_type, {}).keys())
    buttons = []
    row = []
    for i, country in enumerate(countries):
        row.append({"text": country, "callback_data": f"country:{list_type}:{country}"})
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([{"text": "🎲 Рандомный", "callback_data": f"country:{list_type}:random"}])
    buttons.append([{"text": "◀️ Назад", "callback_data": "back_to_type"}])
    return {"inline_keyboard": buttons}

def main():
    print("🤖 Бот запущен", flush=True)
    offset = None
    while True:
        updates = get_updates(offset)
        for update in updates:
            offset = update["update_id"] + 1

            # Обычное сообщение
            if "message" in update:
                msg = update["message"]
                chat_id = msg.get("chat", {}).get("id")
                text = msg.get("text", "")

                if not chat_id:
                    continue

                if text == "/start":
                    send_message(chat_id,
                        "👋 Привет!\n\n"
                        "/keys — получить ключи по странам\n"
                        "/status — статус подписки"
                    )

                elif text == "/status":
                    send_message(chat_id, "⏳ Проверяю ключи, подожди...")
                    send_message(chat_id, get_status())

                elif text == "/keys":
                    send_message(chat_id,
                        "Выберите тип подписки:",
                        reply_markup={
                            "inline_keyboard": [
                                [
                                    {"text": "🏳️ Lite (при БС)", "callback_data": "type:lite"},
                                    {"text": "🏴 Full (ЧС)", "callback_data": "type:full"}
                                ]
                            ]
                        }
                    )

            # Нажатие кнопки
            elif "callback_query" in update:
                cb = update["callback_query"]
                chat_id = cb["message"]["chat"]["id"]
                data = cb.get("data", "")
                answer_callback(cb["id"])

                if data.startswith("type:"):
                    list_type = data.split(":")[1]
                    keys_data = load_keys()
                    keyboard = make_country_keyboard(list_type, keys_data)
                    label = "Lite 🏳️" if list_type == "lite" else "Full 🏴"
                    send_message(chat_id, f"Выберите страну ({label}):", reply_markup=keyboard)

                elif data.startswith("country:"):
                    parts = data.split(":", 2)
                    list_type = parts[1]
                    country = parts[2]
                    keys_data = load_keys()
                    country_keys = keys_data.get(list_type, {})

                    if country == "random":
                        all_keys = [k for keys in country_keys.values() for k in keys]
                        selected = random.sample(all_keys, min(MAX_KEYS_PER_COUNTRY, len(all_keys)))
                    else:
                        keys = country_keys.get(country, [])
                        selected = random.sample(keys, min(MAX_KEYS_PER_COUNTRY, len(keys)))

                    if not selected:
                        send_message(chat_id, "❌ Ключи не найдены")
                        continue

                    result = "\n".join(selected)
                    send_message(chat_id,
                        f"🔑 <b>{country} — {len(selected)} ключей</b>\n\n"
                        f"<code>{result}</code>\n\n"
                        f"📢 @FreeCFGHub"
                    )

                elif data == "back_to_type":
                    send_message(chat_id,
                        "Выберите тип подписки:",
                        reply_markup={
                            "inline_keyboard": [
                                [
                                    {"text": "🏳️ Lite (при БС)", "callback_data": "type:lite"},
                                    {"text": "🏴 Full (ЧС)", "callback_data": "type:full"}
                                ]
                            ]
                        }
                    )

if __name__ == '__main__':
    main()

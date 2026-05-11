#!/usr/bin/env python3
import os
import socket
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
from datetime import datetime

BOT_TOKEN = os.environ['TG_BOT_TOKEN']
API = f"https://api.telegram.org/bot{BOT_TOKEN}"

CHECK_TIMEOUT = 3
CHECK_WORKERS = 50

def get_updates(offset=None):
    params = {"timeout": 30}
    if offset:
        params["offset"] = offset
    r = requests.get(f"{API}/getUpdates", params=params, timeout=35)
    return r.json().get("result", [])

def send_message(chat_id, text):
    requests.post(f"{API}/sendMessage", json={
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    })

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

        # Проверяем по TCP
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

def main():
    print("🤖 Бот запущен", flush=True)
    offset = None
    while True:
        updates = get_updates(offset)
        for update in updates:
            offset = update["update_id"] + 1
            msg = update.get("message", {})
            chat_id = msg.get("chat", {}).get("id")
            text = msg.get("text", "")

            if not chat_id:
                continue

            if text == "/start":
                send_message(chat_id,
                    "👋 Привет!\n\n"
                    "/status — проверить статус ключей\n"
                    "/keys — получить ссылку на подписку"
                )
            elif text == "/status":
                send_message(chat_id, "⏳ Проверяю ключи, подожди...")
                send_message(chat_id, get_status())
            elif text == "/keys":
                send_message(chat_id,
                    "📲 <b>Ссылки на подписку:</b>\n\n"
                    "При БС:\n"
                    "https://translate.yandex.ru/translate?url=https://raw.githubusercontent.com/Ilyacom4ik/free-v2ray-2026/refs/heads/main/subscriptions/FreeCFGHub1.txt\n\n"
                    "Прямая:\n"
                    "https://raw.githubusercontent.com/Ilyacom4ik/free-v2ray-2026/refs/heads/main/subscriptions/FreeCFGHub1.txt\n\n"
                    "📢 @FreeCFGHub"
                )

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
import os
import re
import random
import requests
from datetime import datetime

BOT_TOKEN = os.environ['TG_BOT_TOKEN']
API = f"https://api.telegram.org/bot{BOT_TOKEN}"

SUBSCRIPTION_URL = "https://raw.githubusercontent.com/Ilyacom4ik/vpn-keys/refs/heads/main/allkeysFreeCFGHub.txt"

MAX_KEYS_PER_REQUEST = 5  # сколько ключей выдавать за раз

def get_updates(offset=None):
    params = {"timeout": 30}
    if offset:
        params["offset"] = offset
    r = requests.get(f"{API}/getUpdates", params=params, timeout=35)
    return r.json().get("result", [])

def send_message(chat_id, text, reply_markup=None):
    data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        data["reply_markup"] = reply_markup
    requests.post(f"{API}/sendMessage", json=data)

def answer_callback(callback_id, text=""):
    requests.post(f"{API}/answerCallbackQuery", json={
        "callback_query_id": callback_id,
        "text": text
    })

def fetch_and_parse_keys():
    """Парсит подписку прямо с GitHub, разделяет на Lite и Full"""
    try:
        r = requests.get(SUBSCRIPTION_URL, timeout=15)
        if r.status_code != 200:
            return None, f"Ошибка загрузки: {r.status_code}"
        
        content = r.text
        lines = content.splitlines()
        
        lite_keys = []
        full_keys = []
        current_category = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Определяем категорию по заголовкам
            if "🏳️ Lite" in line:
                current_category = "lite"
                continue
            elif "🏴 Full" in line:
                current_category = "full"
                continue
            
            # Пропускаем комментарии и пустые строки
            if line.startswith('#') or line.startswith('//') or line.startswith('```'):
                continue
            
            # Если строка начинается с протокола — это ключ
            if re.match(r'^(vless|vmess|trojan|ss|tuic|hysteria2)://', line):
                if current_category == "lite":
                    lite_keys.append(line)
                elif current_category == "full":
                    full_keys.append(line)
                # Если категория не определена, кидаем в full как запасной вариант
                elif current_category is None:
                    full_keys.append(line)
        
        return {"lite": lite_keys, "full": full_keys}, None
        
    except Exception as e:
        return None, str(e)

def get_random_keys(keys_list, count=MAX_KEYS_PER_REQUEST):
    """Возвращает случайные ключи из списка"""
    if not keys_list:
        return []
    count = min(count, len(keys_list))
    return random.sample(keys_list, count)

def get_status():
    """Возвращает статус подписки (количество Lite и Full ключей)"""
    try:
        keys_data, error = fetch_and_parse_keys()
        if error:
            return f"❌ Ошибка: {error}"
        
        lite_count = len(keys_data.get("lite", []))
        full_count = len(keys_data.get("full", []))
        
        return (
            f"📊 <b>Статус подписки</b>\n\n"
            f"🏳️ Lite ключей: {lite_count}\n"
            f"🏴 Full ключей: {full_count}\n\n"
            f"🔄 Обновляется каждые 6 часов\n\n"
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

            if "message" in update:
                msg = update["message"]
                chat_id = msg.get("chat", {}).get("id")
                text = msg.get("text", "")

                if not chat_id:
                    continue

                if text == "/start":
                    send_message(chat_id,
                        "👋 Привет!\n\n"
                        "Я выдаю VPN-ключи из подписки @FreeCFGHub\n\n"
                        "/keys — получить случайные ключи\n"
                        "/status — статус подписки"
                    )

                elif text == "/status":
                    send_message(chat_id, "⏳ Проверяю...")
                    send_message(chat_id, get_status())

                elif text == "/keys":
                    send_message(chat_id,
                        "Выберите тип ключей:",
                        reply_markup={
                            "inline_keyboard": [
                                [
                                    {"text": "🏳️ Lite (оптимизированный)", "callback_data": "get:lite"},
                                    {"text": "🏴 Full (полный доступ)", "callback_data": "get:full"}
                                ]
                            ]
                        }
                    )

            elif "callback_query" in update:
                cb = update["callback_query"]
                chat_id = cb["message"]["chat"]["id"]
                data = cb.get("data", "")
                answer_callback(cb["id"])

                if data.startswith("get:"):
                    key_type = data.split(":")[1]  # lite или full
                    
                    keys_data, error = fetch_and_parse_keys()
                    if error:
                        send_message(chat_id, f"❌ Ошибка: {error}")
                        continue
                    
                    keys_list = keys_data.get(key_type, [])
                    if not keys_list:
                        send_message(chat_id, f"❌ Ключей типа {key_type} не найдено")
                        continue
                    
                    selected = get_random_keys(keys_list)
                    type_name = "Lite 🏳️" if key_type == "lite" else "Full 🏴"
                    
                    # Форматируем ключи для удобного копирования
                    keys_block = "\n\n".join([f"<code>{k}</code>" for k in selected])
                    
                    send_message(chat_id,
                        f"🔑 <b>{type_name} — {len(selected)} ключей</b>\n\n"
                        f"{keys_block}\n\n"
                        f"📢 @FreeCFGHub"
                    )

if __name__ == '__main__':
    main()

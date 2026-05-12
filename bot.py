#!/usr/bin/env python3
import os
import re
import random
import requests
from datetime import datetime

BOT_TOKEN = os.environ['TG_BOT_TOKEN']
API = f"https://api.telegram.org/bot{BOT_TOKEN}"

SUBSCRIPTION_URL = "https://raw.githubusercontent.com/Ilyacom4ik/vpn-keys/refs/heads/main/allkeysFreeCFGHub.txt"

MAX_KEYS_PER_REQUEST = 5

# Ссылка на пост с донатом (твоя)
DONATE_POST_URL = "https://t.me/FreeCFGHub/328"

# Текст для команды /donate
DONATE_TEXT = (
    "❤️ <b>Поддержать проект</b>\n\n"
    "Спасибо, что хотите помочь! Ваша поддержка помогает серверам работать.\n\n"
    "💳 <b>Карта Сбера:</b>\n"
    "<code>2202 2068 1475 8129</code>\n\n"
    "📢 @FreeCFGHub"
)

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

def set_bot_commands():
    """Устанавливает кнопки меню снизу (команды)"""
    commands = [
        {"command": "start", "description": "🏠 Главное меню"},
        {"command": "keys", "description": "🔑 Получить ключи"},
        {"command": "status", "description": "📡 Статус"},
        {"command": "donate", "description": "❤️ Поддержать"}
    ]
    url = f"{API}/setMyCommands"
    requests.post(url, json={"commands": commands})
    print("✅ Кнопки меню установлены", flush=True)

def fetch_and_parse_keys():
    """Парсит подписку, ищет Lite и Full по ключевым словам (без флагов)"""
    try:
        r = requests.get(SUBSCRIPTION_URL, timeout=15)
        if r.status_code != 200:
            return None, f"Ошибка загрузки: {r.status_code}"
        
        content = r.text
        lines = content.splitlines()
        
        lite_keys = []
        full_keys = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Пропускаем строки, которые начинаются с # (комментарии)
            if line.startswith('#'):
                continue
            
            # Проверяем, является ли строка валидным ключом (любой протокол)
            if re.match(r'^(vless|vmess|trojan|ss|tuic|hysteria2)://', line):
                # Если в строке есть слово Lite (без учёта регистра) — это lite
                if re.search(r'\bLite\b', line, re.IGNORECASE):
                    lite_keys.append(line)
                # Если в строке есть слово Full — это full
                elif re.search(r'\bFull\b', line, re.IGNORECASE):
                    full_keys.append(line)
                # Если ничего не нашли, отправляем в full (на всякий случай)
                else:
                    full_keys.append(line)
        
        print(f"DEBUG: Lite ключей: {len(lite_keys)}, Full ключей: {len(full_keys)}", flush=True)
        return {"lite": lite_keys, "full": full_keys}, None
        
    except Exception as e:
        return None, str(e)

def get_random_keys(keys_list, count=MAX_KEYS_PER_REQUEST):
    if not keys_list:
        return []
    count = min(count, len(keys_list))
    return random.sample(keys_list, count)

def get_status():
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
            f"🔄 Обновляется каждый день\n\n"
            f"📢 @FreeCFGHub"
        )
    except Exception as e:
        return f"❌ Ошибка: {e}"

def main():
    print("🤖 Бот запущен", flush=True)
    
    # Устанавливаем кнопки меню снизу
    set_bot_commands()
    
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
                        f"👋 Привет!\n\n"
                        f"Я выдаю VPN-ключи из подписки @FreeCFGHub\n\n"
                        f"Используй кнопки в меню снизу 👇\n\n"
                        f"🔑 /keys — получить ключи\n"
                        f"📡 /status — статус подписки\n"
                        f"❤️ /donate — поддержать проект\n\n"
                        f"✨ <a href='{DONATE_POST_URL}'>Поддержать проект ✨</a>"
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
                                    {"text": "🏳️ Lite", "callback_data": "get:lite"},
                                    {"text": "🏴 Full", "callback_data": "get:full"}
                                ]
                            ]
                        }
                    )
                
                elif text == "/donate":
                    send_message(chat_id, DONATE_TEXT)

            elif "callback_query" in update:
                cb = update["callback_query"]
                chat_id = cb["message"]["chat"]["id"]
                data = cb.get("data", "")
                answer_callback(cb["id"])

                if data.startswith("get:"):
                    key_type = data.split(":")[1]
                    
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
                    
                    keys_block = "\n\n".join([f"<code>{k}</code>" for k in selected])
                    
                    send_message(chat_id,
                        f"🔑 <b>{type_name} — {len(selected)} ключей</b>\n\n{keys_block}\n\n📢 @FreeCFGHub"
                    )

if __name__ == '__main__':
    main()

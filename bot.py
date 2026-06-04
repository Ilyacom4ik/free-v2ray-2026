#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║                        КАК РАБОТАЕТ БОТ                                ║
# ║                                                                          ║
# ║  1. main() запускает два потока одновременно:                            ║
# ║     • Long-polling цикл — постоянно спрашивает Telegram «есть апдейты?» ║
# ║     • Flask-сервер на порту 8080 — принимает webhook от платёжки        ║
# ║                                                                          ║
# ║  2. Пользователь нажимает кнопку → Telegram присылает callback_query    ║
# ║     → handle_callback() разбирает data кнопки и отвечает нужным текстом ║
# ║                                                                          ║
# ║  3. Пользователь хочет премиум:                                          ║
# ║     • create_payment() создаёт транзакцию в Platega                     ║
# ║     • Бот присылает ссылку на оплату                                     ║
# ║     • После оплаты Platega делает POST на /payment/callback              ║
# ║     • payment_callback() проверяет подпись и вызывает _deliver_premium() ║
# ║     • _deliver_premium() генерирует UUID-токен и отдаёт ссылку /sub/... ║
# ║                                                                          ║
# ║  4. VPN-клиент открывает /sub/<token> → proxy_sub() проверяет:          ║
# ║     • токен существует в словаре active_premium_tokens                   ║
# ║     • User-Agent выглядит как VPN-клиент (иначе 403)                    ║
# ║     • Скачивает реальную подписку и отдаёт её клиенту                   ║
# ╚══════════════════════════════════════════════════════════════════════════╝

import os
import re
import uuid
import random
import threading
import requests
from flask import Flask, request, Response, abort


# ═══════════════════════════════════════════════════════
#                     НАСТРОЙКИ
# ═══════════════════════════════════════════════════════

# Токен бота из @BotFather
TELEGRAM_BOT_TOKEN      = os.environ['TG_BOT_TOKEN']

# Идентификатор мерчанта в Platega (передаётся в заголовке X-MerchantId)
PLATEGA_MERCHANT_ID     = os.environ['PLATEGA_MERCHANT_ID']

# Секрет для проверки входящих webhook-запросов от Platega
PLATEGA_WEBHOOK_SECRET  = os.environ['PLATEGA_SECRET']

# Публичный HTTPS-адрес этого сервера (без слэша в конце)
# Пример: https://mybot.example.com
PUBLIC_SERVER_URL       = os.environ['SERVER_URL']

# Цена премиум-подписки в рублях (по умолчанию 99)
PREMIUM_PRICE_RUB       = int(os.environ.get('PREMIUM_PRICE', '99'))

# Базовый URL для всех Telegram API запросов
TELEGRAM_API_BASE       = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# Базовый URL платёжного шлюза Platega
PLATEGA_API_BASE        = "https://app.platega.io"

# URL небольшой подписки (мало серверов, быстро загружается)
SMALL_SUBSCRIPTION_URL  = "https://raw.githubusercontent.com/Ilyacom4ik/free-v2ray-2026/refs/heads/main/subscriptions/FreeCFGHub1.txt"

# URL большой подписки (много серверов, могут быть лаги)
BIG_SUBSCRIPTION_URL    = "https://raw.githubusercontent.com/Ilyacom4ik/vpn-keys/refs/heads/main/allkeysFreeCFGHub.txt"

# URL откуда скачиваем ключи для парсинга (lite/full)
KEYS_SOURCE_URL         = "https://raw.githubusercontent.com/Ilyacom4ik/vpn-keys/refs/heads/main/allkeysFreeCFGHub.txt"

# URL реальной подписки для премиум-пользователей (проксируется через /sub/<token>)
PREMIUM_REAL_CONTENT_URL = "https://raw.githubusercontent.com/Ilyacom4ik/vpn-keys/refs/heads/main/allkeysFreeCFGHub.txt"

# Ссылка на Telegram-канал проекта
PROJECT_CHANNEL_URL     = "https://t.me/FreeCFGHub"

# Файл с ID пользователей, совершивших покупку
USERS_DATABASE_FILE     = "database.txt"

# Сколько ключей выдавать пользователю при запросе
LITE_KEYS_COUNT         = 5
FULL_KEYS_COUNT         = 7

# Словарь активных премиум-токенов: { uuid_token: telegram_user_id }
# Заполняется при успешной оплате, используется в /sub/<token>
active_premium_tokens: dict[str, int] = {}

# Словарь ожидающих оплат: { transaction_id: telegram_user_id }
# Нужен на случай если Platega пришлёт callback без поля payload
pending_payment_user_ids: dict[str, int] = {}


# ═══════════════════════════════════════════════════════
#                      БАЗА ДАННЫХ
# ═══════════════════════════════════════════════════════
# Простая БД — текстовый файл, по одному Telegram ID на строку.
# Хранит только тех, кто купил премиум (для аналитики).

def db_save_user(user_id: int):
    """Записать TG ID в файл-базу, если его там ещё нет."""
    user_id_str = str(user_id)
    existing_ids = db_load_all_user_ids()
    if user_id_str not in existing_ids:
        with open(USERS_DATABASE_FILE, "a", encoding="utf-8") as file:
            file.write(user_id_str + "\n")
        print(f"✅ Новый покупатель добавлен в БД: {user_id_str}", flush=True)

def db_load_all_user_ids() -> set:
    """Загрузить все сохранённые TG ID из файла."""
    if not os.path.exists(USERS_DATABASE_FILE):
        return set()
    with open(USERS_DATABASE_FILE, "r", encoding="utf-8") as file:
        return {line.strip() for line in file if line.strip()}

def db_check_user_exists(user_id: int) -> bool:
    """Проверить, есть ли пользователь в базе (купил ли он ранее)."""
    return str(user_id) in db_load_all_user_ids()


# ═══════════════════════════════════════════════════════
#                       ТЕКСТЫ
# ═══════════════════════════════════════════════════════

def text_welcome_message(user_first_name: str) -> str:
    """Приветственное сообщение для команды /start."""
    return (
        f"Привет, {user_first_name} 👋\n\n"
        "🆓 Тут ты получишь ключи и подписки для разных клиентов таких как:\n"
        "<b>Hiddify, V2rayTun (NG, BOX), Nekobox, Happ и др.</b>\n\n"
        "📁 <b>Как получить?</b>\n"
        "1️⃣ Выбираешь подписку либо ключи\n"
        "2️⃣ Получаешь то или другое\n"
        "3️⃣ Копируешь выданное\n"
        "4️⃣ Вставляешь в любой клиент\n"
        "5️⃣ Пользуешься ✅"
    )

TEXT_SUBSCRIPTION_MENU = (
    "🔶 <b>Выберите тип подписки</b>\n\n"
    "❗️ Внимание: большая подписка может вызвать лаги на слабых устройствах."
)

TEXT_KEYS_MENU = (
    "🔷 <b>Выберите тип ключа</b>\n\n"
    "• <b>Lite 🏳️</b> — при белых списках\n"
    "• <b>Full 🏴</b> — при обычном использовании\n\n"
    "❗️ Не используйте <b>Lite 🏳️</b> на Wi-Fi"
)

TEXT_PREMIUM_INFO = (
    "💎 <b>Премиум подписка</b>\n\n"
    f"Стоимость: <b>{PREMIUM_PRICE_RUB} ₽</b>\n\n"
    "Что входит:\n"
    "• Стабильная подписка с большим пулом серверов\n"
    "• Персональная ссылка — вставляешь один раз в клиент\n"
    "• Ссылка работает только в VPN-клиенте (Hiddify, V2rayTun и др.)\n\n"
    "👇 Нажми <b>Оплатить</b> для получения ссылки на оплату."
)

TEXT_HELP_AND_TOS = (
    "📜 <b>ПОЛЬЗОВАТЕЛЬСКОЕ СОГЛАШЕНИЕ FreeCFGHub</b>\n\n"

    "<b>1. ОПРЕДЕЛЕНИЯ</b>\n"
    "1.1. Проект FreeCFGHub — некоммерческий канал, предоставляющий информацию "
    "о технологиях оптимизации сетевого трафика и ускорении доступа к цифровым сервисам.\n"
    "1.2. «Конфигурации» — наборы технических параметров, улучшающих качество соединения. "
    "Проект не является VPN-сервисом или прокси в юридическом смысле.\n"
    "1.3. Все материалы предоставляются в ознакомительных и образовательных целях.\n\n"

    "<b>2. ЦЕЛИ ПРОЕКТА</b>\n"
    "2.1. Помочь пользователям улучшить стабильность и скорость интернет-соединения.\n"
    "2.2. Проект не пропагандирует нарушение законодательства РФ и других стран.\n"
    "2.3. FreeCFGHub не является рекламой средств обхода блокировок.\n\n"

    "<b>3. ОТВЕТСТВЕННОСТЬ ПОЛЬЗОВАТЕЛЯ</b>\n"
    "3.1. Пользователь самостоятельно несёт ответственность за использование информации "
    "в соответствии с законами своего региона.\n"
    "3.2. Администрация не несёт ответственности за последствия использования конфигураций.\n"
    "3.3. Пользователь обязуется использовать конфигурации только для легальных целей.\n\n"

    "<b>4. ОТСУТСТВИЕ ГАРАНТИЙ</b>\n"
    "4.1. Все материалы предоставляются «как есть» (AS IS) без каких-либо гарантий.\n"
    "4.2. Работоспособность конфигураций не гарантируется — они могут устаревать "
    "или блокироваться третьими лицами.\n\n"

    "<b>5. АВТОРСКИЕ ПРАВА</b>\n"
    "5.1. Материалы Проекта являются собственностью администрации FreeCFGHub.\n"
    "5.2. Запрещено копирование, распространение или коммерческое использование "
    "без письменного согласия.\n\n"

    "<b>6. КОНФИДЕНЦИАЛЬНОСТЬ</b>\n"
    "6.1. Проект не собирает и не хранит персональные данные пользователей.\n"
    "6.2. Применяется политика конфиденциальности Telegram.\n\n"

    "<b>7. ЗАПРЕТ НА НЕЗАКОННЫЕ ДЕЙСТВИЯ</b>\n"
    "Запрещено использовать конфигурации для:\n"
    "• Распространения экстремистских материалов\n"
    "• Мошеннических действий\n"
    "• Организации DDoS-атак\n"
    "• Любой иной деятельности, запрещённой законодательством РФ\n\n"

    "<b>8. ИЗМЕНЕНИЕ УСЛОВИЙ</b>\n"
    "8.1. Администрация вправе изменять условия Соглашения без уведомления.\n"
    "8.2. Актуальная версия — в закреплённом сообщении канала.\n\n"

    "<b>9. ЗАКЛЮЧИТЕЛЬНЫЕ ПОЛОЖЕНИЯ</b>\n"
    "9.1. Использование материалов означает полное согласие с настоящим Соглашением.\n"
    "9.2. Если вы не согласны — прекратите использование материалов FreeCFGHub.\n"
    "9.3. Соглашение регулируется законодательством Российской Федерации.\n\n"
    f"📢 Канал: {PROJECT_CHANNEL_URL}"
)

TEXT_LOADING_STATUS = "⏳ Проверяю..."


# ═══════════════════════════════════════════════════════
#              ОБЁРТКИ ДЛЯ TELEGRAM API
# ═══════════════════════════════════════════════════════
# Все запросы к Telegram идут через эти три функции.
# Так проще: не надо везде повторять URL и parse_mode.

def telegram_get_updates(last_update_id=None) -> list:
    """
    Long-polling: запросить новые апдейты у Telegram.
    timeout=30 означает «держи соединение до 30 секунд, жди новых сообщений».
    Если пришли — сразу вернёт, иначе вернёт пустой список через 30 сек.
    """
    params = {"timeout": 30}
    if last_update_id:
        # offset = последний обработанный ID + 1, чтобы не получать дубли
        params["offset"] = last_update_id
    try:
        response = requests.get(
            f"{TELEGRAM_API_BASE}/getUpdates",
            params=params,
            timeout=35
        )
        return response.json().get("result", [])
    except Exception as error:
        print(f"Ошибка get_updates: {error}", flush=True)
        return []

def telegram_send_message(chat_id: int, text: str, reply_markup=None):
    """Отправить новое сообщение пользователю."""
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        requests.post(f"{TELEGRAM_API_BASE}/sendMessage", json=payload, timeout=10)
    except Exception as error:
        print(f"Ошибка send_message: {error}", flush=True)

def telegram_edit_message(chat_id: int, message_id: int, text: str, reply_markup=None):
    """
    Изменить уже существующее сообщение.
    Используется при нажатии кнопок — бот не шлёт новое, а редактирует текущее.
    Это создаёт ощущение «экранов» без мусора в чате.
    """
    payload = {
        "chat_id":    chat_id,
        "message_id": message_id,
        "text":       text,
        "parse_mode": "HTML"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        requests.post(f"{TELEGRAM_API_BASE}/editMessageText", json=payload, timeout=10)
    except Exception as error:
        print(f"Ошибка edit_message: {error}", flush=True)

def telegram_answer_callback(callback_query_id: str, popup_text: str = ""):
    """
    Ответить на нажатие кнопки — убирает «часики» на кнопке.
    Если передать popup_text — покажет всплывающее уведомление.
    Без вызова этой функции Telegram будет показывать лоадер на кнопке.
    """
    try:
        requests.post(f"{TELEGRAM_API_BASE}/answerCallbackQuery", json={
            "callback_query_id": callback_query_id,
            "text":              popup_text
        }, timeout=10)
    except Exception as error:
        print(f"Ошибка answer_callback: {error}", flush=True)

def telegram_set_bot_commands():
    """Зарегистрировать команды бота — они отображаются в меню / у пользователя."""
    commands = [
        {"command": "start",   "description": "🏠 Главное меню"},
        {"command": "sub",     "description": "📁 Получить подписку"},
        {"command": "keys",    "description": "🔑 Получить ключи"},
        {"command": "premium", "description": "💎 Премиум подписка"},
        {"command": "status",  "description": "📡 Статус"},
        {"command": "help",    "description": "ℹ️ Справка"},
    ]
    requests.post(f"{TELEGRAM_API_BASE}/setMyCommands", json={"commands": commands}, timeout=10)
    print("✅ Команды меню установлены", flush=True)


# ═══════════════════════════════════════════════════════
#                  INLINE-КЛАВИАТУРЫ
# ═══════════════════════════════════════════════════════
# Каждая функция возвращает словарь — Telegram понимает его как inline-клавиатуру.
# callback_data — строка, которая придёт в handle_callback при нажатии.

def keyboard_main_menu() -> dict:
    """Главное меню бота."""
    return {
        "inline_keyboard": [
            [{"text": "📁 Получить подписку", "callback_data": "menu_sub"}],
            [{"text": "🔑 Получить ключи",    "callback_data": "menu_keys"}],
            [{"text": "💎 Премиум подписка",  "callback_data": "menu_premium"}],
            [{"text": "ℹ️ Справка (ВАЖНО❗️)", "callback_data": "menu_help"}],
        ]
    }

def keyboard_subscription_types() -> dict:
    """Меню выбора размера подписки."""
    return {
        "inline_keyboard": [
            [{"text": "📦 Небольшая подписка (для слабых устройств)", "callback_data": "sub_small"}],
            [{"text": "🗂 Большая подписка (много ключей)",           "callback_data": "sub_big"}],
            [{"text": "◀️ Назад", "callback_data": "back_main"}],
        ]
    }

def keyboard_key_types() -> dict:
    """Меню выбора типа ключа (Lite / Full)."""
    return {
        "inline_keyboard": [
            [
                {"text": "Lite 🏳️", "callback_data": "keys_lite"},
                {"text": "Full 🏴",  "callback_data": "keys_full"},
            ],
            [{"text": "◀️ Назад", "callback_data": "back_main"}],
        ]
    }

def keyboard_premium_pay(payment_url: str) -> dict:
    """Кнопка оплаты — открывает внешний URL платёжной страницы."""
    return {
        "inline_keyboard": [
            [{"text": f"💳 Оплатить {PREMIUM_PRICE_RUB} ₽", "url": payment_url}],
            [{"text": "◀️ Назад", "callback_data": "back_main"}],
        ]
    }

def keyboard_back_to_main() -> dict:
    """Кнопка возврата в главное меню."""
    return {
        "inline_keyboard": [
            [{"text": "🏠 В главное меню", "callback_data": "back_main"}]
        ]
    }


# ═══════════════════════════════════════════════════════
#                  ПЛАТЁЖНАЯ СИСТЕМА (PLATEGA)
# ═══════════════════════════════════════════════════════

def create_platega_payment(telegram_user_id: int) -> tuple[str | None, str | None]:
    """
    Создать платёж в Platega.
    Возвращает (redirect_url, transaction_id) — ссылку на оплату и ID транзакции.
    При ошибке возвращает (None, None).

    Как работает:
    1. Мы шлём POST с суммой и user_id в payload
    2. Platega создаёт транзакцию и даёт нам redirect — ссылку для пользователя
    3. После оплаты Platega пошлёт POST на наш /payment/callback
    4. В callback мы идентифицируем пользователя по payload (user_id)
    """
    try:
        response = requests.post(
            f"{PLATEGA_API_BASE}/api/transactions",
            headers={
                "X-MerchantId": PLATEGA_MERCHANT_ID,
                "X-Secret":     PLATEGA_WEBHOOK_SECRET,
                "Content-Type": "application/json",
            },
            json={
                "paymentDetails": {
                    "amount":   PREMIUM_PRICE_RUB,
                    "currency": "RUB",
                },
                "description": f"Премиум подписка FreeCFGHub | TG:{telegram_user_id}",
                "return":      f"{PUBLIC_SERVER_URL}/payment/success",
                "failedUrl":   f"{PUBLIC_SERVER_URL}/payment/failed",
                "payload":     str(telegram_user_id),  # вернётся в callback — по нему найдём юзера
            },
            timeout=15,
        )
        response_data    = response.json()
        transaction_id   = response_data.get("transactionId")
        redirect_url     = response_data.get("redirect")

        print(f"Platega response: {response_data}", flush=True)

        if transaction_id and redirect_url:
            # Запоминаем кто платит, на случай если payload не придёт в callback
            pending_payment_user_ids[transaction_id] = telegram_user_id
            return redirect_url, transaction_id

        return None, None

    except Exception as error:
        print(f"Ошибка create_payment: {error}", flush=True)
        return None, None


# ═══════════════════════════════════════════════════════
#               ЗАГРУЗКА И ПАРСИНГ КЛЮЧЕЙ
# ═══════════════════════════════════════════════════════

def download_and_parse_vpn_keys() -> tuple[dict | None, str | None]:
    """
    Скачать файл с ключами и разобрать по типам: lite и full.

    Логика определения типа:
    - Если в строке ключа есть слово "Lite" → lite
    - Если есть "Full" или ничего не указано → full
    - Строки без валидного протокола (vless://, vmess://, ...) — пропускаем

    Возвращает: ({"lite": [...], "full": [...]}, None) или (None, "текст ошибки")
    """
    try:
        response = requests.get(KEYS_SOURCE_URL, timeout=15)
        if response.status_code != 200:
            return None, f"Ошибка загрузки: {response.status_code}"

        lite_keys = []
        full_keys = []

        for raw_line in response.text.splitlines():
            line = raw_line.strip()

            # Пропускаем пустые строки и комментарии
            if not line or line.startswith('#'):
                continue

            # Проверяем что строка — валидный VPN-ключ (начинается с протокола)
            valid_protocol = re.match(r'^(vless|vmess|trojan|ss|tuic|hysteria2)://', line)
            if not valid_protocol:
                continue

            # Определяем тип ключа по метке в строке
            if re.search(r'\bLite\b', line, re.IGNORECASE):
                lite_keys.append(line)
            else:
                # "Full" или без метки — считаем full
                full_keys.append(line)

        print(f"DEBUG: Lite={len(lite_keys)}, Full={len(full_keys)}", flush=True)
        return {"lite": lite_keys, "full": full_keys}, None

    except Exception as error:
        return None, str(error)


def pick_random_keys(all_keys: list, how_many: int) -> list:
    """Выбрать случайные ключи из списка. Если ключей меньше — вернуть все."""
    if not all_keys:
        return []
    return random.sample(all_keys, min(how_many, len(all_keys)))


def build_status_text() -> str:
    """Сформировать текст с количеством доступных ключей для команды /status."""
    parsed_keys, error = download_and_parse_vpn_keys()
    if error:
        return f"❌ Ошибка: {error}"
    return (
        f"📊 <b>Статус подписки</b>\n\n"
        f"🏳️ Lite ключей: {len(parsed_keys.get('lite', []))}\n"
        f"🏴 Full ключей: {len(parsed_keys.get('full', []))}\n\n"
        f"🔄 Обновляется автоматически\n\n"
        f"📢 {PROJECT_CHANNEL_URL}"
    )


# ═══════════════════════════════════════════════════════
#                  ОБРАБОТКА СООБЩЕНИЙ
# ═══════════════════════════════════════════════════════

def handle_message(message: dict):
    """
    Обработать текстовое сообщение от пользователя (команды /start, /sub и т.д.).
    Каждая команда показывает нужный экран с клавиатурой.
    """
    chat_id      = message.get("chat", {}).get("id")
    command_text = message.get("text", "")

    if not chat_id:
        return

    user_first_name = message.get("from", {}).get("first_name") or "друг"

    if command_text == "/start":
        telegram_send_message(chat_id, text_welcome_message(user_first_name),
                              reply_markup=keyboard_main_menu())

    elif command_text in ("/sub",):
        telegram_send_message(chat_id, TEXT_SUBSCRIPTION_MENU,
                              reply_markup=keyboard_subscription_types())

    elif command_text == "/keys":
        telegram_send_message(chat_id, TEXT_KEYS_MENU,
                              reply_markup=keyboard_key_types())

    elif command_text in ("/premium",):
        # Для команды нет message_id для редактирования — шлём новое
        _show_premium_screen(chat_id, message_id=None)

    elif command_text == "/status":
        telegram_send_message(chat_id, TEXT_LOADING_STATUS)
        telegram_send_message(chat_id, build_status_text())

    elif command_text in ("/help", "/info"):
        telegram_send_message(chat_id, TEXT_HELP_AND_TOS,
                              reply_markup=keyboard_back_to_main())


def _show_premium_screen(chat_id: int, message_id: int | None):
    """
    Создать платёж и показать экран с кнопкой оплаты.
    Если message_id передан — редактируем существующее сообщение,
    иначе отправляем новое (при вызове через команду /premium).
    """
    payment_url, transaction_id = create_platega_payment(chat_id)

    if not payment_url:
        error_text = "❌ Не удалось создать ссылку на оплату. Попробуй позже."
        if message_id:
            telegram_edit_message(chat_id, message_id, error_text,
                                  reply_markup=keyboard_back_to_main())
        else:
            telegram_send_message(chat_id, error_text,
                                  reply_markup=keyboard_back_to_main())
        return

    screen_text = TEXT_PREMIUM_INFO + f"\n\n🆔 ID транзакции: <code>{transaction_id}</code>"

    if message_id:
        telegram_edit_message(chat_id, message_id, screen_text,
                              reply_markup=keyboard_premium_pay(payment_url))
    else:
        telegram_send_message(chat_id, screen_text,
                              reply_markup=keyboard_premium_pay(payment_url))


# ═══════════════════════════════════════════════════════
#                  ОБРАБОТКА CALLBACK-КНОПОК
# ═══════════════════════════════════════════════════════

def handle_callback(callback_query: dict):
    """
    Обработать нажатие inline-кнопки.
    
    Telegram присылает объект callback_query с полем data — это строка,
    которую мы задали в callback_data при создании кнопки.
    По этой строке мы понимаем, какую «страницу» показать пользователю.
    
    Вместо отправки нового сообщения используем edit_message —
    так бот обновляет текущее сообщение без засорения чата.
    """
    chat_id      = callback_query["message"]["chat"]["id"]
    message_id   = callback_query["message"]["message_id"]
    button_data  = callback_query.get("data", "")
    sender_info  = callback_query.get("from", {})
    user_name    = sender_info.get("first_name") or "друг"

    # Обязательно подтверждаем нажатие — убирает лоадер с кнопки
    telegram_answer_callback(callback_query["id"])

    # ── Навигация ──────────────────────────────────────────────────

    if button_data == "back_main":
        telegram_edit_message(chat_id, message_id,
                              text_welcome_message(user_name),
                              reply_markup=keyboard_main_menu())

    elif button_data == "menu_sub":
        telegram_edit_message(chat_id, message_id,
                              TEXT_SUBSCRIPTION_MENU,
                              reply_markup=keyboard_subscription_types())

    elif button_data == "menu_keys":
        telegram_edit_message(chat_id, message_id,
                              TEXT_KEYS_MENU,
                              reply_markup=keyboard_key_types())

    elif button_data == "menu_premium":
        _show_premium_screen(chat_id, message_id)

    elif button_data == "menu_help":
        telegram_edit_message(chat_id, message_id,
                              TEXT_HELP_AND_TOS,
                              reply_markup=keyboard_back_to_main())

    # ── Подписки ───────────────────────────────────────────────────

    elif button_data == "sub_small":
        response_text = (
            "📦 <b>Небольшая подписка</b>\n\n"
            "Скопируй ссылку ниже и вставь в поле <b>«Подписка»</b> в своём клиенте "
            "(Hiddify, V2rayTun, Nekobox и др.):\n\n"
            f"<code>{SMALL_SUBSCRIPTION_URL}</code>\n\n"
            "✅ Ссылка обновляется автоматически — добавь один раз и пользуйся."
        )
        telegram_edit_message(chat_id, message_id, response_text,
                              reply_markup=keyboard_back_to_main())

    elif button_data == "sub_big":
        response_text = (
            "🗂 <b>Большая подписка</b>\n\n"
            "Скопируй ссылку ниже и вставь в поле <b>«Подписка»</b> в своём клиенте:\n\n"
            f"<code>{BIG_SUBSCRIPTION_URL}</code>\n\n"
            "⚠️ Много серверов — возможны лаги на слабых устройствах.\n"
            "✅ Ссылка обновляется автоматически."
        )
        telegram_edit_message(chat_id, message_id, response_text,
                              reply_markup=keyboard_back_to_main())

    # ── Ключи ──────────────────────────────────────────────────────

    elif button_data in ("keys_lite", "keys_full"):
        # Определяем тип запрошенных ключей
        is_lite_requested = (button_data == "keys_lite")
        key_type_id       = "lite" if is_lite_requested else "full"
        keys_to_show      = LITE_KEYS_COUNT if is_lite_requested else FULL_KEYS_COUNT
        display_label     = "Lite 🏳️" if is_lite_requested else "Full 🏴"
        wifi_warning      = "\n❗️ Не используй на Wi-Fi!" if is_lite_requested else ""

        # Показываем лоадер пока скачиваем ключи
        telegram_edit_message(chat_id, message_id, f"⏳ Загружаю {display_label} ключи...")

        parsed_keys, error = download_and_parse_vpn_keys()

        if error:
            telegram_edit_message(chat_id, message_id,
                                  f"❌ Не удалось загрузить ключи: {error}",
                                  reply_markup=keyboard_back_to_main())
            return

        available_keys = parsed_keys.get(key_type_id, [])

        if not available_keys:
            telegram_edit_message(chat_id, message_id,
                                  "😔 Ключи временно недоступны. Загляни позже!",
                                  reply_markup=keyboard_back_to_main())
            return

        selected_keys    = pick_random_keys(available_keys, keys_to_show)
        # Каждый ключ оборачиваем в <code> — чтобы по тапу копировался
        formatted_keys   = "\n\n".join(f"<code>{key}</code>" for key in selected_keys)

        telegram_edit_message(
            chat_id, message_id,
            f"🔑 <b>{display_label} — {len(selected_keys)} шт.</b>{wifi_warning}\n\n"
            f"{formatted_keys}\n\n"
            f"📋 Нажми на ключ чтобы скопировать, вставь в клиент.\n"
            f"📢 {PROJECT_CHANNEL_URL}",
            reply_markup=keyboard_back_to_main()
        )


# ═══════════════════════════════════════════════════════
#         FLASK — WEBHOOK PLATEGA + ПРОКСИ ПОДПИСКИ
# ═══════════════════════════════════════════════════════
# Flask запускается в отдельном потоке и слушает порт 8080.
# Он обрабатывает два типа запросов:
#   1. POST /payment/callback — от Platega после оплаты
#   2. GET  /sub/<token>      — от VPN-клиентов за подпиской

flask_app = Flask(__name__)

# Подстроки в User-Agent, по которым определяем VPN-клиент
KNOWN_VPN_CLIENT_AGENTS = [
    "hiddify", "v2raytun", "v2rayng", "nekobox", "clash",
    "sing-box", "xray", "v2fly", "shadowrocket", "quantumult",
    "surge", "stash", "loon", "streisand", "v2box",
]

def is_request_from_vpn_client(user_agent: str) -> bool:
    """Проверить, что запрос идёт из VPN-клиента, а не из браузера."""
    user_agent_lower = user_agent.lower()
    return any(agent in user_agent_lower for agent in KNOWN_VPN_CLIENT_AGENTS)


@flask_app.route("/sub/<subscription_token>", methods=["GET"])
def proxy_premium_subscription(subscription_token: str):
    """
    Прокси-эндпоинт для премиум подписки.

    Защита двухуровневая:
    1. Проверяем User-Agent — если браузер, отдаём 403 (скрываем URL)
    2. Проверяем токен в словаре active_premium_tokens — если нет, 404

    Если всё ок — скачиваем реальную подписку и проксируем содержимое.
    Это позволяет в любой момент сменить реальный URL без уведомления пользователей.
    """
    user_agent = request.headers.get("User-Agent", "")

    if not is_request_from_vpn_client(user_agent):
        abort(403)  # Браузер — ничего не показываем

    if subscription_token not in active_premium_tokens:
        abort(404)  # Неизвестный токен

    try:
        upstream_response = requests.get(PREMIUM_REAL_CONTENT_URL, timeout=15)
        return Response(
            upstream_response.content,
            status=200,
            headers={
                "Content-Type":        upstream_response.headers.get("Content-Type", "text/plain; charset=utf-8"),
                "Content-Disposition": "inline",
            }
        )
    except Exception as error:
        print(f"Ошибка прокси подписки: {error}", flush=True)
        abort(502)


@flask_app.route("/payment/callback", methods=["POST"])
def handle_payment_webhook():
    """
    Webhook от Platega — вызывается при смене статуса платежа.

    Проверяем подлинность запроса по заголовкам X-MerchantId и X-Secret.
    Если статус CONFIRMED — выдаём пользователю его персональный токен подписки.

    Поиск пользователя по приоритету:
    1. Из словаря pending_payment_user_ids по transaction_id
    2. Из поля payload в теле запроса (Platega возвращает то, что мы передали при создании)
    """
    incoming_merchant_id = request.headers.get("X-MerchantId", "")
    incoming_secret      = request.headers.get("X-Secret", "")

    # Проверяем что запрос реально от Platega
    if incoming_merchant_id != PLATEGA_MERCHANT_ID or incoming_secret != PLATEGA_WEBHOOK_SECRET:
        print("⚠️ Callback: неверная авторизация", flush=True)
        abort(403)

    webhook_data  = request.get_json(silent=True) or {}
    payment_status = webhook_data.get("status")
    transaction_id = webhook_data.get("id")

    print(f"📩 Platega callback: tx={transaction_id} status={payment_status}", flush=True)

    if payment_status == "CONFIRMED" and transaction_id:
        # Пробуем найти пользователя по transaction_id (наш словарь)
        paying_user_id = pending_payment_user_ids.pop(transaction_id, None)

        # Если не нашли — берём из payload (Platega возвращает его обратно)
        if not paying_user_id:
            try:
                paying_user_id = int(webhook_data.get("payload", "0"))
            except (ValueError, TypeError):
                paying_user_id = None

        if paying_user_id:
            db_save_user(paying_user_id)
            _deliver_premium_to_user(paying_user_id)

    return "", 200


@flask_app.route("/payment/success")
def payment_success_page():
    return "<h2>✅ Оплата прошла! Вернитесь в Telegram — бот уже выслал вашу подписку.</h2>", 200


@flask_app.route("/payment/failed")
def payment_failed_page():
    return "<h2>❌ Оплата не прошла. Вернитесь в Telegram и попробуйте ещё раз.</h2>", 200


def _deliver_premium_to_user(telegram_user_id: int):
    """
    Выдать пользователю персональную ссылку на подписку.

    Генерируем UUID без дефисов — это уникальный токен.
    Сохраняем в active_premium_tokens, чтобы /sub/<token> мог проверить доступ.
    Отправляем пользователю ссылку в Telegram.
    """
    unique_token = str(uuid.uuid4()).replace("-", "")
    active_premium_tokens[unique_token] = telegram_user_id

    personal_subscription_link = f"{PUBLIC_SERVER_URL}/sub/{unique_token}"

    telegram_send_message(
        telegram_user_id,
        "🎉 <b>Оплата подтверждена!</b>\n\n"
        "💎 Твоя персональная ссылка на подписку:\n\n"
        f"<code>{personal_subscription_link}</code>\n\n"
        "📋 Скопируй её и вставь в поле <b>«Подписка»</b> в своём клиенте "
        "(Hiddify, V2rayTun, Nekobox и др.).\n\n"
        "⚠️ Ссылка работает <b>только в VPN-клиенте</b>. "
        "При открытии в браузере — страница недоступна.\n\n"
        f"📢 {PROJECT_CHANNEL_URL}",
        reply_markup=keyboard_back_to_main()
    )
    print(f"💎 Премиум выдан: user={telegram_user_id} token={unique_token}", flush=True)


def run_flask_server():
    flask_app.run(host="0.0.0.0", port=8080, debug=False, use_reloader=False)


# ═══════════════════════════════════════════════════════
#                      MAIN LOOP
# ═══════════════════════════════════════════════════════

def main():
    print("🤖 Бот FreeCFGHub запущен", flush=True)
    telegram_set_bot_commands()

    # Flask запускаем в демон-потоке — он завершится вместе с основным процессом
    flask_thread = threading.Thread(target=run_flask_server, daemon=True)
    flask_thread.start()
    print("🌐 Flask-сервер запущен на порту 8080", flush=True)

    # Long-polling: постоянно опрашиваем Telegram на новые апдейты
    last_processed_update_id = None
    while True:
        incoming_updates = telegram_get_updates(last_processed_update_id)
        for update in incoming_updates:
            # Сдвигаем offset — чтобы это же обновление не пришло снова
            last_processed_update_id = update["update_id"] + 1
            try:
                if "message" in update:
                    handle_message(update["message"])
                elif "callback_query" in update:
                    handle_callback(update["callback_query"])
            except Exception as error:
                print(f"Ошибка обработки update: {error}", flush=True)


if __name__ == "__main__":
    main()

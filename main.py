#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import base64
import re
import os
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
from urllib.parse import urlparse

print("DEBUG: скрипт запущен", flush=True)

CHANNEL_TAG = "@FreeCFGHub"
CHECK_TIMEOUT = 3
CHECK_WORKERS = 100

WHITE_KEYWORDS = [
    r'\[\*CIDR\]', r'Lite', r'Белые?\s*списки?', r'White\s*List', r'WL'
]

def is_valid_config(line):
    return bool(re.match(r'^(vless|vmess|trojan|hysteria2|ss|tuic)://', line.strip()))

def fetch_from_url(url):
    configs = []
    try:
        r = requests.get(url.strip(), timeout=15)
        if r.status_code != 200:
            print(f"Ошибка {r.status_code} для {url}")
            return configs
        text = r.text.strip()
        if re.match(r'^[A-Za-z0-9+/=]+$', text) and len(text) > 50:
            try:
                decoded = base64.b64decode(text).decode('utf-8', errors='ignore')
                lines = decoded.splitlines()
            except:
                lines = text.splitlines()
        else:
            lines = text.splitlines()
        for line in lines:
            cleaned = line.strip()
            if not cleaned or cleaned.startswith('#'):
                continue
            if is_valid_config(cleaned):
                configs.append(cleaned)
    except Exception as e:
        print(f"Исключение при {url}: {e}")
    return configs

def extract_uuid(config):
    """Извлекает UUID из vless/vmess URI для дедупликации"""
    try:
        clean = config.split('#')[0]
        parsed = urlparse(clean)
        uuid = parsed.username  # в vless://UUID@host:port — UUID это username
        if uuid and re.match(r'^[0-9a-f-]{36}$', uuid, re.IGNORECASE):
            host = parsed.hostname
            port = parsed.port
            return f"{uuid}@{host}:{port}"  # уникальный ключ = UUID + сервер
    except Exception:
        pass
    return None

def deduplicate(configs):
    """Дедупликация по UUID+хост+порт, fallback — по полной строке"""
    unique = []
    seen_uuids = set()
    seen_raw = set()

    for config in configs:
        uid = extract_uuid(config)
        if uid:
            if uid not in seen_uuids:
                seen_uuids.add(uid)
                unique.append(config)
        else:
            raw = config.split('#')[0].strip()  # сравниваем без названия
            if raw not in seen_raw:
                seen_raw.add(raw)
                unique.append(config)

    return unique

def parse_host_port(config):
    try:
        clean = config.split('#')[0].strip()
        parsed = urlparse(clean)
        return parsed.hostname, parsed.port
    except Exception:
        return None, None

def check_key(config):
    host, port = parse_host_port(config)
    if not host or not port:
        return False
    try:
        sock = socket.create_connection((host, port), timeout=CHECK_TIMEOUT)
        sock.close()
        return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False

def check_all_keys(configs):
    alive = []
    total = len(configs)
    done = 0

    print(f"🔍 Проверка {total} ключей (потоков: {CHECK_WORKERS}, таймаут: {CHECK_TIMEOUT}s)...", flush=True)

    with ThreadPoolExecutor(max_workers=CHECK_WORKERS) as executor:
        future_to_config = {executor.submit(check_key, cfg): cfg for cfg in configs}
        for future in as_completed(future_to_config):
            cfg = future_to_config[future]
            done += 1
            try:
                ok = future.result()
            except Exception:
                ok = False
            if ok:
                alive.append(cfg)
            if done % 50 == 0 or done == total:
                print(f"   [{done}/{total}] живых: {len(alive)}", flush=True)

    return alive

def check_white(name):
    for pattern in WHITE_KEYWORDS:
        if re.search(pattern, name, re.IGNORECASE):
            return True
    return False

COUNTRY_MAP = {
    "RU": ("🇷🇺", "Россия"), "DE": ("🇩🇪", "Германия"), "NL": ("🇳🇱", "Нидерланды"),
    "FR": ("🇫🇷", "Франция"), "FI": ("🇫🇮", "Финляндия"), "SE": ("🇸🇪", "Швеция"),
    "NO": ("🇳🇴", "Норвегия"), "DK": ("🇩🇰", "Дания"), "EE": ("🇪🇪", "Эстония"),
    "LV": ("🇱🇻", "Латвия"), "LT": ("🇱🇹", "Литва"), "PL": ("🇵🇱", "Польша"),
    "CZ": ("🇨🇿", "Чехия"), "SK": ("🇸🇰", "Словакия"), "HU": ("🇭🇺", "Венгрия"),
    "AT": ("🇦🇹", "Австрия"), "CH": ("🇨🇭", "Швейцария"), "BE": ("🇧🇪", "Бельгия"),
    "GB": ("🇬🇧", "Великобритания"), "PT": ("🇵🇹", "Португалия"), "ES": ("🇪🇸", "Испания"),
    "IT": ("🇮🇹", "Италия"), "GR": ("🇬🇷", "Греция"), "BG": ("🇧🇬", "Болгария"),
    "RO": ("🇷🇴", "Румыния"), "UA": ("🇺🇦", "Украина"), "BY": ("🇧🇾", "Беларусь"),
    "KZ": ("🇰🇿", "Казахстан"), "GE": ("🇬🇪", "Грузия"), "AM": ("🇦🇲", "Армения"),
    "TR": ("🇹🇷", "Турция"), "CN": ("🇨🇳", "Китай"), "HK": ("🇭🇰", "Гонконг"),
    "JP": ("🇯🇵", "Япония"), "KR": ("🇰🇷", "Южная Корея"), "IN": ("🇮🇳", "Индия"),
    "SG": ("🇸🇬", "Сингапур"), "ID": ("🇮🇩", "Индонезия"), "MY": ("🇲🇾", "Малайзия"),
    "TH": ("🇹🇭", "Таиланд"), "VN": ("🇻🇳", "Вьетнам"), "PH": ("🇵🇭", "Филиппины"),
    "CA": ("🇨🇦", "Канада"), "US": ("🇺🇸", "США"), "MX": ("🇲🇽", "Мексика"),
    "BR": ("🇧🇷", "Бразилия"), "AR": ("🇦🇷", "Аргентина"), "AU": ("🇦🇺", "Австралия"),
    "NZ": ("🇳🇿", "Новая Зеландия"), "ZA": ("🇿🇦", "ЮАР"), "EG": ("🇪🇬", "Египет"),
}

def extract_flag_and_country(name):
    name_lower = name.lower()
    for code, (flag, country) in COUNTRY_MAP.items():
        if code.lower() in name_lower:
            return flag, country
    for code, (flag, country) in COUNTRY_MAP.items():
        if country.lower() in name_lower:
            return flag, country
    eng_names = {
        "russia": ("🇷🇺", "Россия"), "germany": ("🇩🇪", "Германия"),
        "netherlands": ("🇳🇱", "Нидерланды"), "france": ("🇫🇷", "Франция"),
        "finland": ("🇫🇮", "Финляндия"), "sweden": ("🇸🇪", "Швеция"),
        "poland": ("🇵🇱", "Польша"), "ukraine": ("🇺🇦", "Украина"),
        "usa": ("🇺🇸", "США"), "japan": ("🇯🇵", "Япония"),
        "turkey": ("🇹🇷", "Турция"), "kazakhstan": ("🇰🇿", "Казахстан"),
    }
    for eng, (flag, country) in eng_names.items():
        if eng in name_lower:
            return flag, country
    return "🌍", "Неизвестно"

def main():
    print("🚀 Запуск", flush=True)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    sources_path = os.path.join(script_dir, 'sources.txt')

    try:
        with open(sources_path, 'r', encoding='utf-8') as f:
            sources = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        print(f"📁 Источников: {len(sources)}", flush=True)
    except FileNotFoundError:
        print("❌ sources.txt не найден", flush=True)
        return

    all_configs = []
    for url in sources:
        print(f"📥 Загрузка: {url}", flush=True)
        configs = fetch_from_url(url)
        print(f"   Получено: {len(configs)}", flush=True)
        all_configs.extend(configs)

    # Дедупликация по UUID+хост+порт
    unique_configs = deduplicate(all_configs)
    print(f"📊 Уникальных: {len(unique_configs)} (дубликатов удалено: {len(all_configs) - len(unique_configs)})", flush=True)

    # Проверка живых
    alive_configs = check_all_keys(unique_configs)
    print(f"✅ Живых: {len(alive_configs)} | ❌ Мёртвых: {len(unique_configs) - len(alive_configs)}", flush=True)

    # Разделяем на Lite / Full
    lite_configs = []
    full_configs = []
    for line in alive_configs:
        match = re.search(r'#(.+)$', line)
        name = match.group(1) if match else ""
        if check_white(name):
            lite_configs.append(line)
        else:
            full_configs.append(line)

    result_lines = []

    if lite_configs:
        lite_by_country = defaultdict(list)
        for line in lite_configs:
            match = re.search(r'#(.+)$', line)
            name = match.group(1) if match else ""
            flag, country = extract_flag_and_country(name)
            lite_by_country[(flag, country)].append(line)

        result_lines.append("🏳️ Lite (оптимизированный режим)")
        result_lines.append("")
        idx = 1
        for (flag, country), lines in sorted(lite_by_country.items(), key=lambda x: x[0][1]):
            result_lines.append(f"{flag} {country}")
            for line in lines:
                new_name = f"Lite #{idx:03d} {CHANNEL_TAG}"
                new_line = re.sub(r'#.+$', f'#{new_name}', line)
                result_lines.append(new_line)
                idx += 1
            result_lines.append("")

    if full_configs:
        result_lines.append("🏴 Full (полный доступ)")
        result_lines.append("")
        idx = 1
        for line in full_configs:
            new_name = f"Full #{idx:03d} {CHANNEL_TAG}"
            new_line = re.sub(r'#.+$', f'#{new_name}', line)
            result_lines.append(new_line)
            idx += 1
        result_lines.append("")

    os.makedirs('subscriptions', exist_ok=True)
    output_text = '\n'.join(result_lines)

    with open('subscriptions/FreeCFGHub.txt', 'w', encoding='utf-8') as f:
        f.write(output_text)

    if output_text.strip():
        b64 = base64.b64encode(output_text.encode('utf-8')).decode('utf-8')
        with open('subscriptions/all_base64.txt', 'w', encoding='utf-8') as f:
            f.write(b64)

    print(f"✅ Готово | Lite: {len(lite_configs)} | Full: {len(full_configs)}", flush=True)

if __name__ == '__main__':
    main()

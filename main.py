#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import requests
import base64
import re
import socket
from datetime import datetime
import os
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

print("DEBUG 1: скрипт начал работу", flush=True)

CHANNEL_TAG = "@FreeCFGHub"
CHECK_TIMEOUT = 5
MAX_WORKERS = 20

WHITE_KEYWORDS = [
    r'\[\*CIDR\]', r'Обход', r'Белые?\s*списки?', r'White\s*List', r'WL', r'Обход глушилок'
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

def extract_hostname_and_port(config):
    match = re.search(r'vless://[^@]+@([^:]+):(\d+)', config)
    if match:
        return match.group(1), int(match.group(2))
    if config.startswith('vmess://'):
        try:
            import json
            b64_data = config[8:]
            padding = 4 - len(b64_data) % 4
            if padding != 4:
                b64_data += "=" * padding
            decoded = base64.urlsafe_b64decode(b64_data).decode('utf-8')
            data = json.loads(decoded)
            return data.get('add'), int(data.get('port'))
        except:
            pass
    return None, None

def check_tcp_connection(host, port):
    if not host or not port:
        return False
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(CHECK_TIMEOUT)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except:
        return False

def check_config(config):
    host, port = extract_hostname_and_port(config)
    if host and port:
        is_alive = check_tcp_connection(host, port)
        return config, is_alive
    return config, False

COUNTRY_MAP = {
    "RU": "Россия", "DE": "Германия", "NL": "Нидерланды", "FR": "Франция",
    "FI": "Финляндия", "SE": "Швеция", "NO": "Норвегия", "EE": "Эстония",
    "LV": "Латвия", "LT": "Литва", "PL": "Польша", "GB": "Великобритания",
    "US": "США", "JP": "Япония", "KZ": "Казахстан", "TR": "Турция",
    "CA": "Канада", "AU": "Австралия", "BR": "Бразилия", "IN": "Индия",
    "CH": "Швейцария", "AT": "Австрия", "CZ": "Чехия", "DK": "Дания",
    "HK": "Гонконг", "SG": "Сингапур", "IT": "Италия", "ES": "Испания"
}

def extract_flag_and_country(name):
    flag_match = re.search(r'[🇦-🇿]{2}', name)
    flag = flag_match.group() if flag_match else "🌍"
    name_lower = name.lower()
    for code, country in COUNTRY_MAP.items():
        if code.lower() in name_lower or country.lower() in name_lower:
            return flag, country
    return flag, "Неизвестно"

def check_white(name):
    for pattern in WHITE_KEYWORDS:
        if re.search(pattern, name, re.IGNORECASE):
            return True
    return False

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

    unique_configs = list(dict.fromkeys(all_configs))
    print(f"📊 Уникальных: {len(unique_configs)}", flush=True)
    
    print(f"🔍 Проверка {len(unique_configs)} ключей...", flush=True)
    working_configs = []
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(check_config, config): config for config in unique_configs}
        for i, future in enumerate(as_completed(futures), 1):
            config, is_alive = future.result()
            if is_alive:
                working_configs.append(config)
            if i % 50 == 0:
                print(f"   Прогресс: {i}/{len(unique_configs)}", flush=True)
    
    print(f"✅ Рабочих ключей: {len(working_configs)}", flush=True)
    
    white = defaultdict(list)
    black = defaultdict(list)
    
    for line in working_configs:
        match = re.search(r'#(.+)$', line)
        if not match:
            continue
        name = match.group(1)
        flag, country = extract_flag_and_country(name)
        is_white = check_white(name)
        if is_white:
            white[(flag, country)].append(line)
        else:
            black[(flag, country)].append(line)
    
    result_lines = []
    
    if white:
        result_lines.append("🏳️ Белые списки")
        result_lines.append("")
        idx = 1
        for (flag, country), lines in sorted(white.items(), key=lambda x: x[0][1]):
            result_lines.append(f"{flag} {country}")
            for line in lines:
                new_name = f"{flag}{country} {idx:03d} {CHANNEL_TAG}"
                new_line = re.sub(r'#.+$', f'#{new_name}', line)
                result_lines.append(new_line)
                idx += 1
            result_lines.append("")
    
    if black:
        result_lines.append("🏴 Чёрные списки")
        result_lines.append("")
        idx = 1
        for (flag, country), lines in sorted(black.items(), key=lambda x: x[0][1]):
            for line in lines:
                new_name = f"{flag}{country} {idx:03d} {CHANNEL_TAG}"
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
        print(f"✅ Сохранено {len(working_configs)} ключей", flush=True)
    
    print("✅ Готово", flush=True)

if __name__ == '__main__':
    main()

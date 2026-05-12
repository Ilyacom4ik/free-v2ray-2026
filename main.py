#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import requests
import base64
import re
import os
import json
from collections import defaultdict

print("DEBUG: скрипт запущен", flush=True)

CHANNEL_TAG = "@FreeCFGHub"

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
        
        # Проверяем base64
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

def check_white(name):
    for pattern in WHITE_KEYWORDS:
        if re.search(pattern, name, re.IGNORECASE):
            return True
    return False

def main():
    print("🚀 Запуск (только удаление дубликатов, без проверки)", flush=True)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    sources_path = os.path.join(script_dir, 'sources.txt')
    
    try:
        with open(sources_path, 'r', encoding='utf-8') as f:
            sources = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        print(f"📁 Источников: {len(sources)}", flush=True)
    except FileNotFoundError:
        print("❌ sources.txt не найден", flush=True)
        return

    # Собираем все конфиги
    all_configs = []
    for url in sources:
        print(f"📥 Загрузка: {url}", flush=True)
        configs = fetch_from_url(url)
        print(f"   Получено: {len(configs)}", flush=True)
        all_configs.extend(configs)

    # Удаляем дубликаты
    unique_configs = []
    seen = set()
    for config in all_configs:
        if config not in seen:
            seen.add(config)
            unique_configs.append(config)
    
    print(f"📊 Уникальных: {len(unique_configs)} (дубликатов: {len(all_configs) - len(unique_configs)})", flush=True)

    # Разделяем на Lite и Full по ключевым словам
    lite_configs = []
    full_configs = []
    
    for line in unique_configs:
        match = re.search(r'#(.+)$', line)
        if not match:
            full_configs.append(line)
            continue
        name = match.group(1)
        if check_white(name):
            lite_configs.append(line)
        else:
            full_configs.append(line)
    
    result_lines = []
    
    # Lite раздел
    if lite_configs:
        result_lines.append("🏳️ Lite (оптимизированный режим)")
        result_lines.append("")
        idx = 1
        for line in lite_configs:
            new_name = f"Lite #{idx:03d} {CHANNEL_TAG}"
            new_line = re.sub(r'#.+$', f'#{new_name}', line)
            result_lines.append(new_line)
            idx += 1
        result_lines.append("")
    
    # Full раздел
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
    
    # Создаём папку
    os.makedirs('subscriptions', exist_ok=True)
    output_text = '\n'.join(result_lines)
    
    # Сохраняем plain текст
    with open('subscriptions/FreeCFGHub.txt', 'w', encoding='utf-8') as f:
        f.write(output_text)
    
    # Сохраняем base64 (для обратной совместимости)
    if output_text.strip():
        b64 = base64.b64encode(output_text.encode('utf-8')).decode('utf-8')
        with open('subscriptions/all_base64.txt', 'w', encoding='utf-8') as f:
            f.write(b64)
        print(f"✅ Сохранено {len(unique_configs)} ключей", flush=True)
        print(f"   Lite: {len(lite_configs)}, Full: {len(full_configs)}", flush=True)
    
    print("✅ Готово", flush=True)

if __name__ == '__main__':
    main()

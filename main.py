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

print("DEBUG: скрипт запущен", flush=True)

CHANNEL_TAG = "@FreeCFGHub"
CHECK_TIMEOUT = 5
MAX_WORKERS = 20

# Изменено: теперь проверяем на Lite и Full (старые названия не трогаем)
# Но можно оставить и старые для обратной совместимости
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

# 100+ стран с правильными флагами и названиями
COUNTRY_MAP = {
    # Европа
    "RU": ("🇷🇺", "Россия"), "DE": ("🇩🇪", "Германия"), "NL": ("🇳🇱", "Нидерланды"),
    "FR": ("🇫🇷", "Франция"), "FI": ("🇫🇮", "Финляндия"), "SE": ("🇸🇪", "Швеция"),
    "NO": ("🇳🇴", "Норвегия"), "DK": ("🇩🇰", "Дания"), "EE": ("🇪🇪", "Эстония"),
    "LV": ("🇱🇻", "Латвия"), "LT": ("🇱🇹", "Литва"), "PL": ("🇵🇱", "Польша"),
    "CZ": ("🇨🇿", "Чехия"), "SK": ("🇸🇰", "Словакия"), "HU": ("🇭🇺", "Венгрия"),
    "AT": ("🇦🇹", "Австрия"), "CH": ("🇨🇭", "Швейцария"), "BE": ("🇧🇪", "Бельгия"),
    "LU": ("🇱🇺", "Люксембург"), "IE": ("🇮🇪", "Ирландия"), "GB": ("🇬🇧", "Великобритания"),
    "PT": ("🇵🇹", "Португалия"), "ES": ("🇪🇸", "Испания"), "IT": ("🇮🇹", "Италия"),
    "SI": ("🇸🇮", "Словения"), "HR": ("🇭🇷", "Хорватия"), "BA": ("🇧🇦", "Босния"),
    "RS": ("🇷🇸", "Сербия"), "ME": ("🇲🇪", "Черногория"), "MK": ("🇲🇰", "Македония"),
    "AL": ("🇦🇱", "Албания"), "GR": ("🇬🇷", "Греция"), "BG": ("🇧🇬", "Болгария"),
    "RO": ("🇷🇴", "Румыния"), "MD": ("🇲🇩", "Молдова"), "UA": ("🇺🇦", "Украина"),
    "BY": ("🇧🇾", "Беларусь"), "GE": ("🇬🇪", "Грузия"), "AM": ("🇦🇲", "Армения"),
    "AZ": ("🇦🇿", "Азербайджан"), "TR": ("🇹🇷", "Турция"), "CY": ("🇨🇾", "Кипр"),
    "MT": ("🇲🇹", "Мальта"), "IS": ("🇮🇸", "Исландия"), "LI": ("🇱🇮", "Лихтенштейн"),
    "MC": ("🇲🇨", "Монако"), "AD": ("🇦🇩", "Андорра"),
    
    # Азия
    "CN": ("🇨🇳", "Китай"), "HK": ("🇭🇰", "Гонконг"), "MO": ("🇲🇴", "Макао"),
    "TW": ("🇹🇼", "Тайвань"), "JP": ("🇯🇵", "Япония"), "KR": ("🇰🇷", "Южная Корея"),
    "KP": ("🇰🇵", "Северная Корея"), "MN": ("🇲🇳", "Монголия"), "IN": ("🇮🇳", "Индия"),
    "PK": ("🇵🇰", "Пакистан"), "BD": ("🇧🇩", "Бангладеш"), "LK": ("🇱🇰", "Шри-Ланка"),
    "NP": ("🇳🇵", "Непал"), "BT": ("🇧🇹", "Бутан"), "MV": ("🇲🇻", "Мальдивы"),
    "MM": ("🇲🇲", "Мьянма"), "TH": ("🇹🇭", "Таиланд"), "LA": ("🇱🇦", "Лаос"),
    "KH": ("🇰🇭", "Камбоджа"), "VN": ("🇻🇳", "Вьетнам"), "MY": ("🇲🇾", "Малайзия"),
    "SG": ("🇸🇬", "Сингапур"), "ID": ("🇮🇩", "Индонезия"), "PH": ("🇵🇭", "Филиппины"),
    "BN": ("🇧🇳", "Бруней"), "TL": ("🇹🇱", "Восточный Тимор"), "KZ": ("🇰🇿", "Казахстан"),
    "KG": ("🇰🇬", "Киргизия"), "TJ": ("🇹🇯", "Таджикистан"), "UZ": ("🇺🇿", "Узбекистан"),
    "TM": ("🇹🇲", "Туркменистан"), "AF": ("🇦🇫", "Афганистан"), "IR": ("🇮🇷", "Иран"),
    "IQ": ("🇮🇶", "Ирак"), "SA": ("🇸🇦", "Саудовская Аравия"), "YE": ("🇾🇪", "Йемен"),
    "OM": ("🇴🇲", "Оман"), "AE": ("🇦🇪", "ОАЭ"), "QA": ("🇶🇦", "Катар"),
    "BH": ("🇧🇭", "Бахрейн"), "KW": ("🇰🇼", "Кувейт"), "JO": ("🇯🇴", "Иордания"),
    "LB": ("🇱🇧", "Ливан"), "SY": ("🇸🇾", "Сирия"), "IL": ("🇮🇱", "Израиль"),
    "PS": ("🇵🇸", "Палестина"),
    
    # Америка
    "CA": ("🇨🇦", "Канада"), "US": ("🇺🇸", "США"), "MX": ("🇲🇽", "Мексика"),
    "GT": ("🇬🇹", "Гватемала"), "BZ": ("🇧🇿", "Белиз"), "SV": ("🇸🇻", "Сальвадор"),
    "HN": ("🇭🇳", "Гондурас"), "NI": ("🇳🇮", "Никарагуа"), "CR": ("🇨🇷", "Коста-Рика"),
    "PA": ("🇵🇦", "Панама"), "CU": ("🇨🇺", "Куба"), "JM": ("🇯🇲", "Ямайка"),
    "HT": ("🇭🇹", "Гаити"), "DO": ("🇩🇴", "Доминикана"), "PR": ("🇵🇷", "Пуэрто-Рико"),
    "BS": ("🇧🇸", "Багамы"), "TT": ("🇹🇹", "Тринидад"), "BB": ("🇧🇧", "Барбадос"),
    "LC": ("🇱🇨", "Сент-Люсия"), "VC": ("🇻🇨", "Сент-Винсент"), "GD": ("🇬🇩", "Гренада"),
    "AG": ("🇦🇬", "Антигуа"), "DM": ("🇩🇲", "Доминика"), "KN": ("🇰🇳", "Сент-Китс"),
    "CO": ("🇨🇴", "Колумбия"), "VE": ("🇻🇪", "Венесуэла"), "GY": ("🇬🇾", "Гайана"),
    "SR": ("🇸🇷", "Суринам"), "BR": ("🇧🇷", "Бразилия"), "EC": ("🇪🇨", "Эквадор"),
    "PE": ("🇵🇪", "Перу"), "BO": ("🇧🇴", "Боливия"), "PY": ("🇵🇾", "Парагвай"),
    "CL": ("🇨🇱", "Чили"), "AR": ("🇦🇷", "Аргентина"), "UY": ("🇺🇾", "Уругвай"),
    
    # Австралия и Океания
    "AU": ("🇦🇺", "Австралия"), "NZ": ("🇳🇿", "Новая Зеландия"), "PG": ("🇵🇬", "Папуа-Новая Гвинея"),
    "SB": ("🇸🇧", "Соломоновы острова"), "FJ": ("🇫🇯", "Фиджи"), "VU": ("🇻🇺", "Вануату"),
    "NC": ("🇳🇨", "Новая Каледония"), "PF": ("🇵🇫", "Французская Полинезия"), "WS": ("🇼🇸", "Самоа"),
    "TO": ("🇹🇴", "Тонга"), "KI": ("🇰🇮", "Кирибати"), "FM": ("🇫🇲", "Микронезия"),
    "MH": ("🇲🇭", "Маршалловы острова"), "PW": ("🇵🇼", "Палау"), "NR": ("🇳🇷", "Науру"),
    "TV": ("🇹🇻", "Тувалу"),
    
    # Африка
    "EG": ("🇪🇬", "Египет"), "LY": ("🇱🇾", "Ливия"), "TN": ("🇹🇳", "Тунис"),
    "DZ": ("🇩🇿", "Алжир"), "MA": ("🇲🇦", "Марокко"), "ZA": ("🇿🇦", "ЮАР"),
    "NG": ("🇳🇬", "Нигерия"), "KE": ("🇰🇪", "Кения"), "GH": ("🇬🇭", "Гана"),
}

def extract_flag_and_country(name):
    """Определяет флаг и страну по названию ключа"""
    name_lower = name.lower()
    
    # Сначала ищем по коду страны (RU, DE, US и т.д.)
    for code, (flag, country) in COUNTRY_MAP.items():
        if code.lower() in name_lower:
            return flag, country
    
    # Потом ищем по русскому названию
    for code, (flag, country) in COUNTRY_MAP.items():
        if country.lower() in name_lower:
            return flag, country
    
    # Потом ищем по английскому названию
    eng_names = {
        "russia": ("🇷🇺", "Россия"), "germany": ("🇩🇪", "Германия"),
        "netherlands": ("🇳🇱", "Нидерланды"), "france": ("🇫🇷", "Франция"),
        "finland": ("🇫🇮", "Финляндия"), "sweden": ("🇸🇪", "Швеция"),
        "norway": ("🇳🇴", "Норвегия"), "estonia": ("🇪🇪", "Эстония"),
        "latvia": ("🇱🇻", "Латвия"), "lithuania": ("🇱🇹", "Литва"),
        "poland": ("🇵🇱", "Польша"), "ukraine": ("🇺🇦", "Украина"),
        "italy": ("🇮🇹", "Италия"), "spain": ("🇪🇸", "Испания"),
        "japan": ("🇯🇵", "Япония"), "usa": ("🇺🇸", "США"),
        "canada": ("🇨🇦", "Канада"), "brazil": ("🇧🇷", "Бразилия"),
        "india": ("🇮🇳", "Индия"), "china": ("🇨🇳", "Китай"),
        "turkey": ("🇹🇷", "Турция"), "kazakhstan": ("🇰🇿", "Казахстан"),
    }
    for eng, (flag, country) in eng_names.items():
        if eng in name_lower:
            return flag, country
    
    # Если есть флаг в названии — берём его
    flag_match = re.search(r'[🇦-🇿]{2}', name)
    if flag_match:
        flag = flag_match.group()
        return flag, "Неизвестно"
    
    return "🌍", "Неизвестно"

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
    
    # Разделяем на Lite (бывшие белые) и Full (бывшие черные)
    lite_configs = []   # то что было white
    full_configs = []   # то что было black
    
    for line in working_configs:
        match = re.search(r'#(.+)$', line)
        if not match:
            # Если нет имени, отправляем в Full как есть
            full_configs.append(line)
            continue
        name = match.group(1)
        is_white = check_white(name)
        if is_white:
            lite_configs.append(line)
        else:
            full_configs.append(line)
    
    result_lines = []
    
    # Сортируем Lite по странам (как было с белыми)
    if lite_configs:
        lite_by_country = defaultdict(list)
        for line in lite_configs:
            match = re.search(r'#(.+)$', line)
            if match:
                name = match.group(1)
                flag, country = extract_flag_and_country(name)
                lite_by_country[(flag, country)].append(line)
            else:
                lite_by_country[("🌍", "Неизвестно")].append(line)
        
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
    
    # Full без группировки по странам (как было с черными)
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
    
    # Создаем папку если нет
    os.makedirs('subscriptions', exist_ok=True)
    output_text = '\n'.join(result_lines)
    
    # Сохраняем plain текст
    with open('subscriptions/FreeCFGHub.txt', 'w', encoding='utf-8') as f:
        f.write(output_text)
    
    # Сохраняем base64 (сразу, без задержки)
    if output_text.strip():
        b64 = base64.b64encode(output_text.encode('utf-8')).decode('utf-8')
        with open('subscriptions/all_base64.txt', 'w', encoding='utf-8') as f:
            f.write(b64)
        print(f"✅ Сохранено {len(working_configs)} ключей", flush=True)
        print(f"   Lite: {len(lite_configs)}, Full: {len(full_configs)}", flush=True)
    
    print("✅ Готово", flush=True)

if __name__ == '__main__':
    main()

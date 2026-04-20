#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
print("DEBUG 1: скрипт начал работу", flush=True)
sys.stdout.flush()

print("DEBUG 2: импортирую requests", flush=True)
import requests
print("DEBUG 2.1: requests ok", flush=True)

print("DEBUG 3: импортирую base64", flush=True)
import base64
print("DEBUG 3.1: base64 ok", flush=True)

print("DEBUG 4: импортирую re", flush=True)
import re
print("DEBUG 4.1: re ok", flush=True)

print("DEBUG 5: импортирую socket", flush=True)
import socket
print("DEBUG 5.1: socket ok", flush=True)

print("DEBUG 6: импортирую datetime", flush=True)
from datetime import datetime
print("DEBUG 6.1: datetime ok", flush=True)

print("DEBUG 7: импортирую os", flush=True)
import os
print("DEBUG 7.1: os ok", flush=True)

print("DEBUG 8: импортирую defaultdict", flush=True)
from collections import defaultdict
print("DEBUG 8.1: defaultdict ok", flush=True)

print("DEBUG 9: импортирую ThreadPoolExecutor", flush=True)
from concurrent.futures import ThreadPoolExecutor, as_completed
print("DEBUG 9.1: ThreadPoolExecutor ok", flush=True)

print("START", flush=True)
print("🚀 Запуск", flush=True)

# Дальше остальной код...
import requests
import base64
import re
import socket
from datetime import datetime
import os
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

print("START")

CHANNEL_TAG = "@FreeCFGHub"
CHECK_TIMEOUT = 5
MAX_WORKERS = 20

# Ключевые слова для белого списка 🏳️
WHITE_KEYWORDS = [
    r'\[\*CIDR\]', r'Обход', r'Белые?\s*списки?', r'White\s*List', r'WL', r'Обход глушилок'
]

def is_valid_config(line):
    return bool(re.match(r'^(vless|vmess|trojan|hysteria2|ss|tuic)://', line.strip()))

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

# Полный список стран мира (193 страны + несколько дополнительных)
COUNTRY_MAP = {
    # Европа (50+ стран)
    "RU": "Россия", "DE": "Германия", "NL": "Нидерланды", "FR": "Франция",
    "FI": "Финляндия", "SE": "Швеция", "NO": "Норвегия", "DK": "Дания",
    "EE": "Эстония", "LV": "Латвия", "LT": "Литва", "PL": "Польша",
    "CZ": "Чехия", "SK": "Словакия", "HU": "Венгрия", "AT": "Австрия",
    "CH": "Швейцария", "BE": "Бельгия", "LU": "Люксембург", "IE": "Ирландия",
    "GB": "Великобритания", "PT": "Португалия", "ES": "Испания", "IT": "Италия",
    "SI": "Словения", "HR": "Хорватия", "BA": "Босния и Герцеговина", "RS": "Сербия",
    "ME": "Черногория", "MK": "Северная Македония", "AL": "Албания", "GR": "Греция",
    "BG": "Болгария", "RO": "Румыния", "MD": "Молдова", "UA": "Украина",
    "BY": "Беларусь", "GE": "Грузия", "AM": "Армения", "AZ": "Азербайджан",
    "TR": "Турция", "CY": "Кипр", "MT": "Мальта", "IS": "Исландия",
    "LI": "Лихтенштейн", "MC": "Монако", "SM": "Сан-Марино", "VA": "Ватикан",
    "AD": "Андорра", "GI": "Гибралтар", "FO": "Фарерские острова", "GG": "Гернси",
    "JE": "Джерси", "IM": "Остров Мэн", "SX": "Синт-Мартен", "MF": "Сен-Мартен",
    
    # Азия (50+ стран)
    "CN": "Китай", "HK": "Гонконг", "MO": "Макао", "TW": "Тайвань",
    "JP": "Япония", "KR": "Южная Корея", "KP": "Северная Корея", "MN": "Монголия",
    "IN": "Индия", "PK": "Пакистан", "BD": "Бангладеш", "LK": "Шри-Ланка",
    "NP": "Непал", "BT": "Бутан", "MV": "Мальдивы", "MM": "Мьянма",
    "TH": "Таиланд", "LA": "Лаос", "KH": "Камбоджа", "VN": "Вьетнам",
    "MY": "Малайзия", "SG": "Сингапур", "ID": "Индонезия", "PH": "Филиппины",
    "BN": "Бруней", "TL": "Восточный Тимор", "KZ": "Казахстан", "KG": "Киргизия",
    "TJ": "Таджикистан", "UZ": "Узбекистан", "TM": "Туркменистан", "AF": "Афганистан",
    "IR": "Иран", "IQ": "Ирак", "SA": "Саудовская Аравия", "YE": "Йемен",
    "OM": "Оман", "AE": "ОАЭ", "QA": "Катар", "BH": "Бахрейн",
    "KW": "Кувейт", "JO": "Иордания", "LB": "Ливан", "SY": "Сирия",
    "IL": "Израиль", "PS": "Палестина", "AM": "Армения", "AZ": "Азербайджан",
    
    # Африка (50+ стран)
    "EG": "Египет", "LY": "Ливия", "TN": "Тунис", "DZ": "Алжир",
    "MA": "Марокко", "EH": "Западная Сахара", "MR": "Мавритания", "SN": "Сенегал",
    "GM": "Гамбия", "GW": "Гвинея-Бисау", "GN": "Гвинея", "SL": "Сьерра-Леоне",
    "LR": "Либерия", "CI": "Кот-д'Ивуар", "BF": "Буркина-Фасо", "GH": "Гана",
    "TG": "Того", "BJ": "Бенин", "NG": "Нигерия", "NE": "Нигер",
    "ML": "Мали", "TD": "Чад", "SD": "Судан", "SS": "Южный Судан",
    "ER": "Эритрея", "DJ": "Джибути", "SO": "Сомали", "ET": "Эфиопия",
    "KE": "Кения", "UG": "Уганда", "RW": "Руанда", "BI": "Бурунди",
    "TZ": "Танзания", "MZ": "Мозамбик", "MW": "Малави", "ZM": "Замбия",
    "ZW": "Зимбабве", "NA": "Намибия", "BW": "Ботсвана", "ZA": "ЮАР",
    "SZ": "Эсватини", "LS": "Лесото", "MG": "Мадагаскар", "KM": "Коморы",
    "MU": "Маврикий", "SC": "Сейшелы", "CV": "Кабо-Верде", "ST": "Сан-Томе и Принсипи",
    "GQ": "Экваториальная Гвинея", "GA": "Габон", "CG": "Республика Конго",
    "CD": "ДР Конго", "CF": "ЦАР", "CM": "Камерун", "AO": "Ангола",
    
    # Северная и Южная Америка (30+ стран)
    "CA": "Канада", "US": "США", "MX": "Мексика", "GL": "Гренландия",
    "GT": "Гватемала", "BZ": "Белиз", "SV": "Сальвадор", "HN": "Гондурас",
    "NI": "Никарагуа", "CR": "Коста-Рика", "PA": "Панама", "CU": "Куба",
    "JM": "Ямайка", "HT": "Гаити", "DO": "Доминиканская Республика", "PR": "Пуэрто-Рико",
    "BS": "Багамы", "TT": "Тринидад и Тобаго", "BB": "Барбадос", "LC": "Сент-Люсия",
    "VC": "Сент-Винсент и Гренадины", "GD": "Гренада", "AG": "Антигуа и Барбуда",
    "DM": "Доминика", "KN": "Сент-Китс и Невис", "CO": "Колумбия", "VE": "Венесуэла",
    "GY": "Гайана", "SR": "Суринам", "GF": "Французская Гвиана", "BR": "Бразилия",
    "EC": "Эквадор", "PE": "Перу", "BO": "Боливия", "PY": "Парагвай",
    "CL": "Чили", "AR": "Аргентина", "UY": "Уругвай", "FK": "Фолклендские острова",
    
    # Австралия и Океания (15+ стран)
    "AU": "Австралия", "NZ": "Новая Зеландия", "PG": "Папуа-Новая Гвинея",
    "SB": "Соломоновы острова", "FJ": "Фиджи", "VU": "Вануату", "NC": "Новая Каледония",
    "PF": "Французская Полинезия", "WS": "Самоа", "TO": "Тонга", "KI": "Кирибати",
    "FM": "Микронезия", "MH": "Маршалловы острова", "PW": "Палау", "NR": "Науру",
    "TV": "Тувалу", "CK": "Острова Кука", "NU": "Ниуэ"
}

def extract_flag_and_country(name):
    flag_match = re.search(r'[🇦-🇿]{2}', name)
    if flag_match:
        flag = flag_match.group()
    else:
        flag = "🌍"
    
    # Ищем страну по ключевым словам (русские и английские названия)
    name_lower = name.lower()
    
    for code, country in COUNTRY_MAP.items():
        # По коду страны
        if code.lower() in name_lower or f" {code.lower()} " in f" {name_lower} ":
            return flag, country
        # По полному названию страны (русский и английский варианты)
        if country.lower() in name_lower:
            return flag, country
        # Дополнительные английские варианты
        if country == "США" and ("usa" in name_lower or "united states" in name_lower):
            return flag, country
        if country == "Великобритания" and ("uk" in name_lower or "united kingdom" in name_lower):
            return flag, country
        if country == "Южная Корея" and ("south korea" in name_lower or "republic of korea" in name_lower):
            return flag, country
    
    return flag, "Неизвестно"

def check_white(name):
    for pattern in WHITE_KEYWORDS:
        if re.search(pattern, name, re.IGNORECASE):
            return True
    return False

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
                if any(x in decoded for x in ['vless://', 'vmess://', 'trojan://']):
                    lines = decoded.splitlines()
                else:
                    lines = text.splitlines()
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

def check_config(config):
    host, port = extract_hostname_and_port(config)
    if host and port:
        is_alive = check_tcp_connection(host, port)
        return config, is_alive
    return config, False

def main():
    print("=" * 50)
    print(f"🚀 Запуск: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    sources_path = os.path.join(script_dir, 'sources.txt')
    
    try:
        with open(sources_path, 'r', encoding='utf-8') as f:
            sources = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        print(f"📁 Источников: {len(sources)}")
    except FileNotFoundError:
        print("❌ sources.txt не найден")
        return

    if not sources:
        print("❌ Нет источников")
        return

    # Сбор конфигов
    all_configs = []
    for url in sources:
        print(f"📥 Загрузка: {url}")
        configs = fetch_from_url(url)
        print(f"   Получено: {len(configs)}")
        all_configs.extend(configs)

    # Убираем дубликаты
    unique_configs = list(dict.fromkeys(all_configs))
    print(f"📊 Уникальных: {len(unique_configs)}")
    
    # Проверка работоспособности
    print(f"🔍 Проверка {len(unique_configs)} ключей...")
    working_configs = []
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(check_config, config): config for config in unique_configs}
        
        for i, future in enumerate(as_completed(futures), 1):
            config, is_alive = future.result()
            if is_alive:
                working_configs.append(config)
            if i % 50 == 0:
                print(f"   Прогресс: {i}/{len(unique_configs)}")
    
    print(f"✅ Рабочих ключей: {len(working_configs)}")
    
    # Группировка
    white = defaultdict(list)
    black = defaultdict(list)
    
    for line in working_configs:
        match = re.search(r'#(.+)$', line)
        if not match:
            continue
        name = match.group(1)
        
        flag, country = extract_flag_and_country(name)
        is_white = check_white(name)
        
        key = (flag, country)
        
        if is_white:
            white[key].append(line)
        else:
            black[key].append(line)
    
    # Формируем результат
    result_lines = []
    
    # Белые списки (с названиями стран)
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
    
    # Чёрные списки (без названий стран)
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
    
    # Сохраняем
    os.makedirs('subscriptions', exist_ok=True)
    
    output_text = '\n'.join(result_lines)
    with open('subscriptions/FreeCFGHub.txt', 'w', encoding='utf-8') as f:
        f.write(output_text)
    
    if output_text.strip():
        b64 = base64.b64encode(output_text.encode('utf-8')).decode('utf-8')
        with open('subscriptions/all_base64.txt', 'w', encoding='utf-8') as f:
            f.write(b64)
        print(f"✅ Сохранено {len(working_configs)} ключей")
    else:
        with open('subscriptions/all_base64.txt', 'w') as f:
            f.write('')
        print("❌ Нет ключей")

    print(f"✅ Готово {datetime.utcnow()}")

if __name__ == '__main__':
    main()

import requests
import base64
import re
from datetime import datetime
import os

def is_valid_config(line):
    # Проверяет, начинается ли строка с vless://, vmess:// и т.д.
    return bool(re.match(r'^(vless|vmess|trojan|hysteria2|ss|tuic)://', line.strip()))

def fetch_from_url(url):
    configs = []
    try:
        r = requests.get(url.strip(), timeout=12)
        if r.status_code != 200:
            print(f"Ошибка {r.status_code} для {url}")
            return configs
        
        text = r.text.strip()
        
        # Пробуем декодировать base64
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

def main():
    # Определяем путь к файлу sources.txt (там же, где main.py)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    sources_path = os.path.join(script_dir, 'sources.txt')
    
    try:
        with open(sources_path, 'r', encoding='utf-8') as f:
            sources = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    except FileNotFoundError:
        print("sources.txt не найден в корне репозитория!")
        print(f"Искал: {sources_path}")
        return

    if not sources:
        print("Нет источников в sources.txt!")
        return

    all_configs = []
    for url in sources:
        print(f"Собираю из {url}...")
        configs = fetch_from_url(url)
        print(f"  → найдено {len(configs)} конфигов")
        all_configs.extend(configs)

    # Убираем дубликаты
    unique_configs = list(dict.fromkeys(all_configs))
    print(f"Всего уникальных конфигов: {len(unique_configs)}")

    # Создаём папку subscriptions, если её нет
    os.makedirs('subscriptions', exist_ok=True)

    # Сохраняем plaintext
    with open('subscriptions/all.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(unique_configs))

    # Base64 версия (одна строка)
    if unique_configs:
        joined = '\n'.join(unique_configs)
        b64 = base64.b64encode(joined.encode('utf-8')).decode('utf-8')
        with open('subscriptions/all_base64.txt', 'w', encoding='utf-8') as f:
            f.write(b64)
        print(f"✅ Сохранено {len(unique_configs)} конфигов")
    else:
        with open('subscriptions/all_base64.txt', 'w') as f:
            f.write('')
        print("⚠️ Нет конфигов для сохранения")

    print(f"Обновлено в {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")

if __name__ == '__main__':
    main()

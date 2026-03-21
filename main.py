import requests
import base64
import re
from datetime import datetime

def is_valid_config(line):
    # Простая проверка — начинается с vless:// vmess:// trojan:// hysteria2:// ss:// и т.д.
    return bool(re.match(r'^(vless|vmess|trojan|hysteria2|ss|tuic)://', line.strip()))

def fetch_from_url(url):
    configs = []
    try:
        r = requests.get(url.strip(), timeout=12)
        if r.status_code != 200:
            print(f"Ошибка {r.status_code} для {url}")
            return configs
        
        text = r.text.strip()
        if text.startswith('dmVsbGVzOi8v') or text.startswith('dm1lc3M6Ly8='):  # base64-подписка
            try:
                decoded = base64.b64decode(text + '==').decode('utf-8', errors='ignore')  # иногда padding
                lines = decoded.splitlines()
            except:
                lines = text.splitlines()
        else:
            lines = text.splitlines()
        
        for line in lines:
            cleaned = line.strip()
            if is_valid_config(cleaned):
                configs.append(cleaned)
    except Exception as e:
        print(f"Исключение при {url}: {e}")
    return configs

def main():
    try:
        with open('sources.txt', 'r', encoding='utf-8') as f:
            sources = [line for line in f if line.strip() and not line.startswith('#')]
    except FileNotFoundError:
        print("sources.txt не найден!")
        return

    all_configs = []
    for url in sources:
        print(f"Собираю из {url}...")
        all_configs.extend(fetch_from_url(url))

    # Убираем дубликаты
    unique_configs = list(dict.fromkeys(all_configs))  # сохраняем порядок первого появления
    print(f"Всего уникальных конфигов: {len(unique_configs)}")

    # Сохраняем plaintext
    with open('subscriptions/all.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(unique_configs))

    # Base64 версия (одна строка)
    if unique_configs:
        joined = '\n'.join(unique_configs)
        b64 = base64.b64encode(joined.encode('utf-8')).decode('utf-8')
        with open('subscriptions/all_base64.txt', 'w', encoding='utf-8') as f:
            f.write(b64)
    else:
        with open('subscriptions/all_base64.txt', 'w') as f:
            f.write('')

    print(f"Обновлено в {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")

if __name__ == '__main__':
    main()

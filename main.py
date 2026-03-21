import requests
import base64
import re
from datetime import datetime
import json

# Словарь для декодирования Happ-ссылок
# (если у тебя есть реальные ключи для декодирования — добавь их)
HAPP_DECODER = {
    # Здесь будут твои ключи для декодирования, если нужны
}

def is_valid_config(line):
    """Проверяет, является ли строка конфигом"""
    return bool(re.match(r'^(vless|vmess|trojan|hysteria2|ss|tuic)://', line.strip()))

def decode_happ(url):
    """Пробует декодировать Happ-ссылку в обычный VLESS"""
    # Happ-ссылки обычно имеют вид happ://... 
    # Для их декодирования нужен ключ, который есть у разработчиков Happ
    # Пока возвращаем None, если не знаем, как декодировать
    if url.startswith('happ://'):
        # Здесь можно добавить логику декодирования
        # Например, через внешний API или локальный ключ
        # print(f"Найдена Happ-ссылка, пропускаю: {url[:50]}...")
        return None
    return url

def fetch_from_url(url):
    configs = []
    try:
        r = requests.get(url.strip(), timeout=12)
        if r.status_code != 200:
            print(f"Ошибка {r.status_code} для {url}")
            return configs
        
        text = r.text.strip()
        
        # Проверяем, не base64 ли это
        if re.match(r'^[A-Za-z0-9+/=]+$', text) and len(text) > 50:
            try:
                decoded = base64.b64decode(text).decode('utf-8', errors='ignore')
                # Если декодировалось и содержит ссылки — используем
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
            # Пропускаем пустые и комментарии
            if not cleaned or cleaned.startswith('#'):
                continue
            
            # Проверяем на Happ
            if cleaned.startswith('happ://'):
                # Если не умеем декодировать — пропускаем
                # В будущем можно добавить декодер
                continue
            
            # Обычные конфиги
            if is_valid_config(cleaned):
                configs.append(cleaned)
                
    except Exception as e:
        print(f"Исключение при {url}: {e}")
    return configs

def main():
    try:
        with open('sources.txt', 'r', encoding='utf-8') as f:
            sources = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    except FileNotFoundError:
        print("sources.txt не найден!")
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

import requests
import base64
import re
import socket
import time
from datetime import datetime
import os

def is_valid_config(line):
    """Проверяет, является ли строка конфигом"""
    return bool(re.match(r'^(vless|vmess|trojan|hysteria2|ss|tuic)://', line.strip()))

def extract_host_port(line):
    """Извлекает хост и порт из конфига"""
    # Для vless://
    match = re.search(r'vless://[^@]+@([^:]+):(\d+)', line)
    if match:
        return match.group(1), int(match.group(2))
    
    # Для vmess:// (base64)
    if line.startswith('vmess://'):
        try:
            b64 = line[8:]
            b64 += '=' * (4 - len(b64) % 4)
            decoded = base64.b64decode(b64).decode('utf-8')
            import json
            data = json.loads(decoded)
            return data.get('add', ''), int(data.get('port', 443))
        except:
            pass
    
    # Для trojan://
    match = re.search(r'trojan://[^@]+@([^:]+):(\d+)', line)
    if match:
        return match.group(1), int(match.group(2))
    
    # Для hysteria2://
    match = re.search(r'hysteria2://[^@]+@([^:]+):(\d+)', line)
    if match:
        return match.group(1), int(match.group(2))
    
    # Для ss://
    match = re.search(r'ss://[^@]+@([^:]+):(\d+)', line)
    if match:
        return match.group(1), int(match.group(2))
    
    return None, None

def check_port(host, port, timeout=3):
    """Проверяет, открыт ли порт"""
    if not host:
        return False
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except:
        return False

def test_config(line):
    """Тестирует конфиг: извлекает хост:порт и проверяет доступность"""
    host, port = extract_host_port(line)
    if host and port:
        try:
            start = time.time()
            if check_port(host, port):
                ping = (time.time() - start) * 1000
                return True, ping
        except:
            pass
    return False, None

def fetch_from_url(url):
    """Скачивает конфиги из URL"""
    configs = []
    try:
        r = requests.get(url.strip(), timeout=15)
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
    script_dir = os.path.dirname(os.path.abspath(__file__))
    sources_path = os.path.join(script_dir, 'sources.txt')
    
    try:
        with open(sources_path, 'r', encoding='utf-8') as f:
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
    
    # Тестируем конфиги
    print("\n🔍 Тестирую конфиги (проверка порта)...")
    working_configs = []
    
    for i, cfg in enumerate(unique_configs):
        if i % 100 == 0:
            print(f"  → проверено {i}/{len(unique_configs)}")
        
        working, ping = test_config(cfg)
        if working:
            # Добавляем пинг в конец строки (для сортировки)
            working_configs.append((cfg, ping))
    
    print(f"  → проверено {len(unique_configs)} конфигов")
    print(f"  → рабочих: {len(working_configs)}")
    
    # Сортируем по пингу
    working_configs.sort(key=lambda x: x[1])
    sorted_configs = [cfg for cfg, _ in working_configs]
    
    # Сохраняем
    os.makedirs('subscriptions', exist_ok=True)
    
    with open('subscriptions/all.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(sorted_configs))
    
    if sorted_configs:
        joined = '\n'.join(sorted_configs)
        b64 = base64.b64encode(joined.encode('utf-8')).decode('utf-8')
        with open('subscriptions/all_base64.txt', 'w', encoding='utf-8') as f:
            f.write(b64)
        print(f"\n✅ Сохранено {len(sorted_configs)} рабочих конфигов")
    else:
        with open('subscriptions/all_base64.txt', 'w') as f:
            f.write('')
        print("⚠️ Нет рабочих конфигов для сохранения")
    
    print(f"Обновлено в {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")

if __name__ == '__main__':
    main()

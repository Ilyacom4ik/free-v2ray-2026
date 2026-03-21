#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
🔥 FreeCFGHub Auto Collector & Checker
Собирает ключи из источников, проверяет работоспособность, сохраняет только живые
"""

import requests
import base64
import re
import socket
import threading
import queue
from datetime import datetime
import os
import sys

# === Цвета для логов в GitHub Actions (опционально) ===
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    END = '\033[0m'

def log(msg, color=None):
    """Вывод лога с цветом"""
    if color and sys.stdout.isatty():
        print(f"{color}{msg}{Colors.END}")
    else:
        print(msg)

def is_valid_config(line):
    """Проверяет, похоже ли на валидную конфигурацию"""
    return bool(re.match(r'^(vless|vmess|trojan|hysteria2|ss|tuic)://', line.strip()))

def parse_host_from_uri(uri: str):
    """Извлекает хост и порт из любой ссылки"""
    uri = uri.strip()
    
    # VLESS / Trojan / SS (с @)
    if '@' in uri:
        match = re.search(r'://[^@]+@([^:]+):(\d+)', uri)
        if match:
            return match.group(1), int(match.group(2))
    
    # Hysteria2
    if 'hysteria2://' in uri or 'hy2://' in uri:
        match = re.search(r'://([^:]+):(\d+)', uri)
        if match:
            return match.group(1), int(match.group(2))
    
    # VMess base64
    if uri.startswith('vmess://'):
        try:
            b64 = uri[8:]
            b64 += '=' * (4 - len(b64) % 4)
            decoded = base64.b64decode(b64).decode('utf-8')
            config = json.loads(decoded)
            return config.get('add', ''), int(config.get('port', 0))
        except:
            pass
    
    return '', 0

def check_host(host: str, port: int, timeout: float = 3) -> bool:
    """Проверяет доступность хоста и порта"""
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

def fetch_from_url(url):
    """Загрузка конфигов из URL"""
    configs = []
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        r = requests.get(url.strip(), headers=headers, timeout=15)
        if r.status_code != 200:
            log(f"  Ошибка {r.status_code}", Colors.RED)
            return configs
        
        text = r.text.strip()
        
        # Проверяем base64 подписку
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
        log(f"  Ошибка: {e}", Colors.RED)
    return configs

def check_keys(keys, threads=50):
    """Проверка ключей на работоспособность"""
    if not keys:
        return []
    
    log(f"\n🔍 Проверяю {len(keys)} ключей...", Colors.CYAN)
    
    working = []
    lock = threading.Lock()
    counter = 0
    total = len(keys)
    
    q = queue.Queue()
    for key in keys:
        q.put(key)
    
    def worker():
        nonlocal counter
        while True:
            try:
                uri = q.get_nowait()
            except queue.Empty:
                break
            
            with lock:
                counter += 1
                if counter % 50 == 0 or counter == total:
                    log(f"  📊 Проверено: {counter}/{total}", Colors.YELLOW)
            
            host, port = parse_host_from_uri(uri)
            if host and check_host(host, port):
                with lock:
                    working.append(uri)
                    log(f"  ✅ РАБОЧИЙ: {host}:{port}", Colors.GREEN)
            
            q.task_done()
    
    # Запускаем потоки
    thread_list = []
    for _ in range(min(threads, len(keys))):
        t = threading.Thread(target=worker)
        t.start()
        thread_list.append(t)
    
    for t in thread_list:
        t.join()
    
    log(f"\n📊 Результат: {len(working)} рабочих из {total}", Colors.CYAN)
    return working

def main():
    log("🚀 FreeCFGHub Auto Collector & Checker", Colors.CYAN)
    log(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", Colors.YELLOW)
    
    # Определяем пути
    script_dir = os.path.dirname(os.path.abspath(__file__))
    sources_path = os.path.join(script_dir, 'sources.txt')
    
    # Читаем источники
    try:
        with open(sources_path, 'r', encoding='utf-8') as f:
            sources = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        log(f"📋 Загружено источников: {len(sources)}", Colors.GREEN)
    except FileNotFoundError:
        log("❌ sources.txt не найден!", Colors.RED)
        return

    if not sources:
        log("❌ Нет источников для сбора!", Colors.RED)
        return

    # Сбор конфигов
    log("\n📡 Сбор конфигов...", Colors.CYAN)
    all_configs = []
    for url in sources:
        log(f"  📥 {url[:60]}...", Colors.YELLOW)
        configs = fetch_from_url(url)
        log(f"     найдено: {len(configs)}", Colors.GREEN)
        all_configs.extend(configs)

    # Удаляем дубликаты
    unique_configs = list(dict.fromkeys(all_configs))
    log(f"\n📦 Уникальных конфигов: {len(unique_configs)}", Colors.GREEN)

    if not unique_configs:
        log("❌ Нет конфигов для проверки!", Colors.RED)
        return

    # Проверка на работоспособность
    working_configs = check_keys(unique_configs)

    if not working_configs:
        log("❌ Нет рабочих конфигов!", Colors.RED)
        return

    # Сохраняем в файл
    os.makedirs('subscriptions', exist_ok=True)
    
    # Основной файл
    with open('subscriptions/FreeCFGHub.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(working_configs))
    
    # Base64 версия для подписок
    joined = '\n'.join(working_configs)
    b64 = base64.b64encode(joined.encode('utf-8')).decode('utf-8')
    with open('subscriptions/FreeCFGHub_base64.txt', 'w', encoding='utf-8') as f:
        f.write(b64)
    
    log(f"\n✅ Сохранено {len(working_configs)} рабочих конфигов:", Colors.GREEN)
    log(f"   📁 subscriptions/FreeCFGHub.txt", Colors.CYAN)
    log(f"   📁 subscriptions/FreeCFGHub_base64.txt", Colors.CYAN)
    
    # Статистика
    log(f"\n📊 Статистика:", Colors.CYAN)
    log(f"   • Собрано: {len(unique_configs)}", Colors.YELLOW)
    log(f"   • Рабочих: {len(working_configs)}", Colors.GREEN)
    log(f"   • Мёртвых: {len(unique_configs) - len(working_configs)}", Colors.RED)
    
    log(f"\n🏁 Готово! {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", Colors.CYAN)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        log("\n⚠️ Прервано пользователем", Colors.YELLOW)
    except Exception as e:
        log(f"\n❌ Ошибка: {e}", Colors.RED)
        

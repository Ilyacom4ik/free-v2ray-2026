#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import base64
import re
import os
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, parse_qs

CHECK_TIMEOUT = 3
CHECK_WORKERS = 100
CHANNEL_TAG = "@FreeCFGHub"
PROFILE_TITLE = "FreeCFGHub Lite"
PROFILE_UPDATE_INTERVAL = 1

def load_whitelist():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sni_whitelist.txt')
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return set(line.strip().lower() for line in f if line.strip())
    except FileNotFoundError:
        print("❌ sni_whitelist.txt не найден")
        return set()

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
    try:
        clean = config.split('#')[0]
        parsed = urlparse(clean)
        uuid = parsed.username
        if uuid and re.match(r'^[0-9a-f-]{36}$', uuid, re.IGNORECASE):
            return f"{uuid}@{parsed.hostname}:{parsed.port}"
    except Exception:
        pass
    return None

def deduplicate(configs):
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
            raw = config.split('#')[0].strip()
            if raw not in seen_raw:
                seen_raw.add(raw)
                unique.append(config)
    return unique

def extract_sni(config):
    try:
        clean = config.split('#')[0].strip()
        parsed = urlparse(clean)
        params = parse_qs(parsed.query)
        if 'sni' in params:
            return params['sni'][0].lower()
        if 'host' in params:
            return params['host'][0].lower()
        if 'peer' in params:
            return params['peer'][0].lower()
    except Exception:
        pass
    return None

def filter_by_sni(configs, whitelist):
    filtered = []
    no_sni = []
    for config in configs:
        sni = extract_sni(config)
        if sni is None:
            no_sni.append(config)
            continue
        parts = sni.split('.')
        matched = False
        for i in range(len(parts) - 1):
            domain = '.'.join(parts[i:])
            if domain in whitelist:
                matched = True
                break
        if matched:
            filtered.append(config)
    print(f"   С SNI из белого списка: {len(filtered)}")
    print(f"   Без SNI параметра: {len(no_sni)}")
    return filtered

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
    print(f"🔍 Проверка {total} ключей...", flush=True)
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

def main():
    print("🚀 Парсер запущен", flush=True)
    script_dir = os.path.dirname(os.path.abspath(__file__))

    whitelist = load_whitelist()
    print(f"📋 Белый список: {len(whitelist)} доменов", flush=True)

    sources_path = os.path.join(script_dir, 'sources.txt')
    try:
        with open(sources_path, 'r', encoding='utf-8') as f:
            sources = [l.strip() for l in f if l.strip() and not l.startswith('#')]
        print(f"📁 Источников: {len(sources)}", flush=True)
    except FileNotFoundError:
        print("❌ sources.txt не найден", flush=True)
        return

    all_configs = []
    for url in sources:
        print(f"📥 {url}", flush=True)
        configs = fetch_from_url(url)
        print(f"   Получено: {len(configs)}", flush=True)
        all_configs.extend(configs)

    print(f"📊 Всего: {len(all_configs)}", flush=True)

    unique_configs = deduplicate(all_configs)
    print(f"🔄 После дедупликации: {len(unique_configs)}", flush=True)

    print("🔍 Фильтрация по SNI...", flush=True)
    sni_filtered = filter_by_sni(unique_configs, whitelist)
    print(f"✅ После SNI фильтра: {len(sni_filtered)}", flush=True)

    alive = check_all_keys(sni_filtered)
    print(f"✅ Живых: {len(alive)} | ❌ Мёртвых: {len(sni_filtered) - len(alive)}", flush=True)

    # Добавляем префикс
    named = []
    for idx, line in enumerate(alive, 1):
        new_name = f"Lite #{idx:03d} {CHANNEL_TAG}"
        if '#' in line:
            new_line = re.sub(r'#.+$', f'#{new_name}', line)
        else:
            new_line = f"{line}#{new_name}"
        named.append(new_line)

    os.makedirs('subscriptions', exist_ok=True)

    header = f"#profile-title: {PROFILE_TITLE}\n#profile-update-interval: {PROFILE_UPDATE_INTERVAL}\n"
    output = header + '\n'.join(named)

    with open('subscriptions/whitelist_keys.txt', 'w', encoding='utf-8') as f:
        f.write(output)

    b64 = base64.b64encode(output.encode('utf-8')).decode('utf-8')
    with open('subscriptions/whitelist_keys_base64.txt', 'w', encoding='utf-8') as f:
        f.write(b64)

    print(f"✅ Готово — сохранено {len(alive)} ключей в subscriptions/whitelist_keys.txt", flush=True)

if __name__ == '__main__':
    main()

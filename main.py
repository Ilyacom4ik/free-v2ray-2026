#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import base64
import re
import os
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
from urllib.parse import urlparse

print("DEBUG: скрипт запущен", flush=True)

CHANNEL_TAG = "@FreeCFGHub"
CHECK_TIMEOUT = 5
CHECK_WORKERS = 50

# ═══════════════════════════════════════════════════════
#              БЕЛЫЙ СПИСОК ДОМЕНОВ ДЛЯ LITE
# ═══════════════════════════════════════════════════════

LITE_DOMAINS = {
    "sochisirius.ru", "edu.sirius.online", "storage0.sirius.online",
    "alfa-mobile.alfabank.ru", "epp.genproc.gov.ru", "duma.gov.ru",
    "alfabank.ru", "pochta.ru", "xn--80ajghhoc2aj1c8b.xn--p1ai",
    "moskva.taximaxim.ru", "2gis.ru", "tutu.ru", "rzd.ru", "rambler.ru",
    "lenta.ru", "gazeta.ru", "rbc.ru", "kp.ru", "government.ru",
    "kremlin.ru", "travel.yandex.ru", "trk.mail.ru", "1l-api.mail.ru",
    "m.47news.ru", "st.kinopoisk.ru", "quiz.kinopoisk.ru",
    "payment-widget.kinopoisk.ru", "sso.kinopoisk.ru", "touch.kinopoisk.ru",
    "informer.yandex.ru", "digital.gov.ru", "adm.digital.gov.ru",
    "travel.yastatic.net", "api.uxfeedback.yandex.net", "api.s3.yandex.net",
    "cdn.s3.yandex.net", "uxfeedback-cdn.s3.yandex.net", "uxfeedback.yandex.ru",
    "cloudcdn-m9-15.cdn.yandex.net", "cloudcdn-m9-14.cdn.yandex.net",
    "cloudcdn-m9-13.cdn.yandex.net", "cloudcdn-m9-12.cdn.yandex.net",
    "cloudcdn-m9-10.cdn.yandex.net", "cloudcdn-m9-9.cdn.yandex.net",
    "cloudcdn-m9-7.cdn.yandex.net", "cloudcdn-m9-6.cdn.yandex.net",
    "cloudcdn-m9-5.cdn.yandex.net", "cloudcdn-m9-4.cdn.yandex.net",
    "cloudcdn-m9-3.cdn.yandex.net", "cloudcdn-m9-2.cdn.yandex.net",
    "admin.cs7777.vk.ru", "admin.tau.vk.ru", "analytics.vk.ru",
    "api.cs7777.vk.ru", "owa.ozon.ru", "learning.ozon.ru",
    "mapi.learning.ozon.ru", "ws.seller.ozon.ru", "bank.ozon.ru",
    "www.cikrf.ru", "izbirkom.ru", "seller.ozon.ru", "pay.ozon.ru",
    "securepay.ozon.ru", "adv.ozon.ru", "voter.gosuslugi.ru",
    "gosweb.gosuslugi.ru", "invest.ozon.ru", "ord.ozon.ru",
    "autodiscover.ord.ozon.ru", "api.tau.vk.ru", "fw.wb.ru",
    "finance.wb.ru", "jitsi.wb.ru", "dnd.wb.ru", "live.ok.ru",
    "m.ok.ru", "api.ok.ru", "multitest.ok.ru", "dating.ok.ru",
    "tamtam.ok.ru", "away.cs7777.vk.ru", "away.tau.vk.ru",
    "business.vk.ru", "connect.cs7777.vk.ru", "cs7777.vk.ru",
    "dev.cs7777.vk.ru", "dev.tau.vk.ru", "expert.vk.ru",
    "id.cs7777.vk.ru", "id.tau.vk.ru", "login.cs7777.vk.ru",
    "login.tau.vk.ru", "m.cs7777.vk.ru", "m.tau.vk.ru", "m.vk.ru",
    "m.vkvideo.cs7777.vk.ru", "me.cs7777.vk.ru", "ms.cs7777.vk.ru",
    "music.vk.ru", "oauth.cs7777.vk.ru", "oauth.tau.vk.ru",
    "oauth2.cs7777.vk.ru", "ord.vk.ru", "push.vk.ru", "r.vk.ru",
    "target.vk.ru", "tech.vk.ru", "ui.cs7777.vk.ru", "ui.tau.vk.ru",
    "vkvideo.cs7777.vk.ru", "stats.vk-portal.net", "mediafeeds.yandex.ru",
    "cdn.tbank.ru", "uslugi.yandex.ru", "auto.ru",
    "http-check-headers.yandex.ru", "sso.auto.ru", "hrc.tbank.ru",
    "static.rutube.ru", "kiks.yandex.ru", "cobrowsing.tbank.ru",
    "ssp.rutube.ru", "preview.rutube.ru", "st-ok.cdn-vk.ru",
    "ekmp-a-51.rzd.ru", "mp.rzd.ru", "pulse.mp.rzd.ru", "link.mp.rzd.ru",
    "adm.mp.rzd.ru", "welcome.rzd.ru", "travel.rzd.ru",
    "secure-cloud.rzd.ru", "secure.rzd.ru", "market.rzd.ru",
    "ticket.rzd.ru", "my.rzd.ru", "prodvizhenie.rzd.ru", "disk.rzd.ru",
    "www.rzd.ru", "team.rzd.ru", "contacts.rzd.ru", "cargo.rzd.ru",
    "company.rzd.ru", "avatars.mds.yandex.net", "mc.yandex.ru",
    "www.vtb.ru", "chat3.vtb.ru", "s.vtb.ru", "sso-app4.vtb.ru",
    "sso-app5.vtb.ru", "cdn.lemanapro.ru", "dmp.dmpkit.lemanapro.ru",
    "receive-sentry.lmru.tech", "partners.lemanapro.ru",
    "metrics.alfabank.ru", "static.lemanapro.ru", "lemanapro.ru",
    "frontend.vh.yandex.ru", "yandex.net", "favicon.yandex.ru",
    "favicon.yandex.com", "favicon.yandex.net", "gu-st.ru",
    "browser.yandex.com", "api.browser.yandex.com", "wap.yandex.com",
    "kiks.yandex.com", "rs.mail.ru", "yandex.com",
    "mediafeeds.yandex.com", "avatars.mds.yandex.com", "mc.yandex.com",
    "api-maps.yandex.ru", "enterprise.api-maps.yandex.ru", "dzen.ru",
    "300.ya.ru", "ya.ru", "brontp-pre.yandex.ru", "suggest.dzen.ru",
    "dr2.yandex.net", "cloud.cdn.yandex.net", "api.browser.yandex.ru",
    "wap.yandex.ru", "cloud.cdn.yandex.com", "dr.yandex.net",
    "mail.yandex.ru", "mail.yandex.com", "yabs.yandex.ru",
    "neuro.translate.yandex.ru", "cloud.cdn.yandex.ru", "ws-api.oneme.ru",
    "cdn.yandex.ru", "3475482542.mc.yandex.ru", "ads.vk.ru",
    "s3.yandex.net", "browser.yandex.ru", "vk-portal.net",
    "login.vk.ru", "pic.rutubelist.ru", "zen.yandex.ru",
    "zen.yandex.com", "zen.yandex.net", "le.tbank.ru", "rutube.ru",
    "queuev4.vk.com", "api.vk.ru", "collections.yandex.ru",
    "r0.mradx.net", "collections.yandex.com",
    "zen-yabro-morda.mediascope.mc.yandex.ru", "yandex.ru",
    "bro-bg-store.s3.yandex.ru", "bro-bg-store.s3.yandex.net",
    "bro-bg-store.s3.yandex.com", "www.sberbank.ru",
    "static-mon.yandex.net", "id.tbank.ru", "sync.browser.yandex.net",
    "storage.ape.yandex.net", "top-fwz1.mail.ru", "sberbank.ru",
    "cms-res-web.online.sberbank.ru", "sfd.gosuslugi.ru",
    "esia.gosuslugi.ru", "ams2-cdn.2gis.com", "bot.gosuslugi.ru",
    "gosuslugi.ru", "contract.gosuslugi.ru", "novorossiya.gosuslugi.ru",
    "pos.gosuslugi.ru", "lk.gosuslugi.ru", "map.gosuslugi.ru",
    "partners.gosuslugi.ru", "www.gosuslugi.ru", "eh.vk.com",
    "akashi.vk-portal.net", "id.sber.ru", "st.ozone.ru", "ir.ozone.ru",
    "vt-1.ozone.ru", "www.ozon.ru", "ozon.ru", "xapi.ozon.ru",
    "suggest.sso.dzen.ru", "sso.dzen.ru", "strm-rad-23.strm.yandex.net",
    "strm.yandex.net", "strm.yandex.ru", "log.strm.yandex.ru",
    "online.sberbank.ru", "esa-res.online.sberbank.ru",
    "egress.yandex.net", "st.okcdn.ru", "742231.ms.ok.ru",
    "cloudcdn-ams19.cdn.yandex.net", "wb.ru", "a.wb.ru",
    "user-geo-data.wildberries.ru", "banners-website.wildberries.ru",
    "chat-prod.wildberries.ru", "id.vk.ru", "surveys.yandex.ru",
    "pl-res.online.sberbank.ru", "privacy-cs.mail.ru", "disk.2gis.com",
    "imgproxy.cdn-tinkoff.ru", "an.yandex.ru", "sba.yandex.ru",
    "sba.yandex.com", "sba.yandex.net", "login.vk.com", "cloud.vk.com",
    "cloud.vk.ru", "api.2gis.ru", "keys.api.2gis.com",
    "favorites.api.2gis.com", "styles.api.2gis.com",
    "tile0.maps.2gis.com", "tile1.maps.2gis.com", "tile2.maps.2gis.com",
    "tile3.maps.2gis.com", "tile4.maps.2gis.com", "bfds.sberbank.ru",
    "dev.max.ru", "web.max.ru", "api.max.ru", "legal.max.ru",
    "st.max.ru", "max.ru", "botapi.max.ru", "link.max.ru",
    "download.max.ru", "i.max.ru", "help.max.ru",
    "api.photo.2gis.com", "www.t2.ru", "msk.t2.ru", "s3.t2.ru",
    "2gis.com", "filekeeper-vod.2gis.com",
    "i0.photo.2gis.com", "i1.photo.2gis.com", "i2.photo.2gis.com",
    "i3.photo.2gis.com", "i4.photo.2gis.com", "i5.photo.2gis.com",
    "i6.photo.2gis.com", "i7.photo.2gis.com", "i8.photo.2gis.com",
    "i9.photo.2gis.com", "jam.api.2gis.com", "catalog.api.2gis.com",
    "api.reviews.2gis.com", "public-api.reviews.2gis.com",
    "mapgl.2gis.com", "yastatic.net", "csp.yandex.net",
    "cdnrhkgfkkpupuotntfj.svc.cdn.yandex.net", "sntr.avito.ru",
    "stats.avito.ru", "cs.avito.ru", "www.avito.st", "avito.st",
    "st.avito.ru", "www.avito.ru", "m.avito.ru", "avito.ru",
    "api.avito.ru", "yabro-wbplugin.edadeal.yandex.ru",
    "goya.rutube.ru", "www.kinopoisk.ru", "widgets.kinopoisk.ru",
    "payment-widget.plus.kinopoisk.ru",
    "api.events.plus.yandex.net", "speller.yandex.net",
    "d-assets.2gis.ru", "s0.bss.2gis.com", "s1.bss.2gis.com",
}

# ═══════════════════════════════════════════════════════
#                  ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ═══════════════════════════════════════════════════════

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
            except Exception:
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
            host = parsed.hostname
            port = parsed.port
            return f"{uuid}@{host}:{port}"
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
    print(f"🔍 Проверка {total} ключей (потоков: {CHECK_WORKERS}, таймаут: {CHECK_TIMEOUT}s)...", flush=True)
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

def is_lite_by_domain(config):
    """
    Проверяет, содержит ли конфиг маршрутизацию по доменам из белого списка.
    Ищет домены из LITE_DOMAINS в названии (#...) или в самом URI.
    """
    config_lower = config.lower()
    for domain in LITE_DOMAINS:
        if domain.lower() in config_lower:
            return True
    # Дополнительно проверяем по старым ключевым словам в названии
    match = re.search(r'#(.+)$', config)
    if match:
        name = match.group(1)
        for pattern in [r'Lite', r'Белые?\s*списки?', r'White\s*List', r'\bWL\b', r'\[.*CIDR.*\]']:
            if re.search(pattern, name, re.IGNORECASE):
                return True
    return False

# ═══════════════════════════════════════════════════════
#                        MAIN
# ═══════════════════════════════════════════════════════

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

    # Загрузка
    all_configs = []
    for url in sources:
        print(f"📥 Загрузка: {url}", flush=True)
        configs = fetch_from_url(url)
        print(f"   Получено: {len(configs)}", flush=True)
        all_configs.extend(configs)

    # Дедупликация
    unique_configs = deduplicate(all_configs)
    print(
        f"📊 Уникальных: {len(unique_configs)} "
        f"(дубликатов удалено: {len(all_configs) - len(unique_configs)})",
        flush=True
    )

    # Проверка живых
    alive_configs = check_all_keys(unique_configs)
    print(
        f"✅ Живых: {len(alive_configs)} | "
        f"❌ Мёртвых: {len(unique_configs) - len(alive_configs)}",
        flush=True
    )

    # Разделяем на Lite / Full по доменам белого списка
    lite_configs = []
    full_configs = []
    for line in alive_configs:
        if is_lite_by_domain(line):
            lite_configs.append(line)
        else:
            full_configs.append(line)

    result_lines = []

    # ── Lite — без сортировки по странам ──
    if lite_configs:
        result_lines.append("🏳️ Lite (оптимизированный режим)")
        result_lines.append("")
        for idx, line in enumerate(lite_configs, start=1):
            new_name = f"Lite #{idx:03d} {CHANNEL_TAG}"
            new_line = re.sub(r'#.+$', f'#{new_name}', line)
            if '#' not in line:
                new_line = f"{line}#{new_name}"
            result_lines.append(new_line)
        result_lines.append("")

    # ── Full — без сортировки по странам ──
    if full_configs:
        result_lines.append("🏴 Full (полный доступ)")
        result_lines.append("")
        for idx, line in enumerate(full_configs, start=1):
            new_name = f"Full #{idx:03d} {CHANNEL_TAG}"
            new_line = re.sub(r'#.+$', f'#{new_name}', line)
            if '#' not in line:
                new_line = f"{line}#{new_name}"
            result_lines.append(new_line)
        result_lines.append("")

    # Сохранение
    os.makedirs('subscriptions', exist_ok=True)
    output_text = '\n'.join(result_lines)

    with open('subscriptions/FreeCFGHub.txt', 'w', encoding='utf-8') as f:
        f.write(output_text)
    print("💾 Записан subscriptions/FreeCFGHub.txt", flush=True)

    if output_text.strip():
        b64 = base64.b64encode(output_text.encode('utf-8')).decode('utf-8')
        with open('subscriptions/all_base64.txt', 'w', encoding='utf-8') as f:
            f.write(b64)
        print("💾 Записан subscriptions/all_base64.txt", flush=True)

    print(
        f"✅ Готово | Lite: {len(lite_configs)} | Full: {len(full_configs)}",
        flush=True
    )

if __name__ == '__main__':
    main()

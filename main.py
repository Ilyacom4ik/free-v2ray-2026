import requests
import os
from datetime import datetime

# Создаем папку
os.makedirs("subscriptions", exist_ok=True)

# Твои источники (если есть sources.txt, читаем оттуда)
sources = []
if os.path.exists("sources.txt"):
    with open("sources.txt", "r") as f:
        sources = [line.strip() for line in f if line.strip()]
else:
    # Если нет sources.txt, качаем с твоих известных источников
    sources = [
        "https://raw.githubusercontent.com/...",  # добавь свои ссылки
    ]

# Качаем и сохраняем
for url in sources:
    try:
        print(f"[{datetime.now()}] Downloading: {url}")
        r = requests.get(url, timeout=30)
        
        if r.status_code == 200:
            # Определяем имя файла из URL или используем индекс
            filename = url.split("/")[-1].split("?")[0]
            if not filename.endswith(".txt"):
                filename = f"sub_{sources.index(url)}.txt"
            
            filepath = f"subscriptions/{filename}"
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(r.text)
            
            print(f"✅ Saved: {filepath} ({len(r.text)} bytes)")
        else:
            print(f"❌ Failed: {url} - status {r.status_code}")
            
    except Exception as e:
        print(f"❌ Error: {url} - {e}")

# Выводим список файлов после загрузки
print("\n📁 Files in subscriptions/:")
for f in os.listdir("subscriptions"):
    filepath = os.path.join("subscriptions", f)
    size = os.path.getsize(filepath)
    print(f"  - {f} ({size} bytes)")

print("Done.")

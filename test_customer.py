import requests
import time

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    "X-Requested-With": "XMLHttpRequest",
})

BASE = "https://tenders.procurement.gov.ge/public/library"

# Adım 1: Session başlat
print("=== 1. Session başlatılıyor ===")
r = SESSION.get(f"{BASE}/")
print(f"Status: {r.status_code}")
print(f"Cookies: {dict(SESSION.cookies)}")
SESSION.headers["Referer"] = f"{BASE}/"

# Adım 2: who.php
print("\n=== 2. who.php ===")
w = SESSION.get(f"{BASE}/who.php")
print(f"Status: {w.status_code}")
print(f"Body: {repr(w.text[:200])}")

# Adım 3: Her müşteri için list_org.php test
IDS = {
    "424611441": "Lago",
    "436034916": "Our Group",
    "405142634": "Ander Konstrakshen",
    "425057341": "Eplaini",
}

print("\n=== 3. list_org.php testi ===")
for cid, name in IDS.items():
    ts = int(time.time() * 1000)
    r = SESSION.get(f"{BASE}/list_org.php", params={"q": cid, "limit": "50", "timestamp": str(ts)})
    print(f"\n{name} ({cid}):")
    print(f"  Status: {r.status_code}")
    print(f"  Content-Type: {r.headers.get('Content-Type', '?')}")
    print(f"  Body: {repr(r.text[:300])}")
    time.sleep(0.5)

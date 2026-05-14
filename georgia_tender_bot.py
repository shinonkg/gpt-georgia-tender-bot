"""
Georgia Tender Bot — мониторинг тендеров на портале procurement.gov.ge
"""

import os
import csv
import json
import time
import logging
import hashlib
import requests
from pathlib import Path

# ── Настройки ─────────────────────────────────────────────────────────────────

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

KEYWORDS: list[str] = []
CPV_CODES: list[str] = []

CHECK_INTERVAL = 300

SEEN_FILE = Path("seen_tenders_georgia.json")
CUSTOMER_CSV_FILE = "customer_tenders.csv"

# (identification_code): (display_name, monac_id, georgian_name)
CUSTOMERS = {
    "424611441": ("Lago",                   "12891", "ლაგო"),
    "436034916": ("Our Group chveni jgupi",  "",      ""),
    "405142634": ("Ander Konstrakshen",      "",      ""),
    "425057341": ("Eplaini",                 "",      ""),
}

# ── Логирование ────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("georgia_tender_bot.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

# ── Портал ────────────────────────────────────────────────────────────────────

BASE_URL    = "https://tenders.procurement.gov.ge"
API_URL     = f"{BASE_URL}/public/api"
LIBRARY_URL = f"{BASE_URL}/public/library"
CONTROLLER_URL = f"{LIBRARY_URL}/controller.php"
LIST_ORG_URL   = f"{LIBRARY_URL}/list_org.php"

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": f"{LIBRARY_URL}/",
})


def init_session() -> None:
    try:
        SESSION.get(f"{LIBRARY_URL}/", timeout=30)
        SESSION.get(f"{LIBRARY_URL}/who.php", timeout=15)
        SESSION.headers["Referer"] = f"{LIBRARY_URL}/"
        log.info("Session hazır. Cookies: %s", list(SESSION.cookies.keys()))
    except Exception as e:
        log.warning("init_session: %s", e)


def get_monac_id(customer_id: str) -> tuple[str, str]:
    info = CUSTOMERS.get(customer_id, ("", "", ""))
    if info[1]:
        log.info("  Hardcoded: monac_id=%s, org_b=%s", info[1], info[2])
        return info[1], info[2]

    ts = int(time.time() * 1000)
    try:
        resp = SESSION.get(
            LIST_ORG_URL,
            params={"q": customer_id, "limit": "50", "timestamp": str(ts)},
            headers={"Accept": "application/json, text/javascript, */*; q=0.01"},
            timeout=30,
        )
        raw = resp.text.strip()
        log.info("  list_org raw: %s", repr(raw[:200]))
        if not raw:
            return "0", ""
        data = resp.json()
        items = data if isinstance(data, list) else data.get("results", [])
        if items:
            item = items[0]
            monac_id = str(item.get("id", ""))
            name = item.get("name", item.get("label", item.get("value", "")))
            if "(" in name:
                name = name[:name.rfind("(")].strip()
            return monac_id, name
    except Exception as e:
        log.error("get_monac_id(%s): %s", customer_id, e)
    return "0", ""


# ── Tender API ────────────────────────────────────────────────────────────────

def fetch_tenders(page: int = 1, page_size: int = 20) -> dict:
    params = {"page": page, "pageSize": page_size, "sortBy": "publishDate", "sortOrder": "desc"}
    try:
        resp = SESSION.get(f"{API_URL}/tenders", params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        log.error("Ошибка при запросе тендеров: %s", e)
        return {}


def fetch_tenders_html() -> list[dict]:
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        log.warning("beautifulsoup4 не установлен")
        return []
    try:
        resp = SESSION.get(f"{BASE_URL}/public/tenders", timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        log.error("Ошибка HTML-запроса: %s", e)
        return []
    soup = BeautifulSoup(resp.text, "html.parser")
    tenders = []
    for row in soup.select("table.tender-list tbody tr"):
        cols = row.find_all("td")
        if len(cols) < 4:
            continue
        link_tag = cols[1].find("a")
        tenders.append({
            "id":        cols[0].get_text(strip=True),
            "title":     cols[1].get_text(strip=True),
            "url":       BASE_URL + link_tag["href"] if link_tag else "",
            "organizer": cols[2].get_text(strip=True),
            "deadline":  cols[3].get_text(strip=True),
            "budget":    cols[4].get_text(strip=True) if len(cols) > 4 else "",
            "status":    cols[5].get_text(strip=True) if len(cols) > 5 else "",
        })
    return tenders


# ── Müşteri tender çekme ───────────────────────────────────────────────────────

def search_customer_tenders(customer_id: str, customer_name: str) -> list[dict]:
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        log.warning("beautifulsoup4 не установлен")
        return []

    log.info("Загрузка тендеров клиента: %s (%s)", customer_name, customer_id)

    monac_id, org_name_ge = get_monac_id(customer_id)
    if not monac_id or monac_id == "0":
        log.warning("  monac_id bulunamadı, atlanıyor")
        return []

    log.info("  → monac_id=%s, org_b=%s", monac_id, org_name_ge)

    all_tenders = []
    page = 1

    while True:
        post_data = {
            "action":               "search_app",
            "app_t":                "0",
            "search":               "",
            "app_reg_id":           "",
            "app_shems_id":         "0",
            "org_a":                "",
            "app_monac_id":         monac_id,
            "org_b":                org_name_ge,
            "app_particip_status_id": "0",
            "app_donor_id":         "0",
            "app_status":           "0",
            "app_agr_status":       "0",
            "app_type":             "0",
            "app_basecode":         "0",
            "app_codes":            "",
            "app_date_type":        "1",
            "app_date_from":        "",
            "app_date_till":        "",
            "app_amount_from":      "",
            "app_amount_to":        "",
            "app_currency":         "2",
            "app_pricelist":        "0",
        }

        try:
            resp = SESSION.post(CONTROLLER_URL, data=post_data, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            log.error("POST controller.php hata (sayfa %d): %s", page, e)
            break

        soup = BeautifulSoup(resp.text, "html.parser")
        parsed = parse_customer_tenders(soup, customer_id)

        if not parsed:
            log.info("  Sayfa %d boş, bitti.", page)
            break

        all_tenders.extend(parsed)
        log.info("  Sayfa %d: %d tender", page, len(parsed))

        next_link = soup.find("a", string=lambda t: t and (
            ">" in t or "შემდეგი" in t or "next" in (t or "").lower()
        ))
        if not next_link:
            break

        page += 1
        time.sleep(0.5)

    log.info("Клиент %s: итого %d тендеров", customer_name, len(all_tenders))
    return all_tenders


def parse_customer_tenders(soup, customer_id: str) -> list[dict]:
    tenders = []
    for row in soup.select("table tbody tr"):
        cols = row.find_all("td")
        if len(cols) < 2:
            continue

        tender_id   = cols[0].get_text(strip=True) if len(cols) > 0 else ""
        name        = ""
        link        = ""
        org         = ""
        price       = ""
        deadline    = ""
        publish_date = ""
        status      = ""

        a_tag = cols[1].find("a", href=True) if len(cols) >= 2 else None
        if a_tag:
            raw_href = a_tag["href"]
            link = (BASE_URL + raw_href) if raw_href.startswith("/") else raw_href
            name = a_tag.get_text(strip=True)
        elif len(cols) >= 2:
            name = cols[1].get_text(strip=True)

        if len(cols) >= 3: org          = cols[2].get_text(strip=True)
        if len(cols) >= 4: price        = cols[3].get_text(strip=True)
        if len(cols) >= 5: deadline     = cols[4].get_text(strip=True)
        if len(cols) >= 6: publish_date = cols[5].get_text(strip=True)
        if len(cols) >= 7: status       = cols[6].get_text(strip=True)

        if not name and not tender_id:
            continue

        tenders.append({
            "customer_id":  customer_id,
            "id":           tender_id,
            "reg_id":       tender_id,
            "name":         name,
            "org":          org,
            "price":        price,
            "deadline":     deadline,
            "publish_date": publish_date,
            "status":       status,
            "link":         link,
        })
    return tenders


def save_customer_csv(all_tenders: list[dict]) -> None:
    if not all_tenders:
        log.warning("Müşteri tender verisi yok, CSV yazılmadı")
        return
    fieldnames = ["customer_id", "id", "reg_id", "name", "org", "price",
                  "deadline", "publish_date", "status", "link"]
    with open(CUSTOMER_CSV_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for t in all_tenders:
            writer.writerow({k: t.get(k, "") for k in fieldnames})
    log.info("Сохранено %d тендеров клиентов → %s", len(all_tenders), CUSTOMER_CSV_FILE)


# ── Seen tenders ──────────────────────────────────────────────────────────────

def load_seen() -> set[str]:
    if SEEN_FILE.exists():
        try:
            return set(json.loads(SEEN_FILE.read_text(encoding="utf-8")))
        except Exception:
            return set()
    return set()


def save_seen(seen: set[str]) -> None:
    SEEN_FILE.write_text(
        json.dumps(list(seen), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def tender_id(tender: dict) -> str:
    raw = tender.get("id") or tender.get("tenderId") or tender.get("title", "")
    return hashlib.md5(str(raw).encode()).hexdigest()


def matches_filters(tender: dict) -> bool:
    if not KEYWORDS and not CPV_CODES:
        return True
    text = " ".join([
        tender.get("title", ""),
        tender.get("description", ""),
        tender.get("subject", ""),
    ]).lower()
    if KEYWORDS:
        if not any(kw.lower() in text for kw in KEYWORDS):
            return False
    if CPV_CODES:
        cpv = tender.get("cpvCode", "") or tender.get("cpv", "")
        if not any(cpv.startswith(code) for code in CPV_CODES):
            return False
    return True


# ── Telegram ───────────────────────────────────────────────────────────────────

def send_telegram(message: str) -> bool:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        log.warning("Telegram не настроен")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        resp = requests.post(url, json=payload, timeout=15)
        resp.raise_for_status()
        return True
    except requests.RequestException as e:
        log.error("Telegram hatası: %s", e)
        return False


def format_tender_message(tender: dict) -> str:
    title     = tender.get("title") or tender.get("subject") or "Без названия"
    tid       = tender.get("id") or tender.get("tenderId", "—")
    organizer = tender.get("organizer") or tender.get("organizerName", "—")
    budget    = tender.get("budget") or tender.get("estimatedValue", "—")
    deadline  = tender.get("deadline") or tender.get("submissionDeadline", "—")
    published = tender.get("publishDate") or tender.get("publicationDate", "—")
    url       = tender.get("url") or f"{BASE_URL}/public/tenders/{tid}"
    cpv       = tender.get("cpvCode") or tender.get("cpv", "")
    lines = [
        "🇬🇪 <b>Новый тендер — Грузия</b>", "",
        f"📋 <b>{title}</b>",
        f"🆔 ID: <code>{tid}</code>",
        f"🏢 Организатор: {organizer}",
    ]
    if budget and budget != "—":
        lines.append(f"💰 Бюджет: {budget}")
    if cpv:
        lines.append(f"📦 CPV: {cpv}")
    lines += [
        f"📅 Опубликован: {published}",
        f"⏰ Срок подачи: {deadline}",
        f"🔗 <a href='{url}'>Открыть тендер</a>",
    ]
    return "\n".join(lines)


# ── Ana döngü ─────────────────────────────────────────────────────────────────

def process_tenders(tenders: list[dict], seen: set[str]) -> int:
    new_count = 0
    for tender in tenders:
        tid = tender_id(tender)
        if tid in seen:
            continue
        if not matches_filters(tender):
            seen.add(tid)
            continue
        msg = format_tender_message(tender)
        log.info("Новый тендер: %s", tender.get("title", tid))
        send_telegram(msg)
        seen.add(tid)
        new_count += 1
        time.sleep(0.5)
    return new_count


def run_once() -> None:
    init_session()
    seen = load_seen()
    log.info("Проверка новых тендеров (Грузия)…")

    data = fetch_tenders(page=1, page_size=50)
    all_tenders = data.get("items") or data.get("tenders") or data.get("data") or []

    if not all_tenders:
        log.info("API пустой, пробуем HTML-парсинг…")
        all_tenders = fetch_tenders_html()

    new = process_tenders(all_tenders, seen)
    save_seen(seen)
    log.info("Готово. Новых: %d / Проверено: %d", new, len(all_tenders))

    log.info("Обновление тендеров клиентов…")
    all_customer_tenders: list[dict] = []
    for cust_id, cust_info in CUSTOMERS.items():
        cust_name = cust_info[0]
        try:
            tenders = search_customer_tenders(cust_id, cust_name)
            all_customer_tenders.extend(tenders)
        except Exception as e:
            log.error("Ошибка клиента %s: %s", cust_name, e)
        time.sleep(1)

    save_customer_csv(all_customer_tenders)
    log.info("Тендеры клиентов: итого %d", len(all_customer_tenders))


def run_loop() -> None:
    log.info("=" * 60)
    log.info("Georgia Tender Bot запущен")
    log.info("Клиенты: %s", [v[0] for v in CUSTOMERS.values()])
    log.info("=" * 60)
    while True:
        try:
            run_once()
        except KeyboardInterrupt:
            log.info("Остановлено")
            break
        except Exception as e:
            log.exception("Ошибка: %s", e)
        log.info("Следующая проверка через %d сек…", CHECK_INTERVAL)
        time.sleep(CHECK_INTERVAL)


# ── Giriş noktası ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Georgia Tender Bot")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=int, default=CHECK_INTERVAL)
    args = parser.parse_args()
    CHECK_INTERVAL = args.interval
    if args.once:
        run_once()
    else:
        run_loop()

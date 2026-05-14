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
from datetime import datetime, timedelta
from pathlib import Path

# ── Настройки ─────────────────────────────────────────────────────────────────

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

KEYWORDS: list[str] = []
CPV_CODES: list[str] = []

CHECK_INTERVAL = 300  # 5 минут

SEEN_FILE = Path("seen_tenders_georgia.json")
CUSTOMER_CSV_FILE = "customer_tenders.csv"

# Müşteriler: {identification_code: display_name}
CUSTOMERS = {
    "424611441": "Lago",
    "436034916": "Our Group chveni jgupi",
    "405142634": "Ander Konstrakshen",
    "425057341": "Eplaini",
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

# ── API Грузинского портала закупок ───────────────────────────────────────────

BASE_URL = "https://tenders.procurement.gov.ge"
API_URL = f"{BASE_URL}/public/api"
CONTROLLER_URL = f"{BASE_URL}/public/library/controller.php"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    "Referer": BASE_URL,
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def fetch_tenders(page: int = 1, page_size: int = 20) -> dict:
    params = {
        "page": page,
        "pageSize": page_size,
        "sortBy": "publishDate",
        "sortOrder": "desc",
    }
    try:
        resp = SESSION.get(f"{API_URL}/tenders", params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        log.error("Ошибка при запросе тендеров: %s", e)
        return {}


def fetch_tender_detail(tender_id: str) -> dict:
    try:
        resp = SESSION.get(f"{API_URL}/tenders/{tender_id}", timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        log.error("Ошибка при запросе тендера %s: %s", tender_id, e)
        return {}


def search_tenders(keyword: str, page: int = 1) -> dict:
    params = {
        "keyword": keyword,
        "page": page,
        "pageSize": 20,
        "sortBy": "publishDate",
        "sortOrder": "desc",
    }
    try:
        resp = SESSION.get(f"{API_URL}/tenders/search", params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        log.error("Ошибка поиска по '%s': %s", keyword, e)
        return {}


# ── Альтернативный парсер (HTML fallback) ─────────────────────────────────────

def fetch_tenders_html() -> list[dict]:
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        log.warning("beautifulsoup4 не установлен, HTML-парсинг недоступен")
        return []

    url = f"{BASE_URL}/public/tenders"
    try:
        resp = SESSION.get(url, timeout=30)
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
            "id": cols[0].get_text(strip=True),
            "title": cols[1].get_text(strip=True),
            "url": BASE_URL + link_tag["href"] if link_tag else "",
            "organizer": cols[2].get_text(strip=True),
            "deadline": cols[3].get_text(strip=True),
            "budget": cols[4].get_text(strip=True) if len(cols) > 4 else "",
            "status": cols[5].get_text(strip=True) if len(cols) > 5 else "",
        })

    return tenders


# ── Müşteri tender çekme ───────────────────────────────────────────────────────

def search_customer_tenders(customer_id: str, customer_name: str) -> list[dict]:
    """Поставщик ID'sine göre ihaleleri çek (org_b parametresi ile POST)."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        log.warning("beautifulsoup4 не установлен, невозможно получить тендеры клиента")
        return []

    log.info("Загрузка тендеров клиента: %s (%s)", customer_name, customer_id)

    post_data = {
        "action": "search_app",
        "app_t": "0",
        "search": "1",
        "org_b": customer_id,
        "app_status": "0",
        "app_basecode": "0",
        "app_codes": "",
        "org": "",
        "app_number": "",
        "date_from": "",
        "date_to": "",
    }

    all_tenders = []
    page = 1

    while True:
        post_data["page"] = str(page)
        try:
            resp = SESSION.post(CONTROLLER_URL, data=post_data, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            log.error("Ошибка запроса тендеров клиента %s (стр. %d): %s", customer_id, page, e)
            break

        soup = BeautifulSoup(resp.text, "html.parser")
        rows = soup.select("table tbody tr")

        if not rows:
            break

        parsed = parse_customer_tenders(soup, customer_id)
        if not parsed:
            break

        all_tenders.extend(parsed)
        log.info("  %s: стр. %d — найдено %d", customer_name, page, len(parsed))

        # Следующая страница
        next_btn = soup.find("a", string=lambda t: t and (">" in t or "შემდეგი" in t or "next" in t.lower()))
        if not next_btn:
            break
        page += 1
        time.sleep(0.5)

    log.info("Клиент %s: итого %d тендеров", customer_name, len(all_tenders))
    return all_tenders


def parse_customer_tenders(soup, customer_id: str) -> list[dict]:
    """HTML tablosundan tender satırlarını parse et."""
    tenders = []
    rows = soup.select("table tbody tr")

    for row in rows:
        cols = row.find_all("td")
        if len(cols) < 3:
            continue

        # Satır verilerini al (sütun sırası siteye göre değişebilir)
        link_tag = None
        for col in cols:
            a = col.find("a", href=True)
            if a:
                link_tag = a
                break

        tender_id = ""
        name = ""
        org = ""
        price = ""
        deadline = ""
        publish_date = ""
        status = ""
        link = ""

        if len(cols) >= 1:
            tender_id = cols[0].get_text(strip=True)
        if len(cols) >= 2:
            name = cols[1].get_text(strip=True)
            a_tag = cols[1].find("a", href=True)
            if a_tag:
                link = BASE_URL + a_tag["href"] if a_tag["href"].startswith("/") else a_tag["href"]
                name = a_tag.get_text(strip=True) or name
        if len(cols) >= 3:
            org = cols[2].get_text(strip=True)
        if len(cols) >= 4:
            price = cols[3].get_text(strip=True)
        if len(cols) >= 5:
            deadline = cols[4].get_text(strip=True)
        if len(cols) >= 6:
            publish_date = cols[5].get_text(strip=True)
        if len(cols) >= 7:
            status = cols[6].get_text(strip=True)

        # Reg ID (номер заявки)
        reg_id = tender_id

        if not name and not tender_id:
            continue

        tenders.append({
            "customer_id": customer_id,
            "id": tender_id,
            "reg_id": reg_id,
            "name": name,
            "org": org,
            "price": price,
            "deadline": deadline,
            "publish_date": publish_date,
            "status": status,
            "link": link,
        })

    return tenders


def save_customer_csv(all_tenders: list[dict]) -> None:
    """Tüm müşteri tenderlerini CSV'ye kaydet."""
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


# ── Хранилище просмотренных тендеров ──────────────────────────────────────────

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


# ── Фильтрация ─────────────────────────────────────────────────────────────────

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


# ── Telegram уведомления ───────────────────────────────────────────────────────

def send_telegram(message: str) -> bool:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        log.warning("Telegram не настроен, уведомление пропущено")
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
        log.error("Ошибка отправки в Telegram: %s", e)
        return False


def format_tender_message(tender: dict) -> str:
    title = tender.get("title") or tender.get("subject") or "Без названия"
    tid = tender.get("id") or tender.get("tenderId", "—")
    organizer = tender.get("organizer") or tender.get("organizerName", "—")
    budget = tender.get("budget") or tender.get("estimatedValue", "—")
    deadline = tender.get("deadline") or tender.get("submissionDeadline", "—")
    published = tender.get("publishDate") or tender.get("publicationDate", "—")
    url = tender.get("url") or f"{BASE_URL}/public/tenders/{tid}"
    cpv = tender.get("cpvCode") or tender.get("cpv", "")

    lines = [
        "🇬🇪 <b>Новый тендер — Грузия</b>",
        "",
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


# ── Основной цикл ──────────────────────────────────────────────────────────────

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
        print("\n" + msg.replace("<b>", "**").replace("</b>", "**")
                      .replace("<code>", "").replace("</code>", "")
                      .replace(f"<a href='", "").replace("'>Открыть тендер</a>", ""))

        send_telegram(msg)
        seen.add(tid)
        new_count += 1
        time.sleep(0.5)

    return new_count


def run_once() -> None:
    seen = load_seen()
    log.info("Проверка новых тендеров (Грузия)…")

    if KEYWORDS:
        all_tenders: list[dict] = []
        for kw in KEYWORDS:
            data = search_tenders(kw)
            items = data.get("items") or data.get("tenders") or data.get("data") or []
            all_tenders.extend(items)
    else:
        data = fetch_tenders(page=1, page_size=50)
        all_tenders = data.get("items") or data.get("tenders") or data.get("data") or []

        if not all_tenders:
            log.info("API вернул пустой ответ, пробуем HTML-парсинг…")
            all_tenders = fetch_tenders_html()

    new = process_tenders(all_tenders, seen)
    save_seen(seen)
    log.info("Готово. Новых тендеров: %d / Всего проверено: %d", new, len(all_tenders))

    # ── Müşteri tenderlerini güncelle ──────────────────────────────────────
    log.info("Обновление тендеров клиентов…")
    all_customer_tenders: list[dict] = []
    for cust_id, cust_name in CUSTOMERS.items():
        try:
            tenders = search_customer_tenders(cust_id, cust_name)
            all_customer_tenders.extend(tenders)
        except Exception as e:
            log.error("Ошибка при загрузке тендеров клиента %s: %s", cust_name, e)
        time.sleep(1)

    save_customer_csv(all_customer_tenders)
    log.info("Тендеры клиентов: итого %d", len(all_customer_tenders))


def run_loop() -> None:
    log.info("=" * 60)
    log.info("Georgia Tender Bot запущен")
    log.info("Портал: %s", BASE_URL)
    log.info("Интервал проверки: %d сек", CHECK_INTERVAL)
    log.info("Клиенты: %s", list(CUSTOMERS.values()))
    log.info("=" * 60)

    while True:
        try:
            run_once()
        except KeyboardInterrupt:
            log.info("Остановлено пользователем")
            break
        except Exception as e:
            log.exception("Неожиданная ошибка: %s", e)

        log.info("Следующая проверка через %d сек…", CHECK_INTERVAL)
        time.sleep(CHECK_INTERVAL)


# ── Точка входа ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Georgia Tender Bot")
    parser.add_argument("--once", action="store_true", help="Один запуск и выход")
    parser.add_argument("--interval", type=int, default=CHECK_INTERVAL,
                        help=f"Интервал проверки в секундах (по умолчанию {CHECK_INTERVAL})")
    args = parser.parse_args()

    CHECK_INTERVAL = args.interval

    if args.once:
        run_once()
    else:
        run_loop()

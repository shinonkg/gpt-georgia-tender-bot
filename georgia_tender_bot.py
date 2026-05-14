"""
Georgia Tender Bot — procurement.gov.ge müşteri tender monitoring
"""

import os
import csv
import json
import time
import logging
import hashlib
import requests
from datetime import datetime
from pathlib import Path

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

KEYWORDS: list[str] = []
CPV_CODES: list[str] = []
CHECK_INTERVAL = 300

SEEN_FILE = Path("seen_tenders_georgia.json")
CUSTOMER_TENDERS_CSV = Path("customer_tenders.csv")

# id_kodu → (isim, monac_id, supplier_search_text)
CUSTOMERS = {
    "424611441": ("Lago", "12891", "lago"),
    "436034916": ("Our Group", "", "our group"),
    "405142634": ("Ander Konstrakshen", "", "ander konstrakshen"),
    "425057341": ("Eplaini", "", "eplaini"),
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("georgia_tender_bot.log", encoding="utf-8"),
    ],
)

log = logging.getLogger(__name__)

BASE_URL = "https://tenders.procurement.gov.ge"
API_URL = f"{BASE_URL}/public/api"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


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
        encoding="utf-8"
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

    if KEYWORDS and not any(kw.lower() in text for kw in KEYWORDS):
        return False

    if CPV_CODES:
        cpv = tender.get("cpvCode", "") or tender.get("cpv", "")
        if not any(cpv.startswith(code) for code in CPV_CODES):
            return False

    return True


def send_telegram(message: str) -> bool:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        log.warning("Telegram ayarlı değil")
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
    title = tender.get("title") or tender.get("subject") or "Başlıksız"
    tid = tender.get("id") or tender.get("tenderId", "—")
    organizer = tender.get("organizer") or tender.get("organizerName", "—")
    budget = tender.get("budget") or tender.get("estimatedValue", "—")
    deadline = tender.get("deadline") or tender.get("submissionDeadline", "—")
    published = tender.get("publishDate") or tender.get("publicationDate", "—")
    url = tender.get("url") or f"{BASE_URL}/public/tenders/{tid}"
    cpv = tender.get("cpvCode") or tender.get("cpv", "")

    lines = [
        "🇬🇪 <b>Yeni Tender — Georgia</b>",
        "",
        f"📋 <b>{title}</b>",
        f"🆔 ID: <code>{tid}</code>",
        f"🏢 Kurum: {organizer}",
    ]

    if budget and budget != "—":
        lines.append(f"💰 Bütçe: {budget}")

    if cpv:
        lines.append(f"📦 CPV: {cpv}")

    lines += [
        f"📅 Yayın: {published}",
        f"⏰ Son tarih: {deadline}",
        f"🔗 <a href='{url}'>Tenderi aç</a>",
    ]

    return "\n".join(lines)


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
        log.error("Genel tender hatası: %s", e)
        return {}


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
        log.info("Yeni tender: %s", tender.get("title", tid))
        send_telegram(msg)

        seen.add(tid)
        new_count += 1
        time.sleep(0.5)

    return new_count


def fetch_customer_tenders_playwright(
    customer_id: str,
    monac_id: str,
    supplier_text: str,
    customer_label: str,
) -> list[dict]:

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log.error("Playwright kurulu değil. Çalıştır: pip install playwright && playwright install chromium")
        return []

    post_data = {
        "action": "search_app",
        "app_t": "0",
        "search": "",
        "app_reg_id": "",
        "app_shems_id": "0",
        "org_a": "",
        "app_monac_id": monac_id,
        "org_b": supplier_text,
        "app_particip_status_id": "0",
        "app_donor_id": "0",
        "app_status": "0",
        "app_agr_status": "0",
        "app_type": "0",
        "app_basecode": "0",
        "app_codes": "",
        "app_date_type": "1",
        "app_date_from": "",
        "app_date_till": "",
        "app_amount_from": "",
        "app_amount_to": "",
        "app_currency": "2",
        "app_pricelist": "0",
    }

    js_fetch = """
    async (params) => {
        const body = new URLSearchParams(params);

        const resp = await fetch('/public/library/controller.php', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'X-Requested-With': 'XMLHttpRequest',
                'Accept': '*/*'
            },
            credentials: 'include',
            body: body.toString()
        });

        const text = await resp.text();

        return {
            status: resp.status,
            body: text
        };
    }
    """

    results = []

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )

            context = browser.new_context(
                user_agent=HEADERS["User-Agent"],
                locale="en-US",
                timezone_id="Asia/Tbilisi",
            )

            page = context.new_page()

            log.info("[%s] Ana sayfa açılıyor...", customer_label)

            page.goto(
                f"{BASE_URL}/public/?lang=en",
                wait_until="networkidle",
                timeout=60000,
            )

            page.wait_for_timeout(1500)

            log.info("[%s] controller.php POST gönderiliyor...", customer_label)

            result = page.evaluate(js_fetch, post_data)

            status = result.get("status", 0)
            body = result.get("body", "")

            log.info("[%s] HTTP %s", customer_label, status)
            log.info("[%s] body ilk 300 karakter: %s", customer_label, body[:300])

            if status != 200:
                log.error("[%s] HTTP hata: %s", customer_label, status)
                browser.close()
                return []

            if not body.strip():
                log.warning("[%s] Boş cevap geldi", customer_label)
                browser.close()
                return []

            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                log.error("[%s] JSON parse edilemedi. Cevap: %s", customer_label, body[:500])
                browser.close()
                return []

            if isinstance(data, list):
                raw_list = data
            elif isinstance(data, dict):
                raw_list = (
                    data.get("items")
                    or data.get("tenders")
                    or data.get("data")
                    or data.get("results")
                    or []
                )
            else:
                raw_list = []

            log.info("[%s] %d tender bulundu", customer_label, len(raw_list))

            today = datetime.now().strftime("%Y-%m-%d")

            for t in raw_list:
                app_id = t.get("app_id") or t.get("id") or ""

                results.append({
                    "customer_id": customer_id,
                    "customer_name": customer_label,
                    "tender_id": app_id,
                    "title": t.get("app_name") or t.get("title") or t.get("subject") or "",
                    "organizer": t.get("org_name") or t.get("organizer") or "",
                    "budget": t.get("app_amount") or t.get("budget") or t.get("estimatedValue") or "",
                    "currency": t.get("currency_name") or "GEL",
                    "status": t.get("app_status_name") or t.get("status") or "",
                    "publish_date": t.get("app_reg_date") or t.get("publishDate") or today,
                    "deadline": t.get("app_end_date") or t.get("submissionDeadline") or "",
                    "url": f"{BASE_URL}/public/library/#/tenders/apinfo/{app_id}",
                })

            browser.close()

    except Exception as e:
        log.exception("[%s] Playwright hatası: %s", customer_label, e)

    return results


def update_customer_tenders_csv() -> None:
    all_rows: list[dict] = []

    for customer_id, (label, monac_id, supplier_text) in CUSTOMERS.items():
        if not monac_id:
            log.warning("[%s] monac_id bilinmiyor, atlanıyor", label)
            continue

        log.info("Müşteri: %s | ID: %s | monac_id: %s", label, customer_id, monac_id)

        rows = fetch_customer_tenders_playwright(
            customer_id=customer_id,
            monac_id=monac_id,
            supplier_text=supplier_text,
            customer_label=label,
        )

        all_rows.extend(rows)
        time.sleep(2)

    if not all_rows:
        log.warning("Hiç müşteri tender'i bulunamadı. CSV güncellenmedi.")
        return

    fieldnames = [
        "customer_id",
        "customer_name",
        "tender_id",
        "title",
        "organizer",
        "budget",
        "currency",
        "status",
        "publish_date",
        "deadline",
        "url",
    ]

    with open(CUSTOMER_TENDERS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    log.info("customer_tenders.csv güncellendi: %d satır", len(all_rows))


def run_once() -> None:
    seen = load_seen()

    log.info("Genel tender kontrolü başlıyor...")

    data = fetch_tenders(page=1, page_size=50)
    all_tenders = data.get("items") or data.get("tenders") or data.get("data") or []

    new = process_tenders(all_tenders, seen)
    save_seen(seen)

    log.info("Genel tenderler: %d yeni / %d toplam", new, len(all_tenders))

    log.info("Müşteri tenderleri güncelleniyor...")
    update_customer_tenders_csv()


def run_loop() -> None:
    log.info("=" * 60)
    log.info("Georgia Tender Bot başladı")
    log.info("Portal: %s", BASE_URL)
    log.info("Kontrol aralığı: %d sn", CHECK_INTERVAL)
    log.info("=" * 60)

    while True:
        try:
            run_once()
        except KeyboardInterrupt:
            log.info("Kullanıcı tarafından durduruldu")
            break
        except Exception as e:
            log.exception("Beklenmeyen hata: %s", e)

        log.info("Sonraki kontrol %d saniye sonra...", CHECK_INTERVAL)
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Georgia Tender Bot")
    parser.add_argument("--once", action="store_true", help="Bir kez çalıştır ve çık")
    parser.add_argument("--interval", type=int, default=CHECK_INTERVAL)
    parser.add_argument("--customers-only", action="store_true")

    args = parser.parse_args()

    CHECK_INTERVAL = args.interval

    if args.customers_only:
        update_customer_tenders_csv()
    elif args.once:
        run_once()
    else:
        run_loop()

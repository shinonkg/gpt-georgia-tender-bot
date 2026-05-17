"""
Georgia Tender Bot — procurement.gov.ge müşteri tender monitoring
"""

import os
import csv
import json
import time
import re
import logging
import hashlib
import html
import requests
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

CHECK_INTERVAL = 300
MAX_CUSTOMER_PAGES = int(os.getenv("MAX_CUSTOMER_TENDER_PAGES", "25"))

SEEN_FILE = Path("seen_tenders_georgia.json")
CUSTOMER_TENDERS_CSV = Path("customer_tenders.csv")
CUSTOMER_TENDER_YEAR = int(os.getenv("CUSTOMER_TENDER_YEAR", str(datetime.now().year)))
CUSTOMER_TENDER_DATE_TYPE = os.getenv("CUSTOMER_TENDER_DATE_TYPE", "2")

CUSTOMERS = {
    "424611441": ("Lago", "12891", "lago"),
    "436034916": ("Our Group chveni jgupi", "36827", "our group"),
    "405142634": ("Ander Konstrakshen", "104814", "ander konstrakshen"),
    "425057341": ("Eplaini", "71057", "eplaini"),
    "422937273": ("Jorjia Bilding Grupi", "83472", "jorjia bilding grupi"),
    "404573216": ("Kualiti", "77262", "kualiti"),
    "402214304": ("Legu Bildingi", "115620", "legu bildingi"),
    "405372074": ("SG Jgupi", "79247", "sg jgupi"),
    "404764705": ("Regrini", "129219", "regrini"),
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

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*; q=0.01",
}


def customer_date_range() -> tuple[str, str]:
    return f"01.01.{CUSTOMER_TENDER_YEAR}", f"31.12.{CUSTOMER_TENDER_YEAR}"


def send_telegram_message(text: str) -> bool:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        log.error("Telegram ayarları eksik, bildirim gönderilmedi")
        return False

    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=20,
        )
        if resp.status_code != 200:
            log.error("Telegram hata %s: %s", resp.status_code, resp.text[:300])
            return False
        log.info("Telegram bildirimi gönderildi")
        return True
    except Exception as exc:
        log.exception("Telegram bildirimi gönderilemedi: %s", exc)
        return False

def load_existing_customer_tender_ids() -> set[str]:
    if not CUSTOMER_TENDERS_CSV.exists():
        return set()

    try:
        with open(CUSTOMER_TENDERS_CSV, newline="", encoding="utf-8") as f:
            return {
                (row.get("customer_id", "") + ":" + row.get("tender_id", "")).strip(":")
                for row in csv.DictReader(f)
                if row.get("customer_id") and row.get("tender_id")
            }
    except Exception as exc:
        log.warning("Eski müşteri tender CSV okunamadı: %s", exc)
        return set()


def extract_page_count(html: str) -> int:
    patterns = [
        r"page:\s*\d+\s*/\s*(\d+)",
        r"plastpage\s*=\s*eval\(['\"]?(\d+)['\"]?\)",
        r"lastpage\s*=\s*eval\(['\"]?(\d+)['\"]?\)",
        r"page_count\s*[:=]\s*['\"]?(\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, html, re.I)
        if match:
            return max(1, min(MAX_CUSTOMER_PAGES, int(match.group(1))))

    page_numbers = [
        int(value)
        for value in re.findall(r"(?:page=|go_to_page\(|changePage\()\s*['\"]?(\d+)", html, re.I)
        if value.isdigit()
    ]
    if page_numbers:
        return max(1, min(MAX_CUSTOMER_PAGES, max(page_numbers)))
    return 1


def parse_customer_tender_rows(html: str, customer_id: str, customer_label: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows = []

    for row in soup.select("tr[id^='A']"):
        row_id = row.get("id", "")
        app_id = row_id.replace("A", "")
        text = row.get_text(" ", strip=True)

        nat_match = re.search(r"NAT\d+", text)
        nat_number = nat_match.group(0) if nat_match else app_id

        amount_match = re.search(r"([\d'`’.,\s]+)\s*GEL", text)
        budget = amount_match.group(0).strip() if amount_match else ""

        published_match = re.search(r"Procurement announcment date:\s*([0-9.]+)", text, re.I)
        deadline_match = re.search(r"Offer reception term:\s*([0-9.]+)", text, re.I)
        org_match = re.search(r"Procuring entities:\s*(.*?)\s*Procuring category:", text, re.I)

        rows.append({
            "customer_id": customer_id,
            "customer_name": customer_label,
            "tender_id": nat_number,
            "title": text,
            "organizer": org_match.group(1).strip() if org_match else "",
            "budget": budget,
            "currency": "GEL",
            "status": "Contract awarded" if re.search(r"Contract awarded", text, re.I) else "",
            "publish_date": published_match.group(1).strip() if published_match else "",
            "deadline": deadline_match.group(1).strip() if deadline_match else "",
            "url": f"{BASE_URL}/public/?lang=ru&go={app_id}",
        })

    return rows


def build_customer_tender_alert(row: dict) -> str:
    def esc(value: str) -> str:
        return html.escape(str(value or "-"), quote=False)

    return (
        "<b>Yeni musteri ihalesi bulundu</b>\n"
        f"Firma: <b>{esc(row.get('customer_name'))}</b>\n"
        f"Ihale: <b>{esc(row.get('tender_id'))}</b>\n"
        f"Alici kurum: {esc(row.get('organizer'))}\n"
        f"Tarih: {esc(row.get('publish_date'))}\n"
        f"Butce: {esc(row.get('budget'))}\n"
        f"Resmi link: {esc(row.get('url'))}"
    )

def build_no_new_tender_alert(total_rows: int) -> str:
    return (
        "<b>Georgia Tender Monitor</b>\n"
        "Yeni müşteri ihalesi yok.\n"
        f"Kontrol edilen kayıt: <b>{total_rows}</b>\n"
        f"Tarih: <b>{html.escape(datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC'))}</b>"
    )


def build_test_telegram_alert() -> str:
    return (
        "<b>Georgia Tender Monitor test</b>\n"
        "Telegram bildirimleri aktif.\n"
        f"Tarih: <b>{html.escape(datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC'))}</b>"
    )


def send_test_telegram_message() -> None:
    if not send_telegram_message(build_test_telegram_alert()):
        raise RuntimeError("Telegram test mesajı gönderilemedi")

def fetch_customer_tenders_playwright(
    customer_id: str,
    monac_id: str,
    supplier_text: str,
    customer_label: str,
) -> list[dict]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log.error("Playwright is not installed: pip install playwright && playwright install chromium")
        return []

    date_from, date_till = customer_date_range()
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
        "app_date_type": CUSTOMER_TENDER_DATE_TYPE,
        "app_date_from": date_from,
        "app_date_till": "",
        "app_date_tlll": date_till,
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
        return { status: resp.status, body: text };
    }
    """

    js_get_page = """
    async ({ params, pageNo }) => {
        const body = new URLSearchParams(params);
        body.set('page', String(pageNo));

        let resp = await fetch('/public/library/controller.php', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'X-Requested-With': 'XMLHttpRequest',
                'Accept': '*/*'
            },
            credentials: 'include',
            body: body.toString()
        });
        let text = await resp.text();

        if (resp.status === 200 && text.trim()) {
            return { status: resp.status, body: text, method: 'POST' };
        }

        const query = new URLSearchParams(params);
        query.set('page', String(pageNo));
        resp = await fetch('/public/library/controller.php?' + query.toString(), {
            method: 'GET',
            credentials: 'include',
            headers: { 'X-Requested-With': 'XMLHttpRequest', 'Accept': '*/*' }
        });
        text = await resp.text();
        return { status: resp.status, body: text, method: 'GET' };
    }
    """

    results: list[dict] = []

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            context = browser.new_context(
                user_agent=HEADERS["User-Agent"],
                locale="en-US",
                timezone_id="Asia/Tbilisi",
            )
            page = context.new_page()

            log.info("[%s] Opening portal...", customer_label)
            page.goto(f"{BASE_URL}/public/?lang=en", wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(1500)

            log.info("[%s] Searching customer tenders for %s", customer_label, CUSTOMER_TENDER_YEAR)
            result = page.evaluate(js_fetch, post_data)
            status = result.get("status", 0)
            body = result.get("body", "")

            if status != 200 or not body.strip():
                log.warning("[%s] Search failed: HTTP %s", customer_label, status)
                browser.close()
                return []

            first_page_rows = parse_customer_tender_rows(body, customer_id, customer_label)
            results.extend(first_page_rows)
            seen_page_keys = {
                row["customer_id"] + ":" + row["tender_id"]
                for row in first_page_rows
            }
            page_count = extract_page_count(body)
            log.info("[%s] Page 1/%d: %d rows", customer_label, page_count, len(results))

            for page_no in range(2, page_count + 1):
                page_result = page.evaluate(js_get_page, {"params": post_data, "pageNo": page_no})
                page_status = page_result.get("status", 0)
                page_body = page_result.get("body", "")
                if page_status != 200 or not page_body.strip():
                    log.warning("[%s] Page %d failed: HTTP %s", customer_label, page_no, page_status)
                    continue

                page_rows = parse_customer_tender_rows(page_body, customer_id, customer_label)
                new_page_rows = []
                for row in page_rows:
                    key = row["customer_id"] + ":" + row["tender_id"]
                    if key not in seen_page_keys:
                        seen_page_keys.add(key)
                        new_page_rows.append(row)

                if page_rows and not new_page_rows:
                    log.warning("[%s] Page %d repeated already-seen rows; stopping pagination", customer_label, page_no)
                    break

                results.extend(new_page_rows)
                log.info(
                    "[%s] Page %d/%d via %s: %d rows, %d new",
                    customer_label,
                    page_no,
                    page_count,
                    page_result.get("method", "unknown"),
                    len(page_rows),
                    len(new_page_rows),
                )

            browser.close()

    except Exception as exc:
        log.exception("[%s] Playwright error: %s", customer_label, exc)

    unique_rows = {row["customer_id"] + ":" + row["tender_id"]: row for row in results}
    return list(unique_rows.values())


def update_customer_tenders_csv() -> None:
    all_rows: list[dict] = []
    existing_ids = load_existing_customer_tender_ids()

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

    new_rows = [
        row for row in all_rows
        if row["customer_id"] + ":" + row["tender_id"] not in existing_ids
    ]
    failed_count = 0
    if existing_ids:
        if new_rows:
            sent_count = 0
            for row in new_rows:
                if send_telegram_message(build_customer_tender_alert(row)):
                    sent_count += 1
                else:
                    failed_count += 1
            log.info("Telegram bildirimi gonderilen yeni musteri tender sayisi: %d", sent_count)
        elif not send_telegram_message(build_no_new_tender_alert(len(all_rows))):
            failed_count += 1
    else:
        log.info("Ilk musteri tender taramasi; gecmis kayitlar icin yeni ihale bildirimi gonderilmedi.")
        if not send_telegram_message(build_no_new_tender_alert(len(all_rows))):
            failed_count += 1

    if failed_count:
        raise RuntimeError(f"Telegram bildirimi gonderilemeyen mesaj sayisi: {failed_count}")
    log.info("customer_tenders.csv güncellendi: %d satır", len(all_rows))


def run_once() -> None:
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
    parser.add_argument("--test-telegram", action="store_true", help="Telegram test mesajı gönder ve çık")

    args = parser.parse_args()

    CHECK_INTERVAL = args.interval

    if args.test_telegram:
        send_test_telegram_message()
    elif args.customers_only or args.once:
        run_once()
    else:
        run_loop()

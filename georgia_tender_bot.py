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
import requests
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

CHECK_INTERVAL = 300

SEEN_FILE = Path("seen_tenders_georgia.json")
CUSTOMER_TENDERS_CSV = Path("customer_tenders.csv")

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

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*; q=0.01",
}


def fetch_customer_tenders_playwright(
    customer_id: str,
    monac_id: str,
    supplier_text: str,
    customer_label: str,
) -> list[dict]:

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log.error("Playwright kurulu değil: pip install playwright && playwright install chromium")
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
        "app_date_tlll": "",
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
                args=["--no-sandbox", "--disable-dev-shm-usage"],
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

            soup = BeautifulSoup(body, "html.parser")
            rows_html = soup.select("tr[id^='A']")

            log.info("[%s] HTML tablo içinde %d tender satırı bulundu", customer_label, len(rows_html))

            today = datetime.now().strftime("%Y-%m-%d")

            for row in rows_html:
                row_id = row.get("id", "")
                app_id = row_id.replace("A", "")

                text = row.get_text(" ", strip=True)

                nat_match = re.search(r"NAT\d+", text)
                nat_number = nat_match.group(0) if nat_match else app_id

                amount_match = re.search(r"([\d'’.,\s]+)\s*GEL", text)
                budget = amount_match.group(0) if amount_match else ""

                results.append({
                    "customer_id": customer_id,
                    "customer_name": customer_label,
                    "tender_id": nat_number,
                    "title": text,
                    "organizer": "",
                    "budget": budget,
                    "currency": "GEL",
                    "status": "",
                    "publish_date": today,
                    "deadline": "",
                    "url": f"{BASE_URL}/public/?lang=ru&go={app_id}",
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

    if args.customers_only or args.once:
        run_once()
    else:
        run_loop()

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
from datetime import datetime
from pathlib import Path

# ── Настройки ─────────────────────────────────────────────────────────────────

TELEGRAM_TOKEN  = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

KEYWORDS: list[str] = []
CPV_CODES: list[str] = []
CHECK_INTERVAL = 300

SEEN_FILE            = Path("seen_tenders_georgia.json")
CUSTOMER_TENDERS_CSV = Path("customer_tenders.csv")

# Müşteriler: id_kodu → (isim, monac_id, gürcüce_isim)
CUSTOMERS = {
    "424611441": ("Lago",                  "12891", "ლაგო"),
    "436034916": ("Our Group",             "",      "ჩვენი ჯგუფი"),
    "405142634": ("Ander Konstrakshen",    "",      "ანდერ კონსტრაქშენი"),
    "425057341": ("Eplaini",               "",      "ეფლეინი"),
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

# ── URLs ───────────────────────────────────────────────────────────────────────

BASE_URL       = "https://tenders.procurement.gov.ge"
API_URL        = f"{BASE_URL}/public/api"
LIBRARY_URL    = f"{BASE_URL}/public/library"
CONTROLLER_URL = f"{LIBRARY_URL}/controller.php"

HEADERS = {"User-Agent": "TenderMonitorBot/1.0", "Accept": "application/json"}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)

# ── Seen store ────────────────────────────────────────────────────────────────

def load_seen() -> set[str]:
    if SEEN_FILE.exists():
        try:
            return set(json.loads(SEEN_FILE.read_text(encoding="utf-8")))
        except Exception:
            return set()
    return set()

def save_seen(seen: set[str]) -> None:
    SEEN_FILE.write_text(
        json.dumps(list(seen), ensure_ascii=False, indent=2), encoding="utf-8"
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
    if KEYWORDS and not any(kw.lower() in text for kw in KEYWORDS):
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
        log.error("Ошибка Telegram: %s", e)
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

# ── Genel tender API ───────────────────────────────────────────────────────────

def fetch_tenders(page: int = 1, page_size: int = 20) -> dict:
    params = {"page": page, "pageSize": page_size,
               "sortBy": "publishDate", "sortOrder": "desc"}
    try:
        resp = SESSION.get(f"{API_URL}/tenders", params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        log.error("Ошибка тендеров: %s", e)
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
        log.info("Новый тендер: %s", tender.get("title", tid))
        send_telegram(msg)
        seen.add(tid)
        new_count += 1
        time.sleep(0.5)
    return new_count

# ── MÜŞTERİ TENDER — PLAYWRIGHT ───────────────────────────────────────────────

def fetch_customer_tenders_playwright(
    customer_id: str,
    monac_id: str,
    org_name_ge: str,
    customer_label: str,
) -> list[dict]:
    """
    Playwright ile gerçek Chromium tarayıcı kullanarak controller.php'ye POST yapar.
    Anti-bot korumasını geçer çünkü gerçek bir tarayıcı fingerprint'i gönderir.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log.error("playwright kurulu değil: pip install playwright && playwright install chromium")
        return []

    post_data = {
        "action":                  "search_app",
        "lang":                    "ka",          # ← EKLENDİ
        "app_t":                   "0",
        "search":                  "",
        "app_reg_id":              "",
        "app_shems_id":            "0",
        "org_a":                   "",
        "app_monac_id":            monac_id,
        "org_b":                   org_name_ge,
        "app_particip_status_id":  "0",
        "app_donor_id":            "0",
        "app_status":              "0",
        "app_agr_status":          "0",
        "app_type":                "0",
        "app_basecode":            "0",
        "app_codes":               "",
        "app_date_type":           "1",
        "app_date_from":           "",
        "app_date_till":           "",
        "app_amount_from":         "",
        "app_amount_to":           "",
        "app_currency":            "2",
        "app_pricelist":           "0",
    }

    # JavaScript fetch kodu — tarayıcı context'i içinde çalışır
    js_fetch = """
    async (params) => {
        const body = new URLSearchParams(params);
        try {
            const resp = await fetch('/public/library/controller.php', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                credentials: 'include',
                body: body.toString()
            });
            const text = await resp.text();
            return { status: resp.status, body: text };
        } catch(e) {
            return { status: 0, body: e.toString() };
        }
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
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                locale="ka-GE",
                timezone_id="Asia/Tbilisi",
            )
            page = context.new_page()

            # 1) Sayfayı ziyaret et → cookie al
            log.info("  [%s] Sayfaya gidiliyor…", customer_label)
            page.goto(f"{BASE_URL}/public/library/", wait_until="networkidle", timeout=60_000)

            # 2) fetch ile POST yap (aynı origin → CORS yok)
            log.info("  [%s] controller.php POST…", customer_label)
            result = page.evaluate(js_fetch, post_data)

            status = result.get("status", 0)
            body   = result.get("body", "")
            log.info("  [%s] HTTP %d, body[:200]: %s", customer_label, status, body[:200])

            if status == 200 and body.strip():
                try:
                    data = json.loads(body)
                    # Yanıt liste veya dict olabilir
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

                    log.info("  [%s] %d tender bulundu", customer_label, len(raw_list))

                    today = datetime.now().strftime("%Y-%m-%d")
                    for t in raw_list:
                        results.append({
                            "customer_id":    customer_id,
                            "customer_name":  customer_label,
                            "tender_id":      t.get("app_id") or t.get("id") or "",
                            "title":          t.get("app_name") or t.get("title") or t.get("subject") or "",
                            "organizer":      t.get("org_name") or t.get("organizer") or "",
                            "budget":         t.get("app_amount") or t.get("budget") or t.get("estimatedValue") or "",
                            "currency":       t.get("currency_name") or "GEL",
                            "status":         t.get("app_status_name") or t.get("status") or "",
                            "publish_date":   t.get("app_reg_date") or t.get("publishDate") or today,
                            "deadline":       t.get("app_end_date") or t.get("submissionDeadline") or "",
                            "url":            (
                                t.get("url")
                                or f"{BASE_URL}/public/library/#/tenders/apinfo/"
                                   f"{t.get('app_id') or t.get('id', '')}"
                            ),
                        })
                except json.JSONDecodeError:
                    log.error("  [%s] JSON parse hatası: %s", customer_label, body[:300])
            else:
                log.error("  [%s] Hata: HTTP %d", customer_label, status)

            browser.close()
    except Exception as e:
        log.exception("  [%s] Playwright hatası: %s", customer_label, e)

    return results


def update_customer_tenders_csv() -> None:
    """Tüm müşteriler için tender çek, CSV'ye yaz."""
    all_rows: list[dict] = []

    for customer_id, (label, monac_id, org_name_ge) in CUSTOMERS.items():
        if not monac_id:
            log.warning("[%s] monac_id bilinmiyor, atlanıyor", label)
            continue

        log.info("Müşteri: %s (monac_id=%s)", label, monac_id)
        rows = fetch_customer_tenders_playwright(customer_id, monac_id, org_name_ge, label)
        all_rows.extend(rows)
        time.sleep(3)  # aşırı yük önleme

    if not all_rows:
        log.warning("Hiç müşteri tender'i bulunamadı, CSV güncellenmedi")
        return

    fieldnames = [
        "customer_id", "customer_name", "tender_id", "title",
        "organizer", "budget", "currency", "status",
        "publish_date", "deadline", "url",
    ]
    with open(CUSTOMER_TENDERS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    log.info("customer_tenders.csv güncellendi: %d satır", len(all_rows))


# ── ANA DÖNGÜ ─────────────────────────────────────────────────────────────────

def run_once() -> None:
    seen = load_seen()
    log.info("Проверка новых тендеров (Грузия)…")

    # Genel tenderler
    data = fetch_tenders(page=1, page_size=50)
    all_tenders = data.get("items") or data.get("tenders") or data.get("data") or []
    new = process_tenders(all_tenders, seen)
    save_seen(seen)
    log.info("Genel tenderler: %d yeni / %d toplam", new, len(all_tenders))

    # Müşteri tenderler
    log.info("Müşteri tender'leri güncelleniyor…")
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
            log.exception("Beklenmedik hata: %s", e)

        log.info("Sonraki kontrol %d sn sonra…", CHECK_INTERVAL)
        time.sleep(CHECK_INTERVAL)


# ── GİRİŞ NOKTASI ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Georgia Tender Bot")
    parser.add_argument("--once",     action="store_true",
                        help="Bir kez çalıştır ve çık")
    parser.add_argument("--interval", type=int, default=CHECK_INTERVAL,
                        help=f"Kontrol aralığı saniye (varsayılan {CHECK_INTERVAL})")
    parser.add_argument("--customers-only", action="store_true",
                        help="Sadece müşteri tender'lerini güncelle")
    args = parser.parse_args()

    CHECK_INTERVAL = args.interval

    if args.customers_only:
        update_customer_tenders_csv()
    elif args.once:
        run_once()
    else:
        run_loop()

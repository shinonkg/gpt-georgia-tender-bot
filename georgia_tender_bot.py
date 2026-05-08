import os
import json
import csv
import time
import re
import requests
from datetime import datetime
from bs4 import BeautifulSoup

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

SEEN_FILE = "seen_tenders.json"
CSV_FILE = "tenders.csv"

SEARCH_PARAMS = [
    {"app_basecode": "18965", "app_codes": "", "label": "37500000 - Игры / аттракционы"},
    {"app_basecode": "18951", "app_codes": "", "label": "37400000 - Спортивные товары"},
    {"app_basecode": "0", "app_codes": "37420000", "label": "37420000 - Гимнастическое оборудование"},
    {"app_basecode": "0", "app_codes": "37440000", "label": "37440000 - Фитнес оборудование"},
    {"app_basecode": "0", "app_codes": "45112700", "label": "45112700 - Ландшафтные работы"},
    {"app_basecode": "0", "app_codes": "45112720", "label": "45112720 - Спортивные площадки"},
    {"app_basecode": "18999", "app_codes": "", "label": "45100000 - Подготовка стройплощадки"},
]


def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(list(seen)), f, ensure_ascii=False, indent=2)


def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram secrets missing")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }

    r = requests.post(url, json=payload, timeout=20)
    print("Telegram:", r.status_code, r.text[:200])


def get_session():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
        "Referer": "https://tenders.procurement.gov.ge/public/?lang=ru",
        "Origin": "https://tenders.procurement.gov.ge",
    })

    try:
        session.get("https://tenders.procurement.gov.ge/public/?lang=ru", timeout=20)
        time.sleep(1)
    except Exception as e:
        print("Session init error:", e)

    return session


def search_tenders(params):
    session = get_session()

    data = {
        "action": "search_app",
        "app_t": "0",
        "search": "1",
        "app_reg_id": "",
        "app_shems_id": "0",
        "org_a": "",
        "app_monac_id": "0",
        "org_b": "",
        "app_particip_status_id": "0",
        "app_donor_id": "0",
        "app_status": "10",
        "app_agr_status": "0",
        "app_type": "0",
        "app_basecode": params.get("app_basecode", "0"),
        "app_codes": params.get("app_codes", ""),
        "app_date_type": "1",
        "app_date_from": "",
        "app_date_tlll": "",
        "app_amount_from": "",
        "app_amount_to": "",
        "app_currency": "2",
        "app_pricelist": "0",
    }

    try:
        r = session.post(
            "https://tenders.procurement.gov.ge/public/library/controller.php",
            data=data,
            timeout=30
        )

        print(f"Search {params['label']}:", r.status_code, len(r.text))

        if r.status_code == 200:
            return parse_tenders(r.text)

    except Exception as e:
        print("Search error:", e)

    return []


def parse_tenders(html):
    soup = BeautifulSoup(html, "html.parser")
    tenders = []

    rows = soup.find_all("tr", id=re.compile(r"^A\d+"))

    for row in rows:
        row_text = row.get_text(" ", strip=True)

        tender_id = ""
        row_id = row.get("id", "")
        if row_id.startswith("A"):
            tender_id = row_id.replace("A", "")

        onclick = row.get("onclick", "")
        match = re.search(r"ShowApp\((\d+)", onclick)
        if match:
            tender_id = match.group(1)

        reg_id = ""
        match = re.search(r"(NAT|SPA|GEO|CON|MEP|DAP)\d+", row_text)
        if match:
            reg_id = match.group(0)

        price = ""
        match = re.search(r"[\d\s`']+\.00\s*GEL", row_text)
        if match:
            price = match.group(0).strip()

        deadline = ""
        match = re.search(r"Срок принятия предложения[:\s]+(\d{2}\.\d{2}\.\d{4})", row_text)
        if match:
            deadline = match.group(1)

        org = ""
        match = re.search(r"Закупщик[:\s]+(.+?)(?:Категория|Предполагаемая|$)", row_text)
        if match:
            org = match.group(1).strip()

        name = ""
        match = re.search(r"Категория закупки[:\s]+(.+?)(?:Предполагаемая|Коды|$)", row_text)
        if match:
            name = match.group(1).strip()

        if tender_id:
            tenders.append({
                "id": tender_id,
                "reg_id": reg_id,
                "name": name,
                "org": org,
                "price": price,
                "deadline": deadline,
                "text": row_text[:300],
            })

    return tenders


def save_to_csv(tender, label):
    file_exists = os.path.exists(CSV_FILE)

    with open(CSV_FILE, "a", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)

        if not file_exists:
            writer.writerow([
                "date_found",
                "id",
                "reg_id",
                "name",
                "organization",
                "price",
                "deadline",
                "category",
                "link",
            ])

        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            tender.get("id", ""),
            tender.get("reg_id", ""),
            tender.get("name", ""),
            tender.get("org", ""),
            tender.get("price", ""),
            tender.get("deadline", ""),
            label,
            f"https://tenders.procurement.gov.ge/public/?lang=ru&go={tender.get('id', '')}",
        ])


def format_message(tender, label):
    link = f"https://tenders.procurement.gov.ge/public/?lang=ru&go={tender['id']}"

    return (
        f"🆕 <b>НОВЫЙ ТЕНДЕР</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📋 <b>{tender.get('reg_id') or 'Без номера'}</b>\n"
        f"🏷 {label}\n"
        f"🏢 {tender.get('org') or '—'}\n"
        f"💰 {tender.get('price') or '—'}\n"
        f"📅 Срок: {tender.get('deadline') or '—'}\n\n"
        f"🔗 <a href='{link}'>Открыть тендер</a>"
    )


def main():
    print("Bot started:", datetime.now())

    seen = load_seen()
    new_count = 0

    for params in SEARCH_PARAMS:
        label = params["label"]
        tenders = search_tenders(params)

        print(label, "found:", len(tenders))

        for tender in tenders:
            uid = tender.get("id") or tender.get("reg_id")

            if not uid:
                continue

            if uid not in seen:
                seen.add(uid)
                new_count += 1

                save_to_csv(tender, label)
                send_telegram(format_message(tender, label))

                time.sleep(1)

        time.sleep(2)

    save_seen(seen)

    send_telegram(
        f"✅ <b>GPT Tender Bot контроль завершён</b>\n"
        f"🆕 Новых тендеров: <b>{new_count}</b>\n"
        f"📌 Всего в базе: <b>{len(seen)}</b>"
    )

    print("Done. New:", new_count)


if __name__ == "__main__":
    main()

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
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://pibdlregqkpgwapdikdc.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "sb_publishable_xo8SnVOwSqDuKqXBqCT1ZA_xNAgssrv")

DATA_FILE = "tender_data.json"
CSV_FILE = "tenders.csv"
CUSTOMER_CSV_FILE = "customer_tenders.csv"

ALLOWED_CPVS = {
    "45100000": "45100000 - Работы по подготовке строительной площадки",
    "45112720": "45112720 - Ландшафтные работы на спортивных площадках и в зонах отдыха",
    "45112700": "45112700 - Ландшафтные работы",
    "45112723": "45112723 - Ландшафтные работы на игровых площадках",
    "45112710": "45112710 - Ландшафтные работы в зеленых зонах",
}

CUSTOMERS = {
    "424611441": "Lago",
    "436034916": "Our Group chveni jgupi",
    "405142634": "Ander Konstrakshen",
    "425057341": "Eplaini",
}

REAL_STATUSES = [
    "Объявлен",
    "Приём предложений начался",
    "Приём предложений завершён",
    "Отбор/оценка",
    "Победитель выявлен",
    "Завершён с отрицательным результатом",
    "Не состоялся",
    "Прекращён",
    "Идёт подготовка договора",
    "Договор подписан",
]

SEARCH_PARAMS = [
    {"app_basecode": "18999", "app_codes": "", "label": ALLOWED_CPVS["45100000"]},
    {"app_basecode": "0", "app_codes": "45112720", "label": ALLOWED_CPVS["45112720"]},
    {"app_basecode": "0", "app_codes": "45112700", "label": ALLOWED_CPVS["45112700"]},
    {"app_basecode": "0", "app_codes": "45112723", "label": ALLOWED_CPVS["45112723"]},
    {"app_basecode": "0", "app_codes": "45112710", "label": ALLOWED_CPVS["45112710"]},
]


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_ignored_tenders():
    ignored = set()
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/tender_reviews?review_status=eq.ignored&select=tender_id",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
            },
            timeout=15,
        )
        if r.status_code == 200:
            for row in r.json():
                ignored.add(str(row.get("tender_id", "")))
            print(f"Ignored tenders from Supabase: {len(ignored)}")
    except Exception as e:
        print(f"Supabase error: {e}")
    return ignored


def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram secrets missing")
        return
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            },
            timeout=20,
        )
        print("Telegram:", r.status_code)
    except Exception as e:
        print("Telegram error:", e)


def get_session():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,ka;q=0.8,en;q=0.7",
        "Referer": "https://tenders.procurement.gov.ge/public/?lang=ru",
        "Origin": "https://tenders.procurement.gov.ge",
        "Content-Type": "application/x-www-form-urlencoded",
    })
    try:
        session.get("https://tenders.procurement.gov.ge/public/?lang=ru", timeout=20)
        time.sleep(1)
    except Exception as e:
        print("Session init error:", e)
    return session


def get_tender_status(session, tender_id):
    try:
        r = session.get(
            f"https://tenders.procurement.gov.ge/public/?lang=ru&go={tender_id}",
            timeout=20,
        )
        if r.status_code != 200:
            return None
        html = r.text
        for status in REAL_STATUSES:
            if status in html:
                return status
        return None
    except Exception as e:
        print(f"Status fetch error for {tender_id}: {e}")
        return None


def extract_cpvs(text):
    matches = re.findall(r"\b\d{8}\b", text)
    cpvs = []
    for cpv in matches:
        if cpv in ALLOWED_CPVS and cpv not in cpvs:
            cpvs.append(cpv)
    return cpvs


def merge_cpvs(*lists):
    merged = []
    for cpv_list in lists:
        for cpv in cpv_list or []:
            if cpv in ALLOWED_CPVS and cpv not in merged:
                merged.append(cpv)
    return merged


def get_tender_attachments(session, tender_id):
    result = {"attachment_count": 0, "pdf_count": 0, "excel_count": 0, "image_count": 0}
    try:
        r = session.get(
            f"https://tenders.procurement.gov.ge/public/?lang=ru&go={tender_id}",
            timeout=20,
        )
        if r.status_code != 200:
            return result
        soup = BeautifulSoup(r.text, "html.parser")
        links = soup.find_all("a", href=True)
        attachment_links = []
        for a in links:
            href = a.get("href", "").lower()
            if any(x in href for x in [".pdf", ".xls", ".xlsx", ".doc", ".docx", ".jpg", ".jpeg", ".png", ".zip", "download"]):
                attachment_links.append(href)
        result["attachment_count"] = len(attachment_links)
        for href in attachment_links:
            if ".pdf" in href:
                result["pdf_count"] += 1
            elif ".xls" in href or ".xlsx" in href:
                result["excel_count"] += 1
            elif any(x in href for x in [".jpg", ".jpeg", ".png"]):
                result["image_count"] += 1
    except Exception as e:
        print("Attachment parse error:", e)
    return result


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
        m = re.search(r"ShowApp\((\d+)", onclick)
        if m:
            tender_id = m.group(1)
        reg_id = ""
        m = re.search(r"(NAT|SPA|GEO|CON|MEP|DAP)\d+", row_text)
        if m:
            reg_id = m.group(0)
        price = ""
        m = re.search(r"[\d\s`']+\.00\s*GEL", row_text)
        if m:
            price = m.group(0).strip()
        deadline = ""
        m = re.search(r"Срок принятия предложения[:\s]+(\d{2}\.\d{2}\.\d{4})", row_text)
        if m:
            deadline = m.group(1)
        org = ""
        m = re.search(r"Закупщик[:\s]+(.+?)(?:Категория|Предполагаемая|$)", row_text)
        if m:
            org = m.group(1).strip()
        name = ""
        m = re.search(r"Категория закупки[:\s]+(.+?)(?:Предполагаемая|Коды|$)", row_text)
        if m:
            name = m.group(1).strip()
        cpvs = extract_cpvs(row_text)
        if tender_id:
            tenders.append({
                "id": tender_id,
                "reg_id": reg_id,
                "name": name,
                "org": org,
                "price": price,
                "deadline": deadline,
                "cpvs": cpvs,
            })
    return tenders


def parse_customer_tenders(html, customer_id):
    """Müşterinin katıldığı ihaleleri parse et"""
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
        m = re.search(r"ShowApp\((\d+)", onclick)
        if m:
            tender_id = m.group(1)
        reg_id = ""
        m = re.search(r"(NAT|SPA|GEO|CON|MEP|DAP)\d+", row_text)
        if m:
            reg_id = m.group(0)
        price = ""
        m = re.search(r"[\d\s`']+\.00\s*GEL", row_text)
        if m:
            price = m.group(0).strip()
        deadline = ""
        m = re.search(r"Срок принятия предложения[:\s]+(\d{2}\.\d{2}\.\d{4})", row_text)
        if m:
            deadline = m.group(1)
        publish_date = ""
        m = re.search(r"Дата объявления[:\s]+(\d{2}\.\d{2}\.\d{4})", row_text)
        if not m:
            m = re.search(r"(\d{2}\.\d{2}\.\d{4})", row_text)
        if m:
            publish_date = m.group(1)
        org = ""
        m = re.search(r"Закупщик[:\s]+(.+?)(?:Категория|Предполагаемая|$)", row_text)
        if m:
            org = m.group(1).strip()
        name = ""
        m = re.search(r"Категория закупки[:\s]+(.+?)(?:Предполагаемая|Коды|$)", row_text)
        if m:
            name = m.group(1).strip()
        status = ""
        for s in REAL_STATUSES:
            if s in row_text:
                status = s
                break
        if tender_id:
            tenders.append({
                "customer_id": customer_id,
                "id": tender_id,
                "reg_id": reg_id,
                "name": name,
                "org": org,
                "price": price,
                "deadline": deadline,
                "publish_date": publish_date,
                "status": status or "Объявлен",
                "link": f"https://tenders.procurement.gov.ge/public/?lang=ru&go={tender_id}",
            })
    return tenders


def search_customer_tenders(customer_id, customer_name):
    """Tedarikçi ID'sine göre müşterinin tüm ihalelerini çek"""
    session = get_session()
    data = {
        "action": "search_app", "app_t": "0", "search": "1",
        "app_reg_id": "", "app_shems_id": "0", "org_a": "",
        "app_monac_id": "0",
        "org_b": customer_id,
        "app_particip_status_id": "0",
        "app_donor_id": "0",
        "app_status": "0",
        "app_agr_status": "0",
        "app_type": "0",
        "app_basecode": "0",
        "app_codes": "",
        "app_date_type": "1", "app_date_from": "", "app_date_tlll": "",
        "app_amount_from": "", "app_amount_to": "",
        "app_currency": "2", "app_pricelist": "0",
    }
    try:
        session.get("https://tenders.procurement.gov.ge/public/?lang=ru", timeout=20)
        time.sleep(1)
        r = session.post(
            "https://tenders.procurement.gov.ge/public/library/controller.php",
            data=data, timeout=30,
        )
        print(f"Customer [{customer_name}] {customer_id}: HTTP {r.status_code}, {len(r.text)} bytes")
        if r.status_code == 200:
            tenders = parse_customer_tenders(r.text, customer_id)
            print(f"  → {len(tenders)} tenders found")
            return tenders
    except Exception as e:
        print(f"Customer search error [{customer_name}]: {e}")
    return []


def save_customer_csv(all_tenders):
    """Tüm müşteri ihalelerini customer_tenders.csv'ye kaydet"""
    with open(CUSTOMER_CSV_FILE, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "customer_id", "id", "reg_id", "name", "org",
            "price", "deadline", "publish_date", "status", "link",
        ])
        for t in all_tenders:
            writer.writerow([
                t.get("customer_id", ""),
                t.get("id", ""),
                t.get("reg_id", ""),
                t.get("name", ""),
                t.get("org", ""),
                t.get("price", ""),
                t.get("deadline", ""),
                t.get("publish_date", ""),
                t.get("status", ""),
                t.get("link", ""),
            ])
    print(f"Saved {len(all_tenders)} customer tenders to {CUSTOMER_CSV_FILE}")


def search_tenders(params):
    session = get_session()
    data = {
        "action": "search_app", "app_t": "0", "search": "1",
        "app_reg_id": "", "app_shems_id": "0", "org_a": "",
        "app_monac_id": "0", "org_b": "", "app_particip_status_id": "0",
        "app_donor_id": "0", "app_status": "10", "app_agr_status": "0",
        "app_type": "0",
        "app_basecode": params.get("app_basecode", "0"),
        "app_codes": params.get("app_codes", ""),
        "app_date_type": "1", "app_date_from": "", "app_date_tlll": "",
        "app_amount_from": "", "app_amount_to": "",
        "app_currency": "2", "app_pricelist": "0",
    }
    try:
        session.get("https://tenders.procurement.gov.ge/public/?lang=ru", timeout=20)
        time.sleep(1)
        r = session.post(
            "https://tenders.procurement.gov.ge/public/library/controller.php",
            data=data, timeout=30,
        )
        print(f"Search {params['label']}:", r.status_code, len(r.text))
        if r.status_code == 200:
            tenders = parse_tenders(r.text)
            for tender in tenders:
                tender_id = tender.get("id")
                if tender_id:
                    attachments = get_tender_attachments(session, tender_id)
                    tender.update(attachments)
                    print(f"  {tender.get('reg_id') or tender_id}: {attachments['attachment_count']} attachments")
                    time.sleep(0.4)
            return tenders
    except Exception as e:
        print("Search error:", e)
    return []


def save_csv(data):
    with open(CSV_FILE, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "date_found", "last_seen", "id", "reg_id", "name", "org",
            "price", "deadline", "status", "cpvs", "label",
            "attachment_count", "pdf_count", "excel_count", "image_count", "link",
        ])
        for tender_id, t in data.items():
            cpv_labels = [ALLOWED_CPVS.get(cpv, cpv) for cpv in t.get("cpvs", [])]
            writer.writerow([
                t.get("date_found", ""), t.get("last_seen", ""),
                tender_id, t.get("reg_id", ""), t.get("name", ""),
                t.get("org", ""), t.get("price", ""), t.get("deadline", ""),
                t.get("status", ""), "|".join(t.get("cpvs", [])),
                " | ".join(cpv_labels),
                t.get("attachment_count", 0), t.get("pdf_count", 0),
                t.get("excel_count", 0), t.get("image_count", 0),
                f"https://tenders.procurement.gov.ge/public/?lang=ru&go={tender_id}",
            ])


def format_new_message(t):
    cpv_lines = "\n".join(f"🏷 {ALLOWED_CPVS.get(cpv, cpv)}" for cpv in t.get("cpvs", []))
    return (
        f"🆕 <b>НОВЫЙ ТЕНДЕР</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📋 <b>{t.get('reg_id') or 'Без номера'}</b>\n"
        f"📌 Статус: <b>{t.get('status')}</b>\n"
        f"{cpv_lines}\n"
        f"🏢 {t.get('org') or '—'}\n"
        f"💰 {t.get('price') or '—'}\n"
        f"📅 Срок: {t.get('deadline') or '—'}\n\n"
        f"🔗 https://tenders.procurement.gov.ge/public/?lang=ru&go={t.get('id')}"
    )


def format_status_message(t, old_status, new_status):
    return (
        f"🔄 <b>СТАТУС ИЗМЕНИЛСЯ</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📋 <b>{t.get('reg_id') or t.get('id')}</b>\n"
        f"Было: <b>{old_status}</b>\n"
        f"Стало: <b>{new_status}</b>\n\n"
        f"🔗 https://tenders.procurement.gov.ge/public/?lang=ru&go={t.get('id')}"
    )


def main():
    print("Bot started:", datetime.now())

    db = load_data()
    active_now = set()
    ignored_tenders = get_ignored_tenders()
    print(f"Total ignored: {len(ignored_tenders)}")

    new_count = 0
    updated_count = 0

    # ── Tender araması (CPV bazlı) ──
    for params in SEARCH_PARAMS:
        tenders = search_tenders(params)
        print(params["label"], "found:", len(tenders))
        search_cpv = params["label"].split(" - ")[0]

        for t in tenders:
            tid = t.get("id")
            if not tid:
                continue
            active_now.add(tid)
            if tid in ignored_tenders:
                print(f"  Skipping ignored tender: {t.get('reg_id') or tid}")
                if tid in db:
                    db[tid]["last_seen"] = now_str()
                continue
            existing = db.get(tid, {})
            merged_cpvs = merge_cpvs(existing.get("cpvs", []), t.get("cpvs", []), [search_cpv])
            if tid not in db:
                db[tid] = {
                    "id": tid,
                    "reg_id": t.get("reg_id", ""),
                    "name": t.get("name", ""),
                    "org": t.get("org", ""),
                    "price": t.get("price", ""),
                    "deadline": t.get("deadline", ""),
                    "cpvs": merged_cpvs,
                    "status": "Объявлен",
                    "date_found": now_str(),
                    "last_seen": now_str(),
                    "attachment_count": t.get("attachment_count", 0),
                    "pdf_count": t.get("pdf_count", 0),
                    "excel_count": t.get("excel_count", 0),
                    "image_count": t.get("image_count", 0),
                }
                new_count += 1
                send_telegram(format_new_message(db[tid]))
            else:
                db[tid]["reg_id"] = t.get("reg_id") or db[tid].get("reg_id", "")
                db[tid]["name"] = t.get("name") or db[tid].get("name", "")
                db[tid]["org"] = t.get("org") or db[tid].get("org", "")
                db[tid]["price"] = t.get("price") or db[tid].get("price", "")
                db[tid]["deadline"] = t.get("deadline") or db[tid].get("deadline", "")
                db[tid]["cpvs"] = merged_cpvs
                db[tid]["last_seen"] = now_str()
                db[tid]["attachment_count"] = t.get("attachment_count", db[tid].get("attachment_count", 0))
                db[tid]["pdf_count"] = t.get("pdf_count", db[tid].get("pdf_count", 0))
                db[tid]["excel_count"] = t.get("excel_count", db[tid].get("excel_count", 0))
                db[tid]["image_count"] = t.get("image_count", db[tid].get("image_count", 0))

        time.sleep(2)

    # ── Statü kontrolü ──
    session = get_session()
    for tid, tender in db.items():
        if tid in ignored_tenders:
            continue
        if tid not in active_now:
            old_status = tender.get("status", "Объявлен")
            if old_status in ["Объявлен", "Приём предложений начался"]:
                print(f"Checking status for {tender.get('reg_id') or tid}...")
                real_status = get_tender_status(session, tid)
                if real_status and real_status != old_status:
                    tender["status"] = real_status
                    updated_count += 1
                    send_telegram(format_status_message(tender, old_status, real_status))
                    print(f"  Status changed: {old_status} → {real_status}")
                else:
                    print(f"  Status unchanged: {old_status}")
                time.sleep(1)

    save_data(db)
    save_csv(db)

    # ── Müşteri ihaleleri ──
    print("\n=== Fetching customer tenders ===")
    all_customer_tenders = []
    for customer_id, customer_name in CUSTOMERS.items():
        tenders = search_customer_tenders(customer_id, customer_name)
        all_customer_tenders.extend(tenders)
        time.sleep(2)

    save_customer_csv(all_customer_tenders)

    send_telegram(
        f"✅ <b>GPT Tender Bot цикл завершён</b>\n"
        f"🆕 Новых: <b>{new_count}</b>\n"
        f"🔄 Обновлено: <b>{updated_count}</b>\n"
        f"📌 Всего: <b>{len(db)}</b>\n"
        f"👥 Клиентских тендеров: <b>{len(all_customer_tenders)}</b>"
    )

    print("Done. New:", new_count, "Updated:", updated_count, "Total:", len(db))
    print("Customer tenders:", len(all_customer_tenders))


if __name__ == "__main__":
    main()

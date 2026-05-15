import fs from "node:fs";
import {
  BASE_URL,
  extractPageCount,
  parseMainTenderRows,
  rowsToCsv,
} from "./procurement_parsers.mjs";

const MAIN_TENDER_DATE_FROM = process.env.MAIN_TENDER_DATE_FROM || "01.03.2026";
const MAIN_TENDER_DATE_TILL = process.env.MAIN_TENDER_DATE_TILL || "31.12.2026";
const MAIN_TENDER_DATE_TYPE = process.env.MAIN_TENDER_DATE_TYPE || "1";
const MAIN_TENDER_BASECODE = process.env.MAIN_TENDER_BASECODE || "18999";
const MAX_MAIN_TENDER_PAGES = Number(process.env.MAX_MAIN_TENDER_PAGES || 50);

const fieldnames = [
  "date_found",
  "last_seen",
  "id",
  "reg_id",
  "published",
  "name",
  "org",
  "price",
  "deadline",
  "status",
  "cpvs",
  "label",
  "attachment_count",
  "pdf_count",
  "excel_count",
  "image_count",
  "link",
];

async function openSession() {
  const resp = await fetch(`${BASE_URL}/public/?lang=en`);
  const cookie = resp.headers.get("set-cookie")?.split(";")[0] || "";
  if (!resp.ok) throw new Error(`Portal open failed: HTTP ${resp.status}`);
  return cookie;
}

async function searchPage(cookie, params) {
  const body = new URLSearchParams(params);
  const resp = await fetch(`${BASE_URL}/public/library/controller.php`, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
      "X-Requested-With": "XMLHttpRequest",
      "Accept": "*/*",
      "Cookie": cookie,
    },
    body,
  });
  const text = await resp.text();
  if (!resp.ok) throw new Error(`Search failed: HTTP ${resp.status}`);
  return text;
}

const cookie = await openSession();
const baseParams = {
  action: "search_app",
  app_t: "0",
  search: "",
  app_reg_id: "",
  app_shems_id: "0",
  org_a: "",
  app_monac_id: "0",
  org_b: "",
  app_particip_status_id: "0",
  app_donor_id: "0",
  app_status: "0",
  app_agr_status: "0",
  app_type: "0",
  app_basecode: MAIN_TENDER_BASECODE,
  app_codes: "",
  app_date_type: MAIN_TENDER_DATE_TYPE,
  app_date_from: MAIN_TENDER_DATE_FROM,
  app_date_till: "",
  app_date_tlll: MAIN_TENDER_DATE_TILL,
  app_amount_from: "",
  app_amount_to: "",
  app_currency: "2",
  app_pricelist: "0",
};

const firstHtml = await searchPage(cookie, baseParams);
const pageCount = extractPageCount(firstHtml, MAX_MAIN_TENDER_PAGES);
const rows = parseMainTenderRows(firstHtml);
const seen = new Set(rows.map(row => row.id));
console.log(`Main tenders: page 1/${pageCount}, rows=${rows.length}`);

for (let page = 2; page <= pageCount; page++) {
  const html = await searchPage(cookie, { ...baseParams, page: String(page) });
  const pageRows = parseMainTenderRows(html);
  const newRows = pageRows.filter(row => {
    if (seen.has(row.id)) return false;
    seen.add(row.id);
    return true;
  });
  if (pageRows.length && !newRows.length) break;
  rows.push(...newRows);
  console.log(`Main tenders: page ${page}/${pageCount}, rows=${pageRows.length}, new=${newRows.length}`);
}

rows.sort((a, b) => {
  const dateDiff = (new Date(a.date_found).getTime() || 0) - (new Date(b.date_found).getTime() || 0);
  return dateDiff || String(a.reg_id).localeCompare(String(b.reg_id));
});

fs.writeFileSync("tenders.csv", rowsToCsv(fieldnames, rows), "utf8");
fs.writeFileSync("tender_data.json", JSON.stringify(rows, null, 2) + "\n", "utf8");
console.log(`tenders.csv updated: ${rows.length} rows`);

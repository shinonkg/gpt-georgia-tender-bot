import fs from "node:fs";

const BASE_URL = "https://tenders.procurement.gov.ge";
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

function decodeHtml(value) {
  return String(value || "")
    .replace(/&quot;/g, '"')
    .replace(/&#039;|&apos;/g, "'")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&nbsp;/g, " ");
}

function stripTags(value) {
  return decodeHtml(String(value || "").replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim());
}

function csvCell(value) {
  return `"${String(value ?? "").replace(/"/g, '""')}"`;
}

function toIsoDate(dateText) {
  const match = String(dateText || "").match(/^(\d{2})\.(\d{2})\.(\d{4})$/);
  if (!match) return "";
  return `${match[3]}-${match[2]}-${match[1]}`;
}

function normalizeStatus(text) {
  const value = String(text || "");
  const statuses = [
    "Tender announced",
    "Bidding commenced",
    "Bidding completed",
    "Selection/Evaluation",
    "Winner identified",
    "Finalization of contract",
    "Contract awarded",
    "Contract not awarded",
    "No bids received",
    "Cancelled",
  ];
  return statuses.find(status => value.toLowerCase().startsWith(status.toLowerCase())) || "";
}

function extractPageCount(html) {
  const match = String(html).match(/page:\s*\d+\s*\/\s*(\d+)/i)
    || String(html).match(/plastpage\s*=\s*eval\(['"]?(\d+)['"]?\)/i);
  if (!match) return 1;
  return Math.max(1, Math.min(MAX_MAIN_TENDER_PAGES, Number(match[1])));
}

function parseRows(html) {
  const rows = [];
  const rowPattern = /<tr[^>]+id=["']A(\d+)["'][\s\S]*?<\/tr>/gi;
  let match;

  while ((match = rowPattern.exec(html))) {
    const appId = match[1];
    const text = stripTags(match[0]);
    const nat = text.match(/NAT\d+/i)?.[0] || appId;
    const statusText = text.match(/^(.*?)\s+Electronic Tender/i)?.[1]?.trim() || "";
    const status = normalizeStatus(statusText);
    const published = text.match(/Procurement announcment date:\s*([0-9.]+)/i)?.[1]?.trim() || "";
    const deadline = text.match(/Offer reception term:\s*([0-9.]+)/i)?.[1]?.trim() || "";
    const organizer = text.match(/Procuring entities:\s*(.*?)\s*Procuring category:/i)?.[1]?.trim() || "";
    const category = text.match(/Procuring category:\s*(.*?)\s*Estimated value/i)?.[1]?.trim() || "";
    const price = text.match(/Estimated value of procurement:\s*([\d'`’.,\s]+GEL)/i)?.[1]?.trim() || "";
    const cpv = category.match(/^(\d{8})/)?.[1] || "45100000";
    const publishedIso = toIsoDate(published);

    rows.push({
      date_found: publishedIso,
      last_seen: new Date().toISOString().slice(0, 16).replace("T", " "),
      id: appId,
      reg_id: nat,
      published,
      name: category || "45100000-Site preparation work",
      org: organizer,
      price,
      deadline,
      status,
      cpvs: cpv,
      label: category ? `${cpv} - ${category.replace(/^\d{8}-/, "")}` : `${cpv} - Site preparation work`,
      attachment_count: "0",
      pdf_count: "0",
      excel_count: "0",
      image_count: "0",
      link: `${BASE_URL}/public/?lang=ru&go=${appId}`,
    });
  }

  return rows;
}

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
const pageCount = extractPageCount(firstHtml);
const rows = parseRows(firstHtml);
const seen = new Set(rows.map(row => row.id));
console.log(`Main tenders: page 1/${pageCount}, rows=${rows.length}`);

for (let page = 2; page <= pageCount; page++) {
  const html = await searchPage(cookie, { ...baseParams, page: String(page) });
  const pageRows = parseRows(html);
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

const csv = [
  fieldnames.join(","),
  ...rows.map(row => fieldnames.map(name => csvCell(row[name])).join(",")),
].join("\n") + "\n";

fs.writeFileSync("tenders.csv", csv, "utf8");
fs.writeFileSync("tender_data.json", JSON.stringify(rows, null, 2) + "\n", "utf8");
console.log(`tenders.csv updated: ${rows.length} rows`);

import fs from "node:fs";

const BASE_URL = "https://tenders.procurement.gov.ge";
const CUSTOMER_TENDER_YEAR = Number(process.env.CUSTOMER_TENDER_YEAR || new Date().getFullYear());
const CUSTOMER_TENDER_DATE_TYPE = process.env.CUSTOMER_TENDER_DATE_TYPE || "2";
const MAX_CUSTOMER_PAGES = Number(process.env.MAX_CUSTOMER_TENDER_PAGES || 25);

const CUSTOMERS = {
  "424611441": ["Lago", "12891", "lago"],
  "436034916": ["Our Group chveni jgupi", "36827", "our group"],
  "405142634": ["Ander Konstrakshen", "104814", "ander konstrakshen"],
  "425057341": ["Eplaini", "71057", "eplaini"],
};

const fieldnames = [
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

function extractPageCount(html) {
  const patterns = [
    /page:\s*\d+\s*\/\s*(\d+)/i,
    /plastpage\s*=\s*eval\(['"]?(\d+)['"]?\)/i,
    /lastpage\s*=\s*eval\(['"]?(\d+)['"]?\)/i,
    /page_count\s*[:=]\s*['"]?(\d+)/i,
  ];
  for (const pattern of patterns) {
    const match = String(html).match(pattern);
    if (match) return Math.max(1, Math.min(MAX_CUSTOMER_PAGES, Number(match[1])));
  }
  return 1;
}

function parseRows(html, customerId, customerName) {
  const rows = [];
  const rowPattern = /<tr[^>]+id=["']A(\d+)["'][\s\S]*?<\/tr>/gi;
  let match;

  while ((match = rowPattern.exec(html))) {
    const appId = match[1];
    const text = stripTags(match[0]);
    const nat = text.match(/NAT\d+/i)?.[0] || appId;
    const budget = text.match(/([\d'`’.,\s]+)\s*GEL/i)?.[0]?.trim() || "";
    const published = text.match(/Procurement announcment date:\s*([0-9.]+)/i)?.[1]?.trim() || "";
    const deadline = text.match(/Offer reception term:\s*([0-9.]+)/i)?.[1]?.trim() || "";
    const organizer = text.match(/Procuring entities:\s*(.*?)\s*Procuring category:/i)?.[1]?.trim() || "";

    rows.push({
      customer_id: customerId,
      customer_name: customerName,
      tender_id: nat,
      title: text,
      organizer,
      budget,
      currency: "GEL",
      status: /Contract awarded/i.test(text) ? "Contract awarded" : "",
      publish_date: published,
      deadline,
      url: `${BASE_URL}/public/?lang=ru&go=${appId}`,
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

async function fetchCustomer(cookie, customerId, customerName, monacId, supplierText) {
  const baseParams = {
    action: "search_app",
    app_t: "0",
    search: "",
    app_reg_id: "",
    app_shems_id: "0",
    org_a: "",
    app_monac_id: monacId,
    org_b: supplierText,
    app_particip_status_id: "0",
    app_donor_id: "0",
    app_status: "0",
    app_agr_status: "0",
    app_type: "0",
    app_basecode: "0",
    app_codes: "",
    app_date_type: CUSTOMER_TENDER_DATE_TYPE,
    app_date_from: `01.01.${CUSTOMER_TENDER_YEAR}`,
    app_date_till: "",
    app_date_tlll: `31.12.${CUSTOMER_TENDER_YEAR}`,
    app_amount_from: "",
    app_amount_to: "",
    app_currency: "2",
    app_pricelist: "0",
  };

  const firstHtml = await searchPage(cookie, baseParams);
  const pageCount = extractPageCount(firstHtml);
  const rows = parseRows(firstHtml, customerId, customerName);
  const seen = new Set(rows.map(row => `${row.customer_id}:${row.tender_id}`));
  console.log(`${customerName}: page 1/${pageCount}, rows=${rows.length}`);

  for (let page = 2; page <= pageCount; page++) {
    const html = await searchPage(cookie, { ...baseParams, page: String(page) });
    const pageRows = parseRows(html, customerId, customerName);
    const newRows = pageRows.filter(row => {
      const key = `${row.customer_id}:${row.tender_id}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
    if (pageRows.length && !newRows.length) break;
    rows.push(...newRows);
    console.log(`${customerName}: page ${page}/${pageCount}, rows=${pageRows.length}, new=${newRows.length}`);
  }

  return rows;
}

const cookie = await openSession();
const allRows = [];

for (const [customerId, [customerName, monacId, supplierText]] of Object.entries(CUSTOMERS)) {
  allRows.push(...await fetchCustomer(cookie, customerId, customerName, monacId, supplierText));
}

const uniqueRows = [...new Map(allRows.map(row => [`${row.customer_id}:${row.tender_id}`, row])).values()];
const csv = [
  fieldnames.join(","),
  ...uniqueRows.map(row => fieldnames.map(name => csvCell(row[name])).join(",")),
].join("\n") + "\n";

fs.writeFileSync("customer_tenders.csv", csv, "utf8");
console.log(`customer_tenders.csv updated: ${uniqueRows.length} rows`);

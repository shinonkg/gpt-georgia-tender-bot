export const BASE_URL = "https://tenders.procurement.gov.ge";

export function decodeHtml(value) {
  return String(value || "")
    .replace(/&quot;/g, '"')
    .replace(/&#039;|&apos;/g, "'")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&nbsp;/g, " ");
}

export function stripTags(value) {
  return decodeHtml(String(value || "").replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim());
}

export function csvCell(value) {
  return `"${String(value ?? "").replace(/"/g, '""')}"`;
}

export function toIsoDate(dateText) {
  const match = String(dateText || "").match(/^(\d{2})\.(\d{2})\.(\d{4})$/);
  if (!match) return "";
  return `${match[3]}-${match[2]}-${match[1]}`;
}

export function normalizeStatus(text) {
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

export function extractPageCount(html, maxPages = 50) {
  const patterns = [
    /page:\s*\d+\s*\/\s*(\d+)/i,
    /plastpage\s*=\s*eval\(['"]?(\d+)['"]?\)/i,
    /lastpage\s*=\s*eval\(['"]?(\d+)['"]?\)/i,
    /page_count\s*[:=]\s*['"]?(\d+)/i,
  ];
  for (const pattern of patterns) {
    const match = String(html).match(pattern);
    if (match) return Math.max(1, Math.min(maxPages, Number(match[1])));
  }
  return 1;
}

function extractCommonFields(rowHtml) {
  const text = stripTags(rowHtml);
  return {
    text,
    nat: text.match(/NAT\d+/i)?.[0] || "",
    published: text.match(/Procurement announcment date:\s*([0-9.]+)/i)?.[1]?.trim() || "",
    deadline: text.match(/Offer reception term:\s*([0-9.]+)/i)?.[1]?.trim() || "",
    organizer: text.match(/Procuring entities:\s*(.*?)\s*Procuring category:/i)?.[1]?.trim() || "",
  };
}

export function officialTenderUrl(appId) {
  return `${BASE_URL}/public/?lang=ru&go=${appId}`;
}

export function parseMainTenderRows(html, { lastSeen = new Date() } = {}) {
  const rows = [];
  const rowPattern = /<tr[^>]+id=["']A(\d+)["'][\s\S]*?<\/tr>/gi;
  let match;

  while ((match = rowPattern.exec(html))) {
    const appId = match[1];
    const { text, nat, published, deadline, organizer } = extractCommonFields(match[0]);
    const statusText = text.match(/^(.*?)\s+Electronic Tender/i)?.[1]?.trim() || "";
    const status = normalizeStatus(statusText);
    const category = text.match(/Procuring category:\s*(.*?)\s*Estimated value/i)?.[1]?.trim() || "";
    const price = text.match(/Estimated value of procurement:\s*([\d'`\u2019.,\s]+GEL)/i)?.[1]?.trim() || "";
    const cpv = category.match(/^(\d{8})/)?.[1] || "45100000";
    const publishedIso = toIsoDate(published);

    rows.push({
      date_found: publishedIso,
      last_seen: lastSeen.toISOString().slice(0, 16).replace("T", " "),
      id: appId,
      reg_id: nat || appId,
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
      link: officialTenderUrl(appId),
    });
  }

  return rows;
}

export function parseCustomerTenderRows(html, customerId, customerName) {
  const rows = [];
  const rowPattern = /<tr[^>]+id=["']A(\d+)["'][\s\S]*?<\/tr>/gi;
  let match;

  while ((match = rowPattern.exec(html))) {
    const appId = match[1];
    const { text, nat, published, deadline, organizer } = extractCommonFields(match[0]);
    const budget = text.match(/([\d'`\u2019.,\s]+)\s*GEL/i)?.[0]?.trim() || "";

    rows.push({
      customer_id: customerId,
      customer_name: customerName,
      tender_id: nat || appId,
      title: text,
      organizer,
      budget,
      currency: "GEL",
      status: /Contract awarded/i.test(text) ? "Contract awarded" : "",
      publish_date: published,
      deadline,
      url: officialTenderUrl(appId),
    });
  }

  return rows;
}

export function rowsToCsv(fieldnames, rows) {
  return [
    fieldnames.join(","),
    ...rows.map(row => fieldnames.map(name => csvCell(row[name])).join(",")),
  ].join("\n") + "\n";
}

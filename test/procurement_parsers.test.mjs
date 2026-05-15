import assert from "node:assert/strict";
import test from "node:test";
import {
  csvCell,
  extractPageCount,
  officialTenderUrl,
  parseCustomerTenderRows,
  parseMainTenderRows,
  rowsToCsv,
  toIsoDate,
} from "../scripts/procurement_parsers.mjs";

const fixtureHtml = `
<table>
  <tr id="A680266">
    <td>
      Winner identified Electronic Tender
      Announcment number: <strong>NAT260006413</strong>
      Procurement announcment date: 30.03.2026
      Offer reception term: 20.04.2026
      Procuring entities: City Hall &amp; Roads Department
      Procuring category: 45100000-Site preparation work
      Estimated value of procurement: 1'234.56 GEL
    </td>
  </tr>
</table>
<div class="pager">6 Record(s) (page: 1/2)</div>
`;

test("extractPageCount supports portal pager variants and caps large values", () => {
  assert.equal(extractPageCount(fixtureHtml, 25), 2);
  assert.equal(extractPageCount("plastpage = eval('9')", 25), 9);
  assert.equal(extractPageCount("lastpage = eval(8)", 25), 8);
  assert.equal(extractPageCount("page_count: 7", 25), 7);
  assert.equal(extractPageCount("page: 1/999", 25), 25);
  assert.equal(extractPageCount("no pager", 25), 1);
});

test("parseMainTenderRows extracts tender identity, dates, organizer, budget, status, and link", () => {
  const [row] = parseMainTenderRows(fixtureHtml, { lastSeen: new Date("2026-05-15T04:05:00Z") });

  assert.equal(row.id, "680266");
  assert.equal(row.reg_id, "NAT260006413");
  assert.equal(row.published, "30.03.2026");
  assert.equal(row.date_found, "2026-03-30");
  assert.equal(row.deadline, "20.04.2026");
  assert.equal(row.org, "City Hall & Roads Department");
  assert.equal(row.price, "1'234.56 GEL");
  assert.equal(row.status, "Winner identified");
  assert.equal(row.cpvs, "45100000");
  assert.equal(row.link, officialTenderUrl("680266"));
  assert.equal(row.last_seen, "2026-05-15 04:05");
});

test("parseCustomerTenderRows preserves supplier data and awarded status", () => {
  const [row] = parseCustomerTenderRows(fixtureHtml, "424611441", "Lago");

  assert.equal(row.customer_id, "424611441");
  assert.equal(row.customer_name, "Lago");
  assert.equal(row.tender_id, "NAT260006413");
  assert.equal(row.organizer, "City Hall & Roads Department");
  assert.equal(row.budget, "1'234.56 GEL");
  assert.equal(row.currency, "GEL");
  assert.equal(row.status, "");
  assert.equal(row.publish_date, "30.03.2026");
  assert.equal(row.deadline, "20.04.2026");
  assert.equal(row.url, officialTenderUrl("680266"));
});

test("parseCustomerTenderRows falls back to app id when NAT number is missing", () => {
  const [row] = parseCustomerTenderRows("<tr id=\"A123\"><td>Contract awarded Electronic Tender</td></tr>", "1", "Customer");

  assert.equal(row.tender_id, "123");
  assert.equal(row.status, "Contract awarded");
});

test("CSV helpers quote cells and preserve headers", () => {
  assert.equal(csvCell('A "quoted", value'), '"A ""quoted"", value"');
  assert.equal(rowsToCsv(["id", "name"], [{ id: 1, name: "A, B" }]), 'id,name\n"1","A, B"\n');
});

test("toIsoDate rejects unexpected formats", () => {
  assert.equal(toIsoDate("15.05.2026"), "2026-05-15");
  assert.equal(toIsoDate("2026-05-15"), "");
});

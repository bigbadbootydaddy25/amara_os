import PDFDocument from "pdfkit";
import type { Deal, Buyer } from "../db/dealsSchema";
import type { BuyBoxResult } from "./buybox";

const BRAND_BLUE   = "#1e3a8a";
const BRAND_PURPLE = "#7c3aed";
const DARK         = "#111827";
const GRAY         = "#6b7280";
const LIGHT_GRAY   = "#f3f4f6";
const GREEN        = "#15803d";
const RED          = "#dc2626";
const AMBER        = "#b45309";

function money(v: string | number | null | undefined): string {
  if (v == null) return "N/A";
  const n = Number(v);
  if (isNaN(n)) return "N/A";
  return "$" + n.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

function pct(v: string | number | null | undefined, digits = 1): string {
  if (v == null) return "N/A";
  const n = Number(v);
  return isNaN(n) ? "N/A" : `${n.toFixed(digits)}%`;
}

function na(v: unknown): string {
  return v != null && v !== "" ? String(v) : "N/A";
}

/**
 * Generate a PropVision feasibility PDF for a deal + its buyer matches.
 * Returns a Buffer containing the PDF bytes.
 */
export async function generateFeasibilityPDF(
  deal: Deal,
  matches: (BuyBoxResult & { buyerEmail?: string | null; buyerPhone?: string | null })[],
  comps?: Array<{ address: string; price: number; sqft?: number; distance?: string }>
): Promise<Buffer> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = [];
    const doc = new PDFDocument({ size: "LETTER", margin: 50, bufferPages: true });

    doc.on("data",  (c) => chunks.push(c));
    doc.on("end",   () => resolve(Buffer.concat(chunks)));
    doc.on("error", reject);

    const W = doc.page.width - 100; // usable width

    // ─── Header bar ──────────────────────────────────────────────────────────
    doc.rect(0, 0, doc.page.width, 72).fill(BRAND_BLUE);
    doc.rect(0, 65, doc.page.width, 7).fill(BRAND_PURPLE);

    doc.fillColor("#fff").font("Helvetica-Bold").fontSize(20)
      .text("PROPVISION", 50, 18);
    doc.font("Helvetica").fontSize(10).fillColor("#93c5fd")
      .text("Feasibility Report  ×  Amara OS", 50, 43);

    const genDate = new Date().toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" });
    doc.fillColor("#93c5fd").fontSize(9).text(`Generated ${genDate}`, 0, 30, { align: "right" });

    doc.y = 90;

    // ─── Property address ─────────────────────────────────────────────────────
    const addr = [deal.address, deal.city, deal.state, deal.zip].filter(Boolean).join(", ");
    doc.fillColor(DARK).font("Helvetica-Bold").fontSize(16).text(addr || "Property Address N/A", 50, doc.y);
    doc.font("Helvetica").fontSize(10).fillColor(GRAY)
      .text(`${na(deal.propertyType)}  ·  ${na(deal.beds)} bd / ${na(deal.baths)} ba  ·  ${na(deal.sqft)} sqft  ·  Built ${na(deal.yearBuilt)}`, 50, doc.y + 4);

    doc.y += 30;
    hRule(doc, W);

    // ─── Deal Summary grid ────────────────────────────────────────────────────
    sectionTitle(doc, "DEAL SUMMARY", W);

    const summaryItems = [
      ["Asking Price",         money(deal.askingPrice)],
      ["After Repair Value",   money(deal.arv)],
      ["Estimated Rehab",      money(deal.estimatedRehab)],
      ["Max Allowable Offer",  money(deal.maxAllowableOffer)],
      ["Equity %",             pct(deal.equityPct)],
      ["ROI",                  pct(deal.roiPct)],
    ];

    drawGrid(doc, summaryItems, W);

    // ─── ROI Analysis ──────────────────────────────────────────────────────────
    sectionTitle(doc, "ROI ANALYSIS", W);

    const arv    = Number(deal.arv)             || 0;
    const price  = Number(deal.askingPrice)     || 0;
    const rehab  = Number(deal.estimatedRehab)  || 0;
    const profit = arv - price - rehab;
    const roi    = arv > 0 ? (profit / arv) * 100 : 0;

    const roiItems = [
      ["ARV",            money(arv)],
      ["− Asking Price", `(${money(price)})`],
      ["− Est. Rehab",   `(${money(rehab)})`],
      ["= Net Profit",   money(profit)],
      ["ROI %",          `${roi.toFixed(1)}%`],
      ["70% Rule MAO",   money(arv * 0.7 - rehab)],
    ];
    drawGrid(doc, roiItems, W, profit > 0 ? GREEN : RED);

    // Interpretation blurb
    const roiColor = roi >= 20 ? GREEN : roi >= 10 ? AMBER : RED;
    const roiNote  = roi >= 20
      ? "Strong deal — ROI exceeds 20% threshold."
      : roi >= 10
      ? "Moderate deal — ROI between 10-20%."
      : "Thin margins — negotiate price down or reduce rehab scope.";

    doc.moveDown(0.3);
    doc.font("Helvetica-Bold").fillColor(roiColor).fontSize(10).text(`► ${roiNote}`, 50);

    // ─── Comps ────────────────────────────────────────────────────────────────
    const compList = comps ?? (Array.isArray(deal.comps) ? deal.comps as any[] : []);
    if (compList.length) {
      ensureSpace(doc, 120);
      sectionTitle(doc, "COMPARABLE SALES", W);

      const compHeaders = ["Address", "Sale Price", "Sqft", "$/sqft", "Distance"];
      tableHeader(doc, compHeaders, [200, 80, 60, 60, 80], W);

      compList.slice(0, 6).forEach((c, i) => {
        const pricePerSqft = c.sqft && c.price ? Math.round(c.price / c.sqft) : null;
        const bg = i % 2 === 0 ? LIGHT_GRAY : "#fff";
        tableRow(doc, [
          c.address ?? "N/A",
          money(c.price),
          c.sqft ? c.sqft.toLocaleString() : "N/A",
          pricePerSqft ? `$${pricePerSqft}` : "N/A",
          c.distance ?? "N/A",
        ], [200, 80, 60, 60, 80], W, bg);
      });
    }

    // ─── Buyer matches ────────────────────────────────────────────────────────
    if (matches.length) {
      ensureSpace(doc, 140);
      sectionTitle(doc, "BUYER MATCHES", W);

      const mHeaders = ["Buyer", "Contact", "Match Score", "Label"];
      tableHeader(doc, mHeaders, [120, 140, 80, 210], W);

      matches.slice(0, 10).forEach((m, i) => {
        const scoreColor = m.matchScore >= 80 ? GREEN : m.matchScore >= 60 ? AMBER : RED;
        const bg = i % 2 === 0 ? LIGHT_GRAY : "#fff";
        tableRow(doc, [
          m.buyerName,
          [m.buyerEmail, m.buyerPhone].filter(Boolean).join("\n") || "N/A",
          `${m.matchScore}%`,
          m.label,
        ], [120, 140, 80, 210], W, bg, scoreColor, 2 /* score column index */);
      });

      doc.moveDown(0.5);
      doc.font("Helvetica").fontSize(8).fillColor(GRAY)
        .text(`${matches.length} buyer${matches.length !== 1 ? "s" : ""} matched. Showing top ${Math.min(10, matches.length)}.`, 50);
    }

    // ─── Notes ────────────────────────────────────────────────────────────────
    if (deal.notes) {
      ensureSpace(doc, 80);
      sectionTitle(doc, "NOTES", W);
      doc.font("Helvetica").fontSize(10).fillColor(DARK).text(deal.notes, 50, doc.y, { width: W });
    }

    // ─── Footer on every page ─────────────────────────────────────────────────
    const range = doc.bufferedPageRange();
    for (let i = range.start; i < range.start + range.count; i++) {
      doc.switchToPage(i);
      const pageH = doc.page.height;
      doc.rect(0, pageH - 36, doc.page.width, 36).fill(DARK);
      doc.fillColor("#4b5563").font("Helvetica").fontSize(8)
        .text(`PROPVISION × AMARA OS  —  Confidential feasibility analysis  —  Page ${i + 1} of ${range.count}`,
          50, pageH - 23);
    }

    doc.end();
  });
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function hRule(doc: PDFKit.PDFDocument, w: number) {
  doc.moveTo(50, doc.y).lineTo(50 + w, doc.y).strokeColor("#e5e7eb").lineWidth(1).stroke();
  doc.y += 12;
}

function sectionTitle(doc: PDFKit.PDFDocument, title: string, w: number) {
  doc.y += 4;
  doc.rect(50, doc.y, w, 20).fill(BRAND_BLUE);
  doc.fillColor("#fff").font("Helvetica-Bold").fontSize(9)
    .text(title, 56, doc.y + 5, { width: w - 12 });
  doc.y += 28;
}

function drawGrid(
  doc: PDFKit.PDFDocument,
  items: [string, string][],
  w: number,
  valueColor = DARK
) {
  const colW = w / 2;
  let x = 50;
  let y = doc.y;
  let col = 0;

  items.forEach(([label, value], i) => {
    const bg = Math.floor(i / 2) % 2 === 0 ? LIGHT_GRAY : "#fff";
    doc.rect(x, y, colW - 4, 22).fill(bg);
    doc.fillColor(GRAY).font("Helvetica").fontSize(8).text(label, x + 6, y + 4, { width: colW - 16 });
    doc.fillColor(valueColor).font("Helvetica-Bold").fontSize(10).text(value, x + 6, y + 12, { width: colW - 16 });

    col++;
    if (col === 2) { col = 0; y += 22; x = 50; }
    else { x += colW; }
  });

  if (col === 1) y += 22;
  doc.y = y + 8;
}

function tableHeader(doc: PDFKit.PDFDocument, headers: string[], widths: number[], _w: number) {
  let x = 50;
  const y = doc.y;
  headers.forEach((h, i) => {
    doc.rect(x, y, widths[i] - 2, 18).fill(BRAND_BLUE);
    doc.fillColor("#fff").font("Helvetica-Bold").fontSize(8)
      .text(h, x + 4, y + 4, { width: widths[i] - 8 });
    x += widths[i];
  });
  doc.y = y + 20;
}

function tableRow(
  doc: PDFKit.PDFDocument,
  cells: string[],
  widths: number[],
  _w: number,
  bg: string,
  highlightColor?: string,
  highlightCol?: number
) {
  let x = 50;
  const y = doc.y;
  const rowH = 18;

  cells.forEach((cell, i) => {
    doc.rect(x, y, widths[i] - 2, rowH).fill(i === highlightCol && highlightColor ? "#fff" : bg);
    const color = i === highlightCol && highlightColor ? highlightColor : DARK;
    doc.fillColor(color)
      .font(i === highlightCol ? "Helvetica-Bold" : "Helvetica")
      .fontSize(8)
      .text(cell, x + 4, y + 4, { width: widths[i] - 8, lineBreak: false, ellipsis: true });
    x += widths[i];
  });
  doc.y = y + rowH + 1;
}

function ensureSpace(doc: PDFKit.PDFDocument, needed: number) {
  if (doc.y + needed > doc.page.height - 60) {
    doc.addPage();
    doc.y = 50;
  }
}

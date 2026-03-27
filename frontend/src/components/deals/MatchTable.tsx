import { useState, useEffect } from "react";
import type { Deal, DealMatchRow } from "../../types/deals";
import { api } from "../../api/client";
import styles from "./MatchTable.module.css";

interface Props {
  deals: Deal[];
  onSelectDeal: (d: Deal) => void;
  selectedDealId: number | null;
}

const SCORE_COLOR = (s: number) =>
  s >= 80 ? "#22c55e" : s >= 60 ? "#eab308" : "#ef4444";

export function MatchTable({ deals, onSelectDeal, selectedDealId }: Props) {
  const [matches, setMatches] = useState<Record<number, DealMatchRow[]>>({});
  const [loading, setLoading] = useState<Record<number, boolean>>({});
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  async function loadMatches(dealId: number) {
    if (matches[dealId]) return;
    setLoading((p) => ({ ...p, [dealId]: true }));
    try {
      const res = await api.getDealMatches(dealId);
      setMatches((p) => ({ ...p, [dealId]: res.data }));
    } catch {
      setMatches((p) => ({ ...p, [dealId]: [] }));
    } finally {
      setLoading((p) => ({ ...p, [dealId]: false }));
    }
  }

  function toggle(d: Deal) {
    onSelectDeal(d);
    const next = new Set(expanded);
    if (next.has(d.id)) { next.delete(d.id); }
    else {
      next.add(d.id);
      loadMatches(d.id);
    }
    setExpanded(next);
  }

  if (!deals.length) {
    return (
      <div className={styles.empty}>
        No deals yet. Import a CSV to get started.
      </div>
    );
  }

  return (
    <div className={styles.root}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>Address</th>
            <th>Type</th>
            <th>Bd/Ba</th>
            <th>Asking</th>
            <th>ARV</th>
            <th>Rehab</th>
            <th>ROI</th>
            <th>Equity</th>
            <th>Matches</th>
            <th>PDF</th>
          </tr>
        </thead>
        <tbody>
          {deals.map((d) => (
            <>
              <tr
                key={d.id}
                className={`${styles.row} ${selectedDealId === d.id ? styles.selected : ""}`}
                onClick={() => toggle(d)}
              >
                <td className={styles.addr}>
                  <span className={styles.chevron}>{expanded.has(d.id) ? "▾" : "▸"}</span>
                  {[d.address, d.city, d.state].filter(Boolean).join(", ") || "—"}
                </td>
                <td><span className={styles.typeBadge}>{d.propertyType ?? "—"}</span></td>
                <td>{d.beds ?? "?"}/{d.baths ? Number(d.baths) : "?"}</td>
                <td className={styles.money}>{d.askingPrice ? `$${Math.round(Number(d.askingPrice)/1000)}K` : "—"}</td>
                <td className={styles.money}>{d.arv        ? `$${Math.round(Number(d.arv)/1000)}K`        : "—"}</td>
                <td className={styles.money}>{d.estimatedRehab ? `$${Math.round(Number(d.estimatedRehab)/1000)}K` : "—"}</td>
                <td>
                  {d.roiPct ? (
                    <span style={{ color: SCORE_COLOR(Number(d.roiPct)) }}>
                      {Number(d.roiPct).toFixed(1)}%
                    </span>
                  ) : "—"}
                </td>
                <td>
                  {d.equityPct ? (
                    <span style={{ color: SCORE_COLOR(Number(d.equityPct)) }}>
                      {Number(d.equityPct).toFixed(1)}%
                    </span>
                  ) : "—"}
                </td>
                <td>
                  {loading[d.id]
                    ? <span className={styles.spin}>⟳</span>
                    : matches[d.id]
                    ? <span className={styles.matchCount}>{matches[d.id].length}</span>
                    : <span className={styles.matchDot} />
                  }
                </td>
                <td onClick={(e) => e.stopPropagation()}>
                  <PDFButton dealId={d.id} />
                </td>
              </tr>

              {/* Expanded match rows */}
              {expanded.has(d.id) && matches[d.id]?.map((m) => (
                <tr key={`m-${m.matchId}`} className={styles.matchRow}>
                  <td colSpan={9} className={styles.matchCell}>
                    <MatchLabel match={m} />
                  </td>
                  <td />
                </tr>
              ))}
              {expanded.has(d.id) && matches[d.id]?.length === 0 && (
                <tr className={styles.matchRow}>
                  <td colSpan={10} className={styles.noMatch}>No buyer matches ≥ 30%</td>
                </tr>
              )}
            </>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function MatchLabel({ match }: { match: DealMatchRow }) {
  const color = SCORE_COLOR(match.matchScore);
  return (
    <div className={styles.matchLabel}>
      <div className={styles.matchScoreBar}>
        <div
          className={styles.matchScoreFill}
          style={{ width: `${match.matchScore}%`, background: color }}
        />
      </div>
      <span className={styles.matchScoreNum} style={{ color }}>{match.matchScore}%</span>
      <span className={styles.matchLabelText}>{match.label}</span>
      <div className={styles.matchReasons}>
        {(match.matchReasons ?? [])
          .filter((r) => r.earned > 0)
          .slice(0, 3)
          .map((r) => (
            <span key={r.field} className={styles.reasonChip}>{r.note}</span>
          ))}
      </div>
    </div>
  );
}

function PDFButton({ dealId }: { dealId: number }) {
  const [loading, setLoading] = useState(false);

  async function download() {
    setLoading(true);
    try {
      await api.downloadPDF(dealId);
    } finally {
      setLoading(false);
    }
  }

  return (
    <button className={styles.pdfBtn} onClick={download} disabled={loading} title="Download feasibility PDF">
      {loading ? "⟳" : "📥 PDF"}
    </button>
  );
}

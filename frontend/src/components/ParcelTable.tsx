import type { ParcelListItem, PaginatedParcels, ParcelFilters } from "../types/parcel";
import styles from "./ParcelTable.module.css";

interface Props {
  data: PaginatedParcels | null;
  loading: boolean;
  error: string | null;
  selectedId: number | null;
  onSelect: (p: ParcelListItem) => void;
  filters: ParcelFilters;
  onFiltersChange: (f: ParcelFilters) => void;
}

const REC_CLASS: Record<string, string> = {
  GO:    styles.recGo,
  MAYBE: styles.recMaybe,
  PASS:  styles.recPass,
};

function Flag({ active, label }: { active: boolean | null; label: string }) {
  if (!active) return null;
  return <span className={styles.flag}>{label}</span>;
}

export function ParcelTable({
  data, loading, error, selectedId, onSelect, filters, onFiltersChange,
}: Props) {
  const rows = data?.data ?? [];
  const pg = data?.pagination;

  return (
    <div className={styles.wrapper}>
      {error && <div className={styles.error}>{error}</div>}

      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>APN</th>
              <th>City</th>
              <th>State</th>
              <th>Acres</th>
              <th>Zoning</th>
              <th>Est. Lots</th>
              <th>Score</th>
              <th>Rec.</th>
              <th>Flags</th>
              <th>Pipeline</th>
            </tr>
          </thead>
          <tbody>
            {loading && rows.length === 0 && (
              <tr>
                <td colSpan={10} className={styles.center}>Loading…</td>
              </tr>
            )}
            {!loading && rows.length === 0 && (
              <tr>
                <td colSpan={10} className={styles.center}>No parcels found</td>
              </tr>
            )}
            {rows.map((p) => (
              <tr
                key={p.id}
                className={`${styles.row} ${selectedId === p.id ? styles.rowSelected : ""}`}
                onClick={() => onSelect(p)}
              >
                <td className={styles.mono}>{p.apn ?? "—"}</td>
                <td>{p.city ?? "—"}</td>
                <td>{p.state ?? "—"}</td>
                <td>{p.areaAcres != null ? p.areaAcres.toFixed(2) : "—"}</td>
                <td className={styles.mono}>{p.zoningCode ?? "—"}</td>
                <td>{p.estMaxLotCount ?? "—"}</td>
                <td>
                  <ScoreBar score={p.feasibilityScore} />
                </td>
                <td>
                  {p.recommendation ? (
                    <span className={`${styles.rec} ${REC_CLASS[p.recommendation] ?? ""}`}>
                      {p.recommendation}
                    </span>
                  ) : "—"}
                </td>
                <td className={styles.flags}>
                  <Flag active={p.isTaxDelinquent} label="TAX" />
                  <Flag active={p.hasCodeViolations} label="CODE" />
                  <Flag active={p.hasPreforeclosureFlag} label="PRE" />
                  <Flag active={p.isVacantLand} label="VAC" />
                </td>
                <td className={styles.pipeline}>{p.pipelineStatus ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {pg && (
        <div className={styles.pagination}>
          <span className={styles.pgInfo}>
            {pg.total} parcels · page {pg.page} of {pg.totalPages}
          </span>
          <div className={styles.pgBtns}>
            <button
              disabled={pg.page <= 1}
              onClick={() => onFiltersChange({ ...filters, page: pg.page - 1 })}
            >
              ← Prev
            </button>
            <button
              disabled={pg.page >= pg.totalPages}
              onClick={() => onFiltersChange({ ...filters, page: pg.page + 1 })}
            >
              Next →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function ScoreBar({ score }: { score: number | null }) {
  if (score == null) return <span className={styles.noScore}>—</span>;
  const pct = `${score}%`;
  const color = score >= 75 ? "#22c55e" : score >= 55 ? "#eab308" : "#ef4444";
  return (
    <div className={styles.scoreBar} title={`Score: ${score}`}>
      <div className={styles.scoreTrack}>
        <div className={styles.scoreFill} style={{ width: pct, background: color }} />
      </div>
      <span className={styles.scoreNum}>{score}</span>
    </div>
  );
}

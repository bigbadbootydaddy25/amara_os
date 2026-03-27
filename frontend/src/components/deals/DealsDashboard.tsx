import { useState, useEffect } from "react";
import type { Deal, DealStats } from "../../types/deals";
import { api } from "../../api/client";
import { CSVUpload } from "./CSVUpload";
import { MatchTable } from "./MatchTable";
import { BuyersPanel } from "./BuyersPanel";
import styles from "./DealsDashboard.module.css";

type Tab = "deals" | "buyers";

export function DealsDashboard() {
  const [tab, setTab] = useState<Tab>("deals");
  const [deals, setDeals] = useState<Deal[]>([]);
  const [stats, setStats] = useState<DealStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedDealId, setSelectedDealId] = useState<number | null>(null);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);

  useEffect(() => {
    loadDeals();
    loadStats();
  }, [page]);

  async function loadDeals() {
    setLoading(true);
    try {
      const res = await api.listDeals({ page, limit: 50 });
      setDeals(res.data);
      setTotal(res.pagination.total);
    } catch {
    } finally {
      setLoading(false);
    }
  }

  async function loadStats() {
    try {
      const res = await api.getDealStats();
      setStats(res.data);
    } catch {}
  }

  function handleImported() {
    setPage(1);
    loadDeals();
    loadStats();
  }

  return (
    <div className={styles.root}>
      {/* Stats bar */}
      {stats && (
        <div className={styles.statsBar}>
          <StatPill label="Deals" value={stats.totalDeals} color="#4f7ef8" />
          <StatPill label="Active Buyers" value={stats.totalBuyers} color="#a78bfa" />
          <StatPill label="Matches" value={stats.totalMatches} color="#22c55e" />
          <StatPill label="Avg Score" value={`${stats.avgScore ?? 0}%`} color="#eab308" />
          <StatPill label="Hot (≥80%)" value={stats.topMatches} color="#f97316" />
        </div>
      )}

      <div className={styles.body}>
        {/* Left: upload + tab area */}
        <div className={styles.left}>
          <div className={styles.tabs}>
            <button className={`${styles.tab} ${tab === "deals" ? styles.tabActive : ""}`} onClick={() => setTab("deals")}>
              Deals {total > 0 && <span className={styles.count}>{total}</span>}
            </button>
            <button className={`${styles.tab} ${tab === "buyers" ? styles.tabActive : ""}`} onClick={() => setTab("buyers")}>
              Buyers
            </button>
          </div>

          {tab === "deals" && (
            <div className={styles.dealsPane}>
              <CSVUpload onImported={handleImported} />
              <div className={styles.tableWrap}>
                {loading ? (
                  <div className={styles.loading}>Loading deals…</div>
                ) : (
                  <MatchTable
                    deals={deals}
                    onSelectDeal={(d) => setSelectedDealId(d.id)}
                    selectedDealId={selectedDealId}
                  />
                )}
              </div>
              {total > 50 && (
                <div className={styles.pagination}>
                  <button disabled={page <= 1} onClick={() => setPage(page - 1)}>← Prev</button>
                  <span>{page} / {Math.ceil(total / 50)}</span>
                  <button disabled={page >= Math.ceil(total / 50)} onClick={() => setPage(page + 1)}>Next →</button>
                </div>
              )}
            </div>
          )}

          {tab === "buyers" && <BuyersPanel />}
        </div>
      </div>
    </div>
  );
}

function StatPill({ label, value, color }: { label: string; value: number | string; color: string }) {
  return (
    <div className={styles.statPill}>
      <span className={styles.statValue} style={{ color }}>{value}</span>
      <span className={styles.statLabel}>{label}</span>
    </div>
  );
}

import { useState, useEffect } from "react";
import type { PipelineStats, PipelineRun } from "../../types/review";
import { api } from "../../api/client";
import styles from "./PipelineDashboard.module.css";

export function PipelineDashboard() {
  const [stats, setStats] = useState<PipelineStats | null>(null);
  const [runs, setRuns] = useState<PipelineRun[]>([]);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    load();
  }, []);

  async function load() {
    try {
      const [s, r] = await Promise.all([api.getPipelineStats(), api.listPipelineRuns()]);
      setStats(s.data);
      setRuns(r.data);
    } catch (e: any) {
      setError(e.message);
    }
  }

  async function handleRun() {
    setRunning(true);
    setError(null);
    try {
      await api.runPipeline();
      await load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className={styles.root}>
      <div className={styles.header}>
        <div>
          <div className={styles.title}>Amara Pipeline</div>
          <div className={styles.subtitle}>Autonomous deal discovery · runs daily at 6 AM</div>
        </div>
        <button className={styles.runBtn} onClick={handleRun} disabled={running}>
          {running ? "Running…" : "▶ Run Now"}
        </button>
      </div>

      {error && <div className={styles.error}>{error}</div>}

      {stats && (
        <div className={styles.statGrid}>
          <StatCard label="Total Reviewed" value={stats.total} color="#4f7ef8" />
          <StatCard label="Approved" value={stats.approved} color="#22c55e" />
          <StatCard label="Rejected" value={stats.rejected} color="#ef4444" />
          <StatCard label="Needs Info" value={stats.needsInfo} color="#eab308" />
          <StatCard label="LOI Sent" value={stats.loi_sent} color="#a78bfa" />
          <StatCard label="In Negotiation" value={stats.in_negotiation} color="#f472b6" />
          <StatCard label="Under Contract" value={stats.under_contract} color="#34d399" />
          <StatCard label="Closed" value={stats.closed} color="#fbbf24" />
        </div>
      )}

      <div className={styles.runsSection}>
        <div className={styles.runsTitle}>Recent Pipeline Runs</div>
        {runs.length === 0 && (
          <div className={styles.noRuns}>No runs yet. Click "Run Now" to start.</div>
        )}
        {runs.map((r) => (
          <div key={r.runId} className={styles.runRow}>
            <div className={styles.runLeft}>
              <span className={`${styles.runStatus} ${styles[`status${r.status}`]}`}>
                {r.status}
              </span>
              <span className={styles.runId}>{r.runId}</span>
              <span className={styles.runTrigger}>{r.triggeredBy}</span>
            </div>
            <div className={styles.runRight}>
              <span title="Found">🔍 {r.parcelsFound}</span>
              <span title="Approved">✓ {r.amaraApproved}</span>
              <span title="Rejected">✗ {r.amaraRejected}</span>
              <span className={styles.runDate}>
                {r.startedAt ? new Date(r.startedAt).toLocaleString() : "—"}
              </span>
            </div>
            {r.errorMessage && (
              <div className={styles.runError}>{r.errorMessage}</div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className={styles.statCard}>
      <div className={styles.statValue} style={{ color }}>{value}</div>
      <div className={styles.statLabel}>{label}</div>
    </div>
  );
}

import { useState, useEffect } from "react";
import type { DealReview, LifecycleStatus } from "../../types/review";
import { api } from "../../api/client";
import { DocumentViewer } from "./DocumentViewer";
import { LOIModal } from "./LOIModal";
import styles from "./AmaraReviewPanel.module.css";

interface Props {
  parcelId: number;
}

const LIFECYCLE_STEPS: LifecycleStatus[] = [
  "UNDER_REVIEW",
  "APPROVED",
  "LOI_SENT",
  "IN_NEGOTIATION",
  "UNDER_CONTRACT",
  "CLOSED",
];

const DECISION_META: Record<string, { label: string; class: string; icon: string }> = {
  APPROVED:       { label: "Approved",        class: "approved",    icon: "✓" },
  REJECTED:       { label: "Rejected",        class: "rejected",    icon: "✗" },
  NEEDS_MORE_INFO:{ label: "Needs More Info", class: "needsInfo",   icon: "?" },
  PENDING:        { label: "Pending Review",  class: "pending",     icon: "⟳" },
};

export function AmaraReviewPanel({ parcelId }: Props) {
  const [review, setReview] = useState<DealReview | null>(null);
  const [loading, setLoading] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const [activeDoc, setActiveDoc] = useState<{ title: string; text: string } | null>(null);
  const [showLOIModal, setShowLOIModal] = useState(false);
  const [generatingDoc, setGeneratingDoc] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setReview(null);
    setError(null);
    setActiveDoc(null);
    loadReview();
  }, [parcelId]);

  async function loadReview() {
    setLoading(true);
    try {
      const res = await api.getAmaraReview(parcelId);
      setReview(res.data);
    } catch {
      // No review yet — that's fine
    } finally {
      setLoading(false);
    }
  }

  async function handleReview() {
    setReviewing(true);
    setError(null);
    try {
      const res = await api.amaraReview(parcelId);
      setReview(res.data);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setReviewing(false);
    }
  }

  async function handleGenerateLOI(offerPrice: number, buyerEntity: string) {
    setGeneratingDoc("loi");
    setError(null);
    try {
      const res = await api.generateLOI(parcelId, offerPrice, buyerEntity);
      setReview(res.data.review);
      setActiveDoc({ title: "Letter of Intent", text: res.data.loiText });
    } catch (e: any) {
      setError(e.message);
    } finally {
      setGeneratingDoc(null);
      setShowLOIModal(false);
    }
  }

  async function handleGenerateOutreach() {
    setGeneratingDoc("outreach");
    setError(null);
    try {
      const res = await api.generateOutreach(parcelId);
      setReview(res.data.review);
      setActiveDoc({ title: "Owner Outreach Letter", text: res.data.ownerOutreachText });
    } catch (e: any) {
      setError(e.message);
    } finally {
      setGeneratingDoc(null);
    }
  }

  async function handleGenerateNegotiation() {
    setGeneratingDoc("negotiation");
    setError(null);
    try {
      const res = await api.generateNegotiation(parcelId);
      setReview(res.data.review);
      setActiveDoc({ title: "Negotiation Strategy", text: res.data.negotiationStrategy });
    } catch (e: any) {
      setError(e.message);
    } finally {
      setGeneratingDoc(null);
    }
  }

  async function handleLifecycle(status: LifecycleStatus) {
    setError(null);
    try {
      const res = await api.advanceLifecycle(parcelId, status);
      setReview(res.data);
    } catch (e: any) {
      setError(e.message);
    }
  }

  async function handleOverride(decision: "APPROVED" | "REJECTED") {
    setError(null);
    const note = window.prompt(`Note for ${decision} override (optional):`);
    try {
      const res = await api.overrideDecision(parcelId, decision, note ?? undefined, "Human");
      setReview(res.data);
    } catch (e: any) {
      setError(e.message);
    }
  }

  const decisionMeta = review ? DECISION_META[review.amaraDecision] : null;

  return (
    <div className={styles.root}>
      {/* Amara Header */}
      <div className={styles.header}>
        <div className={styles.amaraIdent}>
          <div className={styles.amaraOrb} />
          <div>
            <div className={styles.amaraName}>Amara OS</div>
            <div className={styles.amaraRole}>Autonomous Deal Agent</div>
          </div>
        </div>
        {review && (
          <div className={`${styles.decisionBadge} ${styles[decisionMeta?.class ?? ""]}`}>
            <span className={styles.decisionIcon}>{decisionMeta?.icon}</span>
            {decisionMeta?.label}
          </div>
        )}
      </div>

      {error && <div className={styles.error}>{error}</div>}

      {/* No review yet */}
      {!review && !loading && (
        <div className={styles.noReview}>
          <p>Amara hasn't reviewed this parcel yet.</p>
          <button className={styles.primaryBtn} onClick={handleReview} disabled={reviewing}>
            {reviewing ? "Amara is thinking…" : "→ Send to Amara for Review"}
          </button>
        </div>
      )}

      {loading && <div className={styles.loading}>Loading Amara's review…</div>}

      {review && (
        <>
          {/* Confidence + lifecycle */}
          <div className={styles.meta}>
            <div className={styles.metaItem}>
              <span className={styles.metaLabel}>Confidence</span>
              <ConfidenceBar score={Number(review.confidenceScore)} />
            </div>
            <div className={styles.metaItem}>
              <span className={styles.metaLabel}>Stage</span>
              <span className={styles.lifecycle}>{review.lifecycleStatus ?? "—"}</span>
            </div>
            {review.humanOverride && (
              <div className={styles.overrideBanner}>
                Human override: <strong>{review.humanOverride}</strong>
                {review.humanOverrideNote && ` — ${review.humanOverrideNote}`}
              </div>
            )}
          </div>

          {/* Lifecycle stepper */}
          <LifecycleStepper current={review.lifecycleStatus} onAdvance={handleLifecycle} />

          {/* Amara's reasoning */}
          {review.amaraReasoning && (
            <div className={styles.reasoning}>
              <div className={styles.reasoningLabel}>Amara's Reasoning</div>
              <div className={styles.reasoningText}>{review.amaraReasoning}</div>
            </div>
          )}

          {/* Action buttons */}
          <div className={styles.actions}>
            <div className={styles.actionsLabel}>Generate Documents</div>
            <div className={styles.actionGrid}>
              <button
                className={styles.actionBtn}
                onClick={() => review.loiText
                  ? setActiveDoc({ title: "Letter of Intent", text: review.loiText })
                  : setShowLOIModal(true)
                }
                disabled={generatingDoc === "loi"}
              >
                {generatingDoc === "loi" ? "Generating…" :
                 review.loiText ? "📄 View LOI" : "📄 Generate LOI"}
              </button>

              <button
                className={styles.actionBtn}
                onClick={() => review.ownerOutreachText
                  ? setActiveDoc({ title: "Owner Outreach Letter", text: review.ownerOutreachText })
                  : handleGenerateOutreach()
                }
                disabled={generatingDoc === "outreach"}
              >
                {generatingDoc === "outreach" ? "Generating…" :
                 review.ownerOutreachText ? "✉ View Outreach" : "✉ Write Outreach"}
              </button>

              <button
                className={styles.actionBtn}
                onClick={() => review.negotiationStrategy
                  ? setActiveDoc({ title: "Negotiation Strategy", text: review.negotiationStrategy })
                  : handleGenerateNegotiation()
                }
                disabled={generatingDoc === "negotiation"}
              >
                {generatingDoc === "negotiation" ? "Generating…" :
                 review.negotiationStrategy ? "⚔ View Strategy" : "⚔ Build Strategy"}
              </button>
            </div>
          </div>

          {/* Human override controls */}
          <div className={styles.overrideSection}>
            <div className={styles.actionsLabel}>Human Override</div>
            <div className={styles.overrideBtns}>
              <button
                className={`${styles.overrideBtn} ${styles.approveBtn}`}
                onClick={() => handleOverride("APPROVED")}
              >
                ✓ Override → Approve
              </button>
              <button
                className={`${styles.overrideBtn} ${styles.rejectBtn}`}
                onClick={() => handleOverride("REJECTED")}
              >
                ✗ Override → Reject
              </button>
              <button
                className={styles.overrideBtn}
                onClick={handleReview}
                disabled={reviewing}
              >
                ⟳ Re-run Amara
              </button>
            </div>
          </div>
        </>
      )}

      {/* Document viewer overlay */}
      {activeDoc && (
        <DocumentViewer
          title={activeDoc.title}
          text={activeDoc.text}
          onClose={() => setActiveDoc(null)}
        />
      )}

      {/* LOI input modal */}
      {showLOIModal && (
        <LOIModal
          onGenerate={handleGenerateLOI}
          onClose={() => setShowLOIModal(false)}
          loading={generatingDoc === "loi"}
        />
      )}
    </div>
  );
}

function ConfidenceBar({ score }: { score: number }) {
  const color = score >= 70 ? "#22c55e" : score >= 45 ? "#eab308" : "#ef4444";
  return (
    <div className={styles.confBar}>
      <div className={styles.confTrack}>
        <div className={styles.confFill} style={{ width: `${score}%`, background: color }} />
      </div>
      <span className={styles.confNum}>{score.toFixed(0)}%</span>
    </div>
  );
}

const LIFECYCLE_ORDER: LifecycleStatus[] = [
  "UNDER_REVIEW", "APPROVED", "LOI_SENT", "IN_NEGOTIATION", "UNDER_CONTRACT", "CLOSED",
];

function LifecycleStepper({
  current,
  onAdvance,
}: {
  current: string | null;
  onAdvance: (s: LifecycleStatus) => void;
}) {
  const currentIdx = LIFECYCLE_ORDER.indexOf(current as LifecycleStatus);

  return (
    <div className={styles.stepper}>
      {LIFECYCLE_ORDER.map((step, i) => {
        const isPast = i < currentIdx;
        const isCurrent = i === currentIdx;
        const isNext = i === currentIdx + 1;
        return (
          <button
            key={step}
            className={`${styles.step} ${isPast ? styles.stepPast : ""} ${isCurrent ? styles.stepCurrent : ""}`}
            onClick={() => isNext && onAdvance(step)}
            disabled={!isNext}
            title={isNext ? `Advance to: ${step}` : step}
          >
            <div className={styles.stepDot} />
            <span className={styles.stepLabel}>{step.replace(/_/g, " ")}</span>
          </button>
        );
      })}
    </div>
  );
}

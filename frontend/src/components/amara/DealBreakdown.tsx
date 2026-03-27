/**
 * AmaraDealBreakdown — Tony Romo-style holographic deal analysis panel.
 *
 * Amara appears as a live avatar, annotates the deal with glowing overlays,
 * and reads the breakdown aloud via the British Jarvis voice stub.
 *
 * Voice: swap `speakLine()` for a real TTS call (ElevenLabs / Web Speech API).
 */
import { useState, useRef, useEffect } from "react";
import type { Parcel } from "../../types/parcel";
import type { DealReview } from "../../types/review";
import styles from "./DealBreakdown.module.css";

interface Props {
  parcel: Parcel;
  review: DealReview | null;
}

interface AnnotationLine {
  id: string;
  label: string;
  value: string;
  delta?: string;        // e.g. "+15 pts"
  sentiment: "pos" | "neg" | "neutral";
  x: number;            // % from left in the holo overlay
  y: number;            // % from top
}

// ── Voice adapter (swap for real TTS) ────────────────────────────────────────
function speakLine(text: string) {
  if (!("speechSynthesis" in window)) return;

  window.speechSynthesis.cancel();
  const utt = new SpeechSynthesisUtterance(text);

  // Try to find a British English voice (Jarvis-style)
  const voices = window.speechSynthesis.getVoices();
  const britishVoice =
    voices.find((v) => v.lang === "en-GB" && v.name.toLowerCase().includes("male")) ??
    voices.find((v) => v.lang === "en-GB") ??
    voices.find((v) => v.lang.startsWith("en"));

  if (britishVoice) utt.voice = britishVoice;
  utt.rate = 0.92;
  utt.pitch = 0.88;

  // TODO: replace with ElevenLabs / Cartesia for a true Jarvis voice:
  // const res = await fetch("https://api.elevenlabs.io/v1/text-to-speech/<voice-id>", {
  //   method: "POST",
  //   headers: { "xi-api-key": ELEVENLABS_KEY, "Content-Type": "application/json" },
  //   body: JSON.stringify({ text, model_id: "eleven_turbo_v2" }),
  // });
  // const audio = new Audio(URL.createObjectURL(await res.blob()));
  // audio.play();

  window.speechSynthesis.speak(utt);
}

function buildAnnotations(parcel: Parcel, review: DealReview | null): AnnotationLine[] {
  const lines: AnnotationLine[] = [];

  const score = parcel.feasibilityScore ?? 0;
  const rec = parcel.recommendation ?? "PASS";

  lines.push({
    id: "score",
    label: "Feasibility Score",
    value: `${score} / 100`,
    delta: score >= 75 ? "+GO" : score >= 55 ? "MAYBE" : "PASS",
    sentiment: score >= 75 ? "pos" : score >= 55 ? "neutral" : "neg",
    x: 60, y: 18,
  });

  if (parcel.areaAcres) {
    lines.push({
      id: "acres",
      label: "Site Area",
      value: `${parcel.areaAcres.toFixed(2)} ac`,
      sentiment: "neutral",
      x: 15, y: 30,
    });
  }

  if (parcel.estMaxLotCount) {
    lines.push({
      id: "lots",
      label: "Est. Max Lots",
      value: `${parcel.estMaxLotCount} lots`,
      delta: parcel.estMaxLotCount >= 5 ? "+10 pts" : "",
      sentiment: parcel.estMaxLotCount >= 5 ? "pos" : "neutral",
      x: 70, y: 42,
    });
  }

  if (parcel.isTaxDelinquent) {
    lines.push({
      id: "tax",
      label: "Tax Delinquent",
      value: `$${Number(parcel.taxDelinquentAmount ?? 0).toLocaleString()}`,
      delta: "+8 pts",
      sentiment: "pos",
      x: 20, y: 55,
    });
  }

  if (parcel.hasCodeViolations) {
    lines.push({
      id: "code",
      label: "Code Violations",
      value: `${parcel.codeViolationCount ?? 1} violation${(parcel.codeViolationCount ?? 1) > 1 ? "s" : ""}`,
      delta: "+6 pts",
      sentiment: "pos",
      x: 65, y: 65,
    });
  }

  if (parcel.floodZoneCode && parcel.floodZoneCode !== "X") {
    lines.push({
      id: "flood",
      label: "Flood Zone",
      value: parcel.floodZoneCode,
      delta: "−10 pts",
      sentiment: "neg",
      x: 30, y: 75,
    });
  }

  if (parcel.nearbyNewBuildPricePerUnit && parcel.estimatedLandValuePerPotentialLot) {
    const ratio =
      (Number(parcel.estimatedLandValuePerPotentialLot) /
        Number(parcel.nearbyNewBuildPricePerUnit)) * 100;
    lines.push({
      id: "ratio",
      label: "Land-to-Retail",
      value: `${ratio.toFixed(1)}%`,
      delta: ratio <= 10 ? "+15 pts" : ratio <= 15 ? "+8 pts" : ratio > 25 ? "−10 pts" : "",
      sentiment: ratio <= 10 ? "pos" : ratio > 25 ? "neg" : "neutral",
      x: 55, y: 82,
    });
  }

  if (review) {
    lines.push({
      id: "amara",
      label: "Amara Decision",
      value: review.amaraDecision,
      delta: review.confidenceScore ? `${Number(review.confidenceScore).toFixed(0)}% conf` : "",
      sentiment:
        review.amaraDecision === "APPROVED"
          ? "pos"
          : review.amaraDecision === "REJECTED"
          ? "neg"
          : "neutral",
      x: 40, y: 92,
    });
  }

  return lines;
}

function buildNarration(parcel: Parcel, review: DealReview | null): string {
  const score = parcel.feasibilityScore ?? 0;
  const rec = parcel.recommendation ?? "PASS";
  const address = [parcel.addressLine1, parcel.city, parcel.state].filter(Boolean).join(", ");

  let text = `Right. Let's break this down. ${address}. `;
  text += `PropVision gives it a feasibility score of ${score} out of 100, recommendation: ${rec}. `;

  if (parcel.estMaxLotCount)
    text += `We're looking at ${parcel.estMaxLotCount} potential lots here. `;

  if (parcel.isTaxDelinquent)
    text += `Owner is tax delinquent — that's a distress signal, which I find rather interesting. `;

  if (parcel.hasCodeViolations)
    text += `There are ${parcel.codeViolationCount ?? "multiple"} code violations. Motivation to sell is elevated. `;

  if (parcel.floodZoneCode && parcel.floodZoneCode !== "X")
    text += `Flood zone ${parcel.floodZoneCode} is a concern. Deducting points accordingly. `;

  if (review?.amaraDecision === "APPROVED")
    text += `I've reviewed this independently and I approve it. ${review.confidenceScore ? `Confidence: ${Number(review.confidenceScore).toFixed(0)} percent.` : ""} `;
  else if (review?.amaraDecision === "REJECTED")
    text += `I've reviewed this and I'm rejecting it. The numbers don't work. `;

  text += "That's the picture.";
  return text;
}

export function AmaraDealBreakdown({ parcel, review }: Props) {
  const [active, setActive] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [visibleIds, setVisibleIds] = useState<Set<string>>(new Set());
  const timerRef = useRef<ReturnType<typeof setTimeout>[]>([]);

  const annotations = buildAnnotations(parcel, review);

  function clearTimers() {
    timerRef.current.forEach(clearTimeout);
    timerRef.current = [];
  }

  function handleActivate() {
    clearTimers();
    setActive(true);
    setVisibleIds(new Set());
    setSpeaking(true);

    // Stagger annotation reveals
    annotations.forEach((ann, i) => {
      const t = setTimeout(() => {
        setVisibleIds((prev) => new Set([...prev, ann.id]));
      }, i * 350 + 400);
      timerRef.current.push(t);
    });

    // Speak narration
    speakLine(buildNarration(parcel, review));

    const endT = setTimeout(() => setSpeaking(false), annotations.length * 350 + 2500);
    timerRef.current.push(endT);
  }

  function handleClose() {
    clearTimers();
    setActive(false);
    setVisibleIds(new Set());
    setSpeaking(false);
    window.speechSynthesis?.cancel();
  }

  useEffect(() => () => { clearTimers(); window.speechSynthesis?.cancel(); }, []);

  const rec = parcel.recommendation ?? "PASS";
  const recColor = rec === "GO" ? "#22c55e" : rec === "MAYBE" ? "#eab308" : "#ef4444";

  return (
    <>
      <button className={styles.activateBtn} onClick={handleActivate} title="Tony Romo breakdown">
        <span className={styles.activateBtnOrb} />
        ⬡ Holo Breakdown
      </button>

      {active && (
        <div className={styles.overlay}>
          <div className={styles.holoPanel}>
            {/* Scanline effect */}
            <div className={styles.scanlines} />

            {/* Header */}
            <div className={styles.holoHeader}>
              <div className={styles.holoLogo}>AMARA OS <span>DEAL ANALYSIS</span></div>
              <button className={styles.closeBtn} onClick={handleClose}>✕</button>
            </div>

            {/* Avatar + field */}
            <div className={styles.field}>
              {/* Amara avatar */}
              <div className={styles.avatarZone}>
                <img
                  src="/amara-live-head.jpg"
                  alt="Amara"
                  className={`${styles.avatar} ${speaking ? styles.avatarSpeaking : ""}`}
                  onError={(e) => {
                    // Fallback to the orb if image not found
                    (e.target as HTMLImageElement).style.display = "none";
                  }}
                />
                <div className={`${styles.avatarOrb} ${speaking ? styles.orbSpeaking : ""}`} />
                <div className={styles.avatarName}>
                  AMARA
                  {speaking && <span className={styles.speakingDot}>●</span>}
                </div>
              </div>

              {/* Central parcel card */}
              <div className={styles.parcelCard}>
                <div className={styles.parcelApn}>{parcel.apn ?? "APN N/A"}</div>
                <div className={styles.parcelAddress}>
                  {[parcel.addressLine1, parcel.city, parcel.state].filter(Boolean).join(", ")}
                </div>
                <div className={styles.parcelScore} style={{ color: recColor }}>
                  {parcel.feasibilityScore ?? "—"}
                  <span>/100</span>
                </div>
                <div className={styles.parcelRec} style={{ background: recColor + "22", color: recColor }}>
                  {rec}
                </div>
              </div>

              {/* Holographic annotation overlays */}
              {annotations.map((ann) => (
                <div
                  key={ann.id}
                  className={`${styles.annotation} ${visibleIds.has(ann.id) ? styles.annotationVisible : ""} ${styles[`ann_${ann.sentiment}`]}`}
                  style={{ left: `${ann.x}%`, top: `${ann.y}%` }}
                >
                  <div className={styles.annLabel}>{ann.label}</div>
                  <div className={styles.annValue}>{ann.value}</div>
                  {ann.delta && <div className={styles.annDelta}>{ann.delta}</div>}
                  <div className={styles.annLine} />
                </div>
              ))}

              {/* Corner grid lines */}
              <div className={styles.gridLines} />
            </div>

            {/* Amara reasoning strip */}
            {review?.amaraReasoning && (
              <div className={styles.reasoningStrip}>
                <span className={styles.reasoningLabel}>AMARA ANALYSIS —</span>
                <span className={styles.reasoningText}>{review.amaraReasoning.slice(0, 280)}…</span>
              </div>
            )}

            {/* Replay button */}
            <div className={styles.holoFooter}>
              <button className={styles.replayBtn} onClick={handleActivate}>
                ↺ Replay
              </button>
              <span className={styles.footerTag}>PROPVISION × AMARA OS</span>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

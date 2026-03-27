import { useState } from "react";
import styles from "./LOIModal.module.css";

interface Props {
  onGenerate: (offerPrice: number, buyerEntity: string) => void;
  onClose: () => void;
  loading: boolean;
}

export function LOIModal({ onGenerate, onClose, loading }: Props) {
  const [offerPrice, setOfferPrice] = useState("");
  const [buyerEntity, setBuyerEntity] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const price = Number(offerPrice.replace(/[^0-9.]/g, ""));
    if (!price || !buyerEntity.trim()) return;
    onGenerate(price, buyerEntity.trim());
  }

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <span>Generate Letter of Intent</span>
          <button className={styles.closeBtn} onClick={onClose}>✕</button>
        </div>
        <form className={styles.form} onSubmit={handleSubmit}>
          <label className={styles.label}>
            Offer Price ($)
            <input
              className={styles.input}
              type="text"
              placeholder="e.g. 1250000"
              value={offerPrice}
              onChange={(e) => setOfferPrice(e.target.value)}
              required
            />
          </label>
          <label className={styles.label}>
            Buying Entity (LLC / Corp name)
            <input
              className={styles.input}
              type="text"
              placeholder="e.g. Amara Capital LLC"
              value={buyerEntity}
              onChange={(e) => setBuyerEntity(e.target.value)}
              required
            />
          </label>
          <button className={styles.submitBtn} type="submit" disabled={loading}>
            {loading ? "Amara is drafting…" : "Generate LOI"}
          </button>
        </form>
      </div>
    </div>
  );
}

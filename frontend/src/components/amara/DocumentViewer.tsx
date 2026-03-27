import styles from "./DocumentViewer.module.css";

interface Props {
  title: string;
  text: string;
  onClose: () => void;
}

export function DocumentViewer({ title, text, onClose }: Props) {
  function handleCopy() {
    navigator.clipboard.writeText(text).catch(() => {});
  }

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <span className={styles.title}>{title}</span>
          <div className={styles.headerActions}>
            <button className={styles.copyBtn} onClick={handleCopy} title="Copy to clipboard">
              Copy
            </button>
            <button className={styles.closeBtn} onClick={onClose} title="Close">
              ✕
            </button>
          </div>
        </div>
        <div className={styles.content}>
          <pre className={styles.text}>{text}</pre>
        </div>
      </div>
    </div>
  );
}

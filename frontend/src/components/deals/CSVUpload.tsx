import { useState, useRef } from "react";
import { api } from "../../api/client";
import styles from "./CSVUpload.module.css";

interface ImportResult {
  batchId: string;
  imported: number;
  totalMatches: number;
}

interface Props {
  onImported: (result: ImportResult) => void;
}

const SAMPLE_CSV = `address,city,state,zip,property_type,beds,baths,sqft,year_built,asking_price,arv,estimated_rehab
4820 E Sunset Rd,Henderson,NV,89014,SFR,3,2,1450,1998,240000,340000,45000
7200 W Cheyenne Ave,Las Vegas,NV,89129,SFR,4,2,1800,2003,310000,430000,30000
1840 N Decatur Blvd,Las Vegas,NV,89108,MF,0,0,4200,1975,480000,680000,95000
3310 N Rainbow Blvd,Las Vegas,NV,89108,SFR,3,2,1320,1989,215000,295000,28000
9600 S Eastern Ave,Henderson,NV,89002,SFR,5,3,2600,2012,420000,560000,18000`;

export function CSVUpload({ onImported }: Props) {
  const [csvText, setCsvText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => setCsvText(ev.target?.result as string ?? "");
    reader.readAsText(file);
  }

  async function handleImport() {
    if (!csvText.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await api.importCSV(csvText);
      setResult(res.data);
      onImported(res.data);
      setCsvText("");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={styles.root}>
      <div className={styles.header}>
        <span className={styles.title}>Import CSV</span>
        <button className={styles.sampleBtn} onClick={() => setCsvText(SAMPLE_CSV)}>
          Load Sample
        </button>
      </div>

      <div className={styles.dropZone} onClick={() => fileRef.current?.click()}>
        <input ref={fileRef} type="file" accept=".csv,.txt" onChange={handleFileChange} style={{ display: "none" }} />
        <span className={styles.dropIcon}>📄</span>
        <span className={styles.dropText}>Drop CSV file here or click to browse</span>
        <span className={styles.dropHint}>Columns: address, city, state, zip, beds, baths, asking_price, arv, estimated_rehab…</span>
      </div>

      {csvText && (
        <div className={styles.preview}>
          <div className={styles.previewLabel}>
            Preview ({csvText.split("\n").length - 1} data rows)
          </div>
          <pre className={styles.previewText}>{csvText.slice(0, 600)}{csvText.length > 600 ? "\n…" : ""}</pre>
        </div>
      )}

      {error && <div className={styles.error}>{error}</div>}

      {result && (
        <div className={styles.success}>
          ✓ Imported <strong>{result.imported}</strong> deals ·{" "}
          <strong>{result.totalMatches}</strong> buyer matches found
          <span className={styles.batchId}>{result.batchId}</span>
        </div>
      )}

      <button
        className={styles.importBtn}
        onClick={handleImport}
        disabled={loading || !csvText.trim()}
      >
        {loading ? "Importing + matching…" : "Import & Match Buyers"}
      </button>
    </div>
  );
}

import { useState } from "react";
import type { Parcel } from "../types/parcel";
import { api } from "../api/client";
import { AssistantPanel } from "./AssistantPanel";
import { AmaraReviewPanel } from "./amara/AmaraReviewPanel";
import styles from "./ParcelDetail.module.css";

interface Props {
  parcel: Parcel | null;
  loading: boolean;
  onRecomputed: (updated: Parcel) => void;
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className={styles.field}>
      <span className={styles.fieldLabel}>{label}</span>
      <span className={styles.fieldValue}>{value ?? "—"}</span>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className={styles.section}>
      <div className={styles.sectionTitle}>{title}</div>
      {children}
    </div>
  );
}

function Bool({ v }: { v: boolean | null }) {
  if (v == null) return <>—</>;
  return <span className={v ? styles.yes : styles.no}>{v ? "Yes" : "No"}</span>;
}

export function ParcelDetail({ parcel, loading, onRecomputed }: Props) {
  const [recomputing, setRecomputing] = useState(false);
  const [recomputeError, setRecomputeError] = useState<string | null>(null);

  async function handleRecompute() {
    if (!parcel) return;
    setRecomputing(true);
    setRecomputeError(null);
    try {
      const res = await api.recomputeFeasibility(parcel.id);
      onRecomputed(res.data);
    } catch (e: any) {
      setRecomputeError(e.message);
    } finally {
      setRecomputing(false);
    }
  }

  if (loading) return <div className={styles.empty}>Loading parcel…</div>;
  if (!parcel)  return <div className={styles.empty}>Select a parcel to view details</div>;

  const rec = parcel.recommendation;
  const recClass =
    rec === "GO"    ? styles.recGo :
    rec === "MAYBE" ? styles.recMaybe : styles.recPass;

  return (
    <div className={styles.root}>
      {/* Header */}
      <div className={styles.header}>
        <div>
          <div className={styles.apn}>{parcel.apn ?? "No APN"}</div>
          <div className={styles.address}>
            {[parcel.addressLine1, parcel.city, parcel.state, parcel.zip]
              .filter(Boolean)
              .join(", ")}
          </div>
        </div>
        <div className={styles.scoreBadge}>
          <div className={styles.scoreNum}>{parcel.feasibilityScore ?? "—"}</div>
          <div className={styles.scoreLabel}>/ 100</div>
          {rec && <div className={`${styles.recBadge} ${recClass}`}>{rec}</div>}
        </div>
      </div>

      {recomputeError && <div className={styles.error}>{recomputeError}</div>}
      <button
        className={styles.recomputeBtn}
        onClick={handleRecompute}
        disabled={recomputing}
      >
        {recomputing ? "Recomputing…" : "⟳ Recompute Feasibility"}
      </button>

      <div className={styles.scrollArea}>
        <Section title="Location">
          <Field label="County"     value={parcel.county} />
          <Field label="Jurisdiction" value={parcel.jurisdiction} />
          <Field label="Lat / Lon"  value={parcel.latitude != null ? `${parcel.latitude}, ${parcel.longitude}` : null} />
          <Field label="Area (sqft)" value={parcel.areaSqft?.toLocaleString()} />
          <Field label="Area (acres)" value={parcel.areaAcres?.toFixed(4)} />
        </Section>

        <Section title="Ownership">
          <Field label="Owner"        value={parcel.ownerName} />
          <Field label="Mailing Addr" value={parcel.ownerMailingAddress} />
          <Field label="Last Sale"    value={parcel.lastSaleDate} />
          <Field label="Sale Price"   value={parcel.lastSalePrice ? `$${Number(parcel.lastSalePrice).toLocaleString()}` : null} />
          <Field label="Assessed Land" value={parcel.assessedLandValue ? `$${Number(parcel.assessedLandValue).toLocaleString()}` : null} />
          <Field label="Assessed Total" value={parcel.assessedTotalValue ? `$${Number(parcel.assessedTotalValue).toLocaleString()}` : null} />
          <Field label="Years Owned"  value={parcel.yearsOwned} />
        </Section>

        <Section title="Zoning">
          <Field label="Code"         value={parcel.zoningCode} />
          <Field label="Description"  value={parcel.zoningDescription} />
          <Field label="Allowed Use"  value={parcel.allowedUseCategory} />
          <Field label="Min Lot Sqft" value={parcel.minLotSizeSqft?.toLocaleString()} />
          <Field label="Max Units/Ac" value={parcel.maxUnitsPerAcre} />
          <Field label="FAR"          value={parcel.floorAreaRatio} />
          <Field label="Max Height"   value={parcel.maxHeightFt ? `${parcel.maxHeightFt} ft` : null} />
          <Field label="Setbacks (F/S/R)" value={
            [parcel.frontSetbackFt, parcel.sideSetbackFt, parcel.rearSetbackFt]
              .map((v) => (v != null ? `${v}′` : "—"))
              .join(" / ")
          } />
        </Section>

        <Section title="Physical">
          <Field label="Topography"   value={parcel.topographyClass} />
          <Field label="Flood Zone"   value={parcel.floodZoneCode} />
          <Field label="Environmental Flag" value={<Bool v={parcel.hasEnvironmentalFlag} />} />
          <Field label="Access Type"  value={parcel.accessType} />
          <Field label="Existing Structure" value={<Bool v={parcel.hasExistingStructure} />} />
          <Field label="Existing Use" value={parcel.existingUseType} />
          <Field label="Existing Bldg Sqft" value={parcel.existingBuildingSqft?.toLocaleString()} />
        </Section>

        <Section title="Utilities & Schools">
          <Field label="Water" value={<Bool v={parcel.hasWater} />} />
          <Field label="Sewer" value={<Bool v={parcel.hasSewer} />} />
          <Field label="Power" value={<Bool v={parcel.hasPower} />} />
          <Field label="Gas"   value={<Bool v={parcel.hasGas} />} />
          <Field label="School District" value={parcel.schoolDistrict} />
          <Field label="School Score"    value={parcel.schoolScoreBucket} />
        </Section>

        <Section title="Market">
          <Field label="Nearby New Build $/Unit" value={parcel.nearbyNewBuildPricePerUnit ? `$${Number(parcel.nearbyNewBuildPricePerUnit).toLocaleString()}` : null} />
          <Field label="Resale $/sqft"           value={parcel.nearbyResalePricePerSqft ? `$${Number(parcel.nearbyResalePricePerSqft).toLocaleString()}` : null} />
          <Field label="Est. Land Value Total"   value={parcel.estimatedLandValueTotal ? `$${Number(parcel.estimatedLandValueTotal).toLocaleString()}` : null} />
          <Field label="Est. Value/Acre"         value={parcel.estimatedLandValuePerAcre ? `$${Number(parcel.estimatedLandValuePerAcre).toLocaleString()}` : null} />
          <Field label="Est. Value/Potential Lot" value={parcel.estimatedLandValuePerPotentialLot ? `$${Number(parcel.estimatedLandValuePerPotentialLot).toLocaleString()}` : null} />
        </Section>

        <Section title="Distress">
          <Field label="Tax Delinquent"  value={<Bool v={parcel.isTaxDelinquent} />} />
          <Field label="Delinquent Amt"  value={parcel.taxDelinquentAmount ? `$${Number(parcel.taxDelinquentAmount).toLocaleString()}` : null} />
          <Field label="Code Violations" value={<Bool v={parcel.hasCodeViolations} />} />
          <Field label="Violation Count" value={parcel.codeViolationCount} />
          <Field label="Preforeclosure"  value={<Bool v={parcel.hasPreforeclosureFlag} />} />
          <Field label="Vacant Land"     value={<Bool v={parcel.isVacantLand} />} />
          <Field label="Vacant Structure" value={<Bool v={parcel.isVacantStructure} />} />
        </Section>

        <Section title="Analysis">
          <Field label="Target Product" value={parcel.targetProductType} />
          <Field label="Est. Max Lots"  value={parcel.estMaxLotCount} />
          <Field label="Est. Max Units" value={parcel.estMaxUnitCount} />
          <Field label="Pipeline"       value={parcel.pipelineStatus} />
          <Field label="Notes"          value={parcel.notes} />
        </Section>
      </div>

      <AmaraReviewPanel parcelId={parcel.id} />
      <AssistantPanel parcelId={parcel.id} />
    </div>
  );
}

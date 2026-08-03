import type { Metadata } from "next";
import { getBrand } from "@aces/brand";
import { disclaimerSections } from "@aces/content";
import { LegalPageLayout } from "@aces/ui";

const brand = getBrand("investment-holdings");

export const metadata: Metadata = {
  title: "Disclaimer",
};

export default function DisclaimerPage() {
  return (
    <LegalPageLayout
      title="Disclaimer"
      sections={disclaimerSections(brand.name)}
    />
  );
}

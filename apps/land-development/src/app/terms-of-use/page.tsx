import type { Metadata } from "next";
import { getBrand } from "@aces/brand";
import { termsOfUseSections } from "@aces/content";
import { LegalPageLayout } from "@aces/ui";

const brand = getBrand("land-development");

export const metadata: Metadata = {
  title: "Terms of Use",
};

export default function TermsOfUsePage() {
  return (
    <LegalPageLayout
      title="Terms of Use"
      sections={termsOfUseSections(brand.name)}
    />
  );
}

import type { Metadata } from "next";
import { getBrand } from "@aces/brand";
import { privacyPolicySections } from "@aces/content";
import { LegalPageLayout } from "@aces/ui";

const brand = getBrand("capital");

export const metadata: Metadata = {
  title: "Privacy Policy",
};

export default function PrivacyPolicyPage() {
  return (
    <LegalPageLayout
      title="Privacy Policy"
      sections={privacyPolicySections(brand.name)}
    />
  );
}

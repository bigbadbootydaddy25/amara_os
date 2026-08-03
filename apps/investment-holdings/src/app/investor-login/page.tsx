import type { Metadata } from "next";
import { getBrand } from "@aces/brand";
import { ComingSoonPortalPage } from "@aces/ui";

const brand = getBrand("investment-holdings");

export const metadata: Metadata = {
  title: "Investor Login",
};

export default function InvestorLoginPage() {
  return <ComingSoonPortalPage siteName={brand.name} />;
}

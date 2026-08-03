import type { MetadataRoute } from "next";
import { getBrand } from "@aces/brand";

const brand = getBrand("capital");
const base = `https://${brand.domainPlaceholder}`;

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
    },
    sitemap: `${base}/sitemap.xml`,
  };
}

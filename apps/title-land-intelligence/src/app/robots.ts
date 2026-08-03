import type { MetadataRoute } from "next";
import { getBrand } from "@aces/brand";

const brand = getBrand("title-land-intelligence");
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

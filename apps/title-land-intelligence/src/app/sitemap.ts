import type { MetadataRoute } from "next";
import { getBrand } from "@aces/brand";

const brand = getBrand("title-land-intelligence");
const base = `https://${brand.domainPlaceholder}`;

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    { url: base, lastModified: new Date(), changeFrequency: "monthly", priority: 1 },
    { url: `${base}/privacy-policy`, lastModified: new Date(), changeFrequency: "yearly", priority: 0.3 },
    { url: `${base}/terms-of-use`, lastModified: new Date(), changeFrequency: "yearly", priority: 0.3 },
    { url: `${base}/disclaimer`, lastModified: new Date(), changeFrequency: "yearly", priority: 0.3 },
  ];
}

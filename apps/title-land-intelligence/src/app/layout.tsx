import type { Metadata } from "next";
import { Playfair_Display, Inter } from "next/font/google";
import { getBrand } from "@aces/brand";
import { titleLandIntelligenceContent } from "@aces/content";
import { Header, Footer, ThemeRoot } from "@aces/ui";
import "./globals.css";

const displayFont = Playfair_Display({
  subsets: ["latin"],
  variable: "--font-display",
  weight: ["500", "600", "700"],
});

const bodyFont = Inter({
  subsets: ["latin"],
  variable: "--font-body",
});

const brand = getBrand("title-land-intelligence");

export const metadata: Metadata = {
  metadataBase: new URL(`https://${brand.domainPlaceholder}`),
  title: {
    default: `${brand.name} | ${titleLandIntelligenceContent.hero.headline.join(" ")}`,
    template: `%s | ${brand.shortName}`,
  },
  description: brand.description,
  openGraph: {
    title: brand.name,
    description: brand.description,
    siteName: brand.name,
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: brand.name,
    description: brand.description,
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" data-scroll-behavior="smooth" className={`${displayFont.variable} ${bodyFont.variable}`}>
      <body>
        <ThemeRoot brand={brand}>
          <Header
            siteName={brand.name}
            shortName={brand.shortName}
            nav={titleLandIntelligenceContent.nav}
            ctaLabel={titleLandIntelligenceContent.hero.ctaLabel}
            ctaHref={titleLandIntelligenceContent.hero.ctaHref}
          />
          {children}
          <Footer
            siteName={brand.name}
            tagline={brand.tagline}
            nav={titleLandIntelligenceContent.nav}
            footerNote={titleLandIntelligenceContent.footerNote}
          />
        </ThemeRoot>
      </body>
    </html>
  );
}

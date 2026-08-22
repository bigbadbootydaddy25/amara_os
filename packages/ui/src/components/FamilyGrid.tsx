import Link from "next/link";
import type { SiteKey } from "@aces/brand";
import { getBrand } from "@aces/brand";

export interface FamilyLink {
  key: SiteKey;
  shortName: string;
  href: string;
}

export const familyLinks: FamilyLink[] = [
  { key: "capital", shortName: "Capital", href: "https://acesn8scapital.com" },
  {
    key: "land-development",
    shortName: "Land Development",
    href: "https://acesn8sland.com",
  },
  {
    key: "investment-holdings",
    shortName: "Investment Holdings",
    href: "https://acesn8sholdings.com",
  },
  {
    key: "title-land-intelligence",
    shortName: "Title & Land Intelligence",
    href: "https://acesn8stitle.com",
  },
];

export function FamilyGrid({ currentKey }: { currentKey: SiteKey }) {
  return (
    <section id="family" className="scroll-mt-24 border-t border-white/10 py-24">
      <div className="mx-auto max-w-[1240px] px-6">
        <span className="text-xs uppercase tracking-[0.22em] text-[var(--color-gold)]">
          Aces N 8s Family
        </span>
        <h2 className="mt-3 font-[var(--font-display)] text-[clamp(2.1rem,4vw,3.6rem)] font-semibold leading-[1.05] text-[var(--color-text)]">
          One platform. Four specialized companies.
        </h2>

        <div className="mt-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {familyLinks.map((link) => {
            const brand = getBrand(link.key);
            const isCurrent = link.key === currentKey;
            return (
              <Link
                key={link.key}
                href={isCurrent ? "/" : link.href}
                {...(isCurrent ? {} : { target: "_blank", rel: "noopener noreferrer" })}
                className="border border-white/10 px-4 py-4 text-center text-sm text-[#d8d0c1] transition-colors hover:border-[var(--color-gold)] hover:text-white"
                style={isCurrent ? { borderColor: brand.colors.gold, color: "#fff" } : undefined}
              >
                {link.shortName}
              </Link>
            );
          })}
        </div>
      </div>
    </section>
  );
}

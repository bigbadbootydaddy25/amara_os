# Aces N 8s Platform

Monorepo for the Aces N 8s family of companies: four branded, production-ready
Next.js sites sharing a common design system, plus the existing Amara OS app.

## Apps

- `apps/capital` — Aces N 8s Capital
- `apps/land-development` — Aces N 8s Land Development
- `apps/investment-holdings` — Aces N 8s Investment Holdings
- `apps/title-land-intelligence` — Aces N 8s Title & Land Intelligence
- `apps/amara-os` — Amara OS (voice-activated animated AI assistant, unrelated product retained from before this monorepo)

## Shared packages

- `packages/brand` — per-site design tokens (colors, glow, taglines, domain placeholders)
- `packages/content` — structured copy per site (nav, hero, sections, legal, contact)
- `packages/ui` — shared React components (Header, Footer, Hero, CTAButton, InfoCards,
  SectionTitle, ContactForm, LegalPageLayout, ComingSoonPortalPage, AnimatedBackground,
  StatsStrip, FeatureGrid)

## Getting started

```bash
npm install
npm run dev:capital                 # or dev:land-development / dev:investment-holdings
                                     # / dev:title-land-intelligence / dev:amara-os
```

Each app runs on port 3000 by default; pass `-- -p <port>` to run several at once, e.g.:

```bash
npm run dev:land-development -- -p 3001
```

## Build & lint

```bash
npm run build   # builds every workspace with a build script
npm run lint     # lints every workspace with a lint script
```

## Notes

- Brand colors/taglines/copy are placeholder-conservative: no fabricated financial
  performance, AUM, licensing, deal history, or team information. Replace placeholder
  contact emails, domains, and legal-page text with real client-supplied content
  before launch.
- Land Development intentionally omits proprietary acquisition/underwriting criteria.
- Investment Holdings' "Investor Login" routes to a Private Access Coming Soon page.

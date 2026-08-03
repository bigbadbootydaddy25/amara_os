import { titleLandIntelligenceContent } from "@aces/content";
import { Hero, StatsStrip, SectionTitle, FeatureGrid, ContactForm } from "@aces/ui";
import { ParcelIntelligenceViewer } from "@/components/ParcelIntelligenceViewer";

export default function Home() {
  return (
    <main>
      <Hero hero={titleLandIntelligenceContent.hero} backgroundVariant="blueprint" />

      {titleLandIntelligenceContent.stats ? (
        <StatsStrip stats={titleLandIntelligenceContent.stats} />
      ) : null}

      <section className="mx-auto max-w-7xl px-6 py-24 md:px-10">
        <SectionTitle
          eyebrow="Our Services"
          title="Research and intelligence built on precision."
        />
        <div className="mt-14">
          <FeatureGrid sections={titleLandIntelligenceContent.sections} columns={3} />
        </div>
      </section>

      <ParcelIntelligenceViewer />

      <section
        id="contact"
        className="scroll-mt-24 border-t border-[var(--color-border)] bg-[var(--color-bg-elevated)]"
      >
        <div className="mx-auto max-w-7xl px-6 py-24 md:px-10">
          <SectionTitle
            eyebrow="Get In Touch"
            title={titleLandIntelligenceContent.contact.heading}
          />
          <div className="mt-14">
            <ContactForm contact={titleLandIntelligenceContent.contact} />
          </div>
        </div>
      </section>
    </main>
  );
}

import { landDevelopmentContent } from "@aces/content";
import { Hero, StatsStrip, SectionTitle, FeatureGrid, ContactForm } from "@aces/ui";
import { SubdivisionVisualizer } from "@/components/SubdivisionVisualizer";

export default function Home() {
  return (
    <main>
      <Hero hero={landDevelopmentContent.hero} backgroundVariant="map-grid" />

      {landDevelopmentContent.stats ? (
        <StatsStrip stats={landDevelopmentContent.stats} />
      ) : null}

      <section className="mx-auto max-w-7xl px-6 py-24 md:px-10">
        <SectionTitle
          eyebrow="Our Process"
          title="From raw land to lasting communities."
        />
        <div className="mt-14">
          <FeatureGrid sections={landDevelopmentContent.sections} columns={3} />
        </div>
      </section>

      <SubdivisionVisualizer />

      <section
        id="contact"
        className="scroll-mt-24 border-t border-[var(--color-border)] bg-[var(--color-bg-elevated)]"
      >
        <div className="mx-auto max-w-7xl px-6 py-24 md:px-10">
          <SectionTitle
            eyebrow="Get In Touch"
            title={landDevelopmentContent.contact.heading}
          />
          <div className="mt-14">
            <ContactForm contact={landDevelopmentContent.contact} />
          </div>
        </div>
      </section>
    </main>
  );
}

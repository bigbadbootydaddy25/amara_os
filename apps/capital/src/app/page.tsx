import { capitalContent } from "@aces/content";
import { Hero, StatsStrip, SectionTitle, FeatureGrid, ContactForm } from "@aces/ui";

export default function Home() {
  return (
    <main>
      <Hero hero={capitalContent.hero} backgroundVariant="skyline" />

      {capitalContent.stats ? <StatsStrip stats={capitalContent.stats} /> : null}

      <section className="mx-auto max-w-7xl px-6 py-24 md:px-10">
        <SectionTitle
          eyebrow="What We Do"
          title="Strategic capital, applied with precision."
        />
        <div className="mt-14">
          <FeatureGrid sections={capitalContent.sections} columns={3} />
        </div>
      </section>

      <section
        id="contact"
        className="scroll-mt-24 border-t border-[var(--color-border)] bg-[var(--color-bg-elevated)]"
      >
        <div className="mx-auto max-w-7xl px-6 py-24 md:px-10">
          <SectionTitle eyebrow="Get In Touch" title={capitalContent.contact.heading} />
          <div className="mt-14">
            <ContactForm contact={capitalContent.contact} />
          </div>
        </div>
      </section>
    </main>
  );
}

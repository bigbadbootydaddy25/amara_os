import { investmentHoldingsContent } from "@aces/content";
import { Hero, StatsStrip, SectionTitle, FeatureGrid, ContactForm } from "@aces/ui";

export default function Home() {
  return (
    <main>
      <Hero hero={investmentHoldingsContent.hero} backgroundVariant="aurora" />

      {investmentHoldingsContent.stats ? (
        <StatsStrip stats={investmentHoldingsContent.stats} />
      ) : null}

      <section className="mx-auto max-w-7xl px-6 py-24 md:px-10">
        <SectionTitle
          eyebrow="How We Operate"
          title="Disciplined capital. Private partnership."
        />
        <div className="mt-14">
          <FeatureGrid sections={investmentHoldingsContent.sections} columns={3} />
        </div>
      </section>

      <section
        id="contact"
        className="scroll-mt-24 border-t border-[var(--color-border)] bg-[var(--color-bg-elevated)]"
      >
        <div className="mx-auto max-w-7xl px-6 py-24 md:px-10">
          <SectionTitle
            eyebrow="Get In Touch"
            title={investmentHoldingsContent.contact.heading}
          />
          <div className="mt-14">
            <ContactForm contact={investmentHoldingsContent.contact} />
          </div>
        </div>
      </section>
    </main>
  );
}

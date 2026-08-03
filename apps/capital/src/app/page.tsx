import { getBrand } from "@aces/brand";
import { capitalContent, divisions, valueChainStages } from "@aces/content";
import {
  Hero,
  StatsStrip,
  SectionTitle,
  FeatureGrid,
  ContactForm,
  IconFeatureRow,
  SpadeIcon,
  DiamondIcon,
  ClubIcon,
  HeartIcon,
} from "@aces/ui";
import { CommandCenter } from "@/components/CommandCenter";
import { ValueChainSequence } from "@/components/ValueChainSequence";

const brand = getBrand("capital");
const suitIcons = [SpadeIcon, DiamondIcon, ClubIcon, HeartIcon];

export default function Home() {
  const suitFeatures = capitalContent.sections.slice(0, 4).map((section, i) => {
    const Icon = suitIcons[i];
    return {
      icon: <Icon className="h-6 w-6" />,
      label: section.title,
      body: section.body,
    };
  });

  return (
    <main>
      <Hero hero={capitalContent.hero} backgroundVariant="skyline" accentLastLine />

      <IconFeatureRow items={suitFeatures} />

      {brand.tagline ? (
        <div className="border-b border-[var(--color-border)] bg-[var(--color-bg-elevated)] py-6 text-center">
          <p className="font-[var(--font-display)] text-sm uppercase tracking-[0.3em] text-[var(--color-gold)]">
            {brand.tagline}
          </p>
        </div>
      ) : null}

      <CommandCenter capitalName="Aces N 8s Capital" divisions={divisions} />

      <ValueChainSequence stages={valueChainStages} />

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

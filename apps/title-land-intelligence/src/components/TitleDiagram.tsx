"use client";

import { StepDiagram, DiagramLayer, type StepDiagramStep } from "@aces/ui";

const steps: StepDiagramStep[] = [
  { label: "Parcel Layer" },
  { label: "Instrument Search" },
  { label: "Ownership Chain" },
  { label: "Mineral & Surface" },
  { label: "Curative Issues" },
  { label: "Decision Support" },
];

export function TitleDiagram() {
  return (
    <StepDiagram steps={steps}>
      {(active) => (
        <svg
          viewBox="0 0 900 440"
          role="img"
          aria-label="Title chain and parcel intelligence"
          className="h-full w-full"
        >
          <DiagramLayer layer={0} activeIndex={active}>
            <path
              d="M80 85H820V355H80Z"
              fill="none"
              stroke="var(--color-gold)"
              strokeWidth={2}
            />
          </DiagramLayer>

          <DiagramLayer layer={1} activeIndex={active}>
            <path
              d="M80 220H820M300 85V355M540 85V355"
              fill="none"
              stroke="var(--color-gold)"
              strokeWidth={2}
            />
          </DiagramLayer>

          <DiagramLayer layer={2} activeIndex={active}>
            <rect x={120} y={120} width={150} height={70} fill="#0c1a26" stroke="#d4af37" />
            <text x={195} y={160} fontSize={12} textAnchor="middle" fill="#efe7d2">
              VESTING
            </text>
          </DiagramLayer>

          <DiagramLayer layer={3} activeIndex={active}>
            <rect x={375} y={120} width={150} height={70} fill="#0c1a26" stroke="#d4af37" />
            <text x={450} y={160} fontSize={12} textAnchor="middle" fill="#efe7d2">
              CHAIN
            </text>
            <path d="M270 155H375M525 155H630" fill="none" stroke="#d4af37" strokeWidth={2} />
          </DiagramLayer>

          <DiagramLayer layer={4} activeIndex={active}>
            <rect x={630} y={120} width={150} height={70} fill="#0c1a26" stroke="#d4af37" />
            <text x={705} y={160} fontSize={12} textAnchor="middle" fill="#efe7d2">
              CURATIVE
            </text>
          </DiagramLayer>

          <DiagramLayer layer={5} activeIndex={active}>
            <path d="M525 235L630 325" stroke="#8c1515" strokeWidth={5} />
          </DiagramLayer>
        </svg>
      )}
    </StepDiagram>
  );
}

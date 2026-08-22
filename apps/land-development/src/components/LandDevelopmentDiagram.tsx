"use client";

import { StepDiagram, DiagramLayer, type StepDiagramStep } from "@aces/ui";

const steps: StepDiagramStep[] = [
  { label: "Raw Land" },
  { label: "Survey & Plat" },
  { label: "Road Network" },
  { label: "Water Lines" },
  { label: "Sewer & Drainage" },
  { label: "Finished Lots" },
];

const lots = [
  { x: 105, y: 95 },
  { x: 255, y: 95 },
  { x: 530, y: 280 },
  { x: 680, y: 280 },
];

export function LandDevelopmentDiagram() {
  return (
    <StepDiagram steps={steps}>
      {(active) => (
        <svg
          viewBox="0 0 900 440"
          role="img"
          aria-label="Subdivision infrastructure sequence"
          className="h-full w-full"
        >
          <DiagramLayer layer={0} activeIndex={active}>
            <path d="M40 50H860V390H40Z" stroke="#3f6f4f" fill="#152018" />
          </DiagramLayer>

          <DiagramLayer layer={1} activeIndex={active}>
            <path
              d="M100 80V360M230 80V360M360 80V360M490 80V360M620 80V360M750 80V360"
              stroke="var(--color-gold)"
              fill="none"
              strokeWidth={2}
            />
            <path d="M70 150H830M70 260H830" stroke="var(--color-gold)" fill="none" strokeWidth={2} />
          </DiagramLayer>

          <DiagramLayer layer={2} activeIndex={active}>
            <path d="M70 205H830" stroke="#8b8b8b" fill="none" strokeWidth={18} />
            <path d="M425 70V370" stroke="#8b8b8b" fill="none" strokeWidth={18} />
          </DiagramLayer>

          <DiagramLayer layer={3} activeIndex={active}>
            <path d="M80 185H820" stroke="#2d7dc0" fill="none" strokeWidth={5} />
            <path d="M405 80V360" stroke="#2d7dc0" fill="none" strokeWidth={5} />
          </DiagramLayer>

          <DiagramLayer layer={4} activeIndex={active}>
            <path
              d="M80 230H820"
              stroke="#6d8f59"
              fill="none"
              strokeWidth={5}
              strokeDasharray="10 8"
            />
            <path
              d="M445 80V360"
              stroke="#6d8f59"
              fill="none"
              strokeWidth={5}
              strokeDasharray="10 8"
            />
          </DiagramLayer>

          <DiagramLayer layer={5} activeIndex={active}>
            {lots.map((lot) => (
              <rect
                key={`${lot.x}-${lot.y}`}
                x={lot.x}
                y={lot.y}
                width={75}
                height={40}
                fill="#efe7d2"
                stroke="#c8b789"
              />
            ))}
          </DiagramLayer>
        </svg>
      )}
    </StepDiagram>
  );
}

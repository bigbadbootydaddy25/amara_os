import type { SVGProps } from "react";

export type IconProps = SVGProps<SVGSVGElement>;

const base = {
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.4,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

export function SpadeIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <path d="M12 3c-3 3.4-7 6.4-7 10a5 5 0 0 0 8.2 3.8C13 18.4 12 20 10.5 21h7C16 20 15 18.4 14.8 16.8A5 5 0 0 0 19 13c0-3.6-4-6.6-7-10Z" />
    </svg>
  );
}

export function DiamondIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <path d="M12 2 20 12 12 22 4 12Z" />
    </svg>
  );
}

export function ClubIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <circle cx="12" cy="8.5" r="3.4" />
      <circle cx="8" cy="13" r="3.4" />
      <circle cx="16" cy="13" r="3.4" />
      <path d="M12 13v3.5c0 1.7.7 3 2 4.5H10c1.3-1.5 2-2.8 2-4.5V13" />
    </svg>
  );
}

export function HeartIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <path d="M12 21s-7.5-4.9-10-9.3C.5 8.2 2.3 5 5.6 5 8 5 10 6.4 12 9c2-2.6 4-4 6.4-4 3.3 0 5.1 3.2 3.6 6.7C19.5 16.1 12 21 12 21Z" />
    </svg>
  );
}

export function PinIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <path d="M12 22s7-7.4 7-12.5A7 7 0 0 0 5 9.5C5 14.6 12 22 12 22Z" />
      <circle cx="12" cy="9.5" r="2.4" />
    </svg>
  );
}

export function DocumentIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <path d="M6 2.5h8l4 4V21a.5.5 0 0 1-.5.5h-11A.5.5 0 0 1 6 21Z" />
      <path d="M14 2.5V7h4" />
      <path d="M9 12h6M9 15.5h6M9 8.5h2" />
    </svg>
  );
}

export function BlueprintIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <rect x="3" y="3" width="18" height="18" rx="1" />
      <path d="M3 9h18M3 15h18M9 3v18M15 3v18" strokeWidth={1} opacity={0.6} />
    </svg>
  );
}

export function BuildingIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <rect x="4" y="9" width="7" height="12" />
      <rect x="13" y="4" width="7" height="17" />
      <path d="M6.5 12h2M6.5 15h2M6.5 18h2M15.5 7h2M15.5 10h2M15.5 13h2M15.5 16h2" />
    </svg>
  );
}

export function ChartUpIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <path d="M3 20h18" />
      <path d="M4 16l5-6 4 3 7-8" />
      <path d="M15 5h5v5" />
    </svg>
  );
}

export function TargetIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="12" r="5" />
      <circle cx="12" cy="12" r="1" fill="currentColor" />
    </svg>
  );
}

export function ShieldIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <path d="M12 2.5 20 6v6c0 5-3.5 8.3-8 9.5-4.5-1.2-8-4.5-8-9.5V6Z" />
      <path d="M8.5 12l2.3 2.3L15.5 9.5" />
    </svg>
  );
}

export function UsersIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <circle cx="9" cy="8" r="3.2" />
      <path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6" />
      <circle cx="17" cy="9" r="2.6" />
      <path d="M15.8 14.2c2.6.4 4.7 2.6 4.7 5.8" />
    </svg>
  );
}

export function ClockIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3.5 2" />
    </svg>
  );
}

export function HandshakeIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <path d="M2 11l4-3 4 2 3-2 3 2 4-2 2 3-4 5-3-2-2 2h-3l-2-2-3 2Z" />
    </svg>
  );
}

export function SearchIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <circle cx="11" cy="11" r="7" />
      <path d="M20 20l-4.35-4.35" />
    </svg>
  );
}

export function BankIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <path d="M3 9.5 12 4l9 5.5" />
      <path d="M4 10h16v1.5H4Z" />
      <path d="M5.5 12v7M9.5 12v7M14.5 12v7M18.5 12v7" />
      <path d="M3 20.5h18" />
    </svg>
  );
}

export function MapIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <path d="M9 3 3 5v16l6-2 6 2 6-2V3l-6 2-6-2Z" />
      <path d="M9 3v16M15 5v16" />
    </svg>
  );
}

export function DropIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <path d="M12 2.5c4 5 7 8.8 7 12.5a7 7 0 1 1-14 0c0-3.7 3-7.5 7-12.5Z" />
    </svg>
  );
}

export function HomeIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <path d="M3.5 11 12 4l8.5 7" />
      <path d="M5.5 9.5V20h13V9.5" />
      <path d="M10 20v-6h4v6" />
    </svg>
  );
}

export function LockIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <rect x="4" y="11" width="16" height="9" rx="2" />
      <path d="M8 11V7a4 4 0 0 1 8 0v4" />
    </svg>
  );
}

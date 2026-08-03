import type { ReactNode, CSSProperties } from "react";
import { brandCssVars, type BrandTokens } from "@aces/brand";

export interface ThemeRootProps {
  brand: BrandTokens;
  children: ReactNode;
}

export function ThemeRoot({ brand, children }: ThemeRootProps) {
  return (
    <div
      style={brandCssVars(brand) as CSSProperties}
      className="min-h-screen bg-[var(--color-bg)] text-[var(--color-text)] antialiased"
    >
      {children}
    </div>
  );
}

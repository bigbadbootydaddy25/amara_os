import Link from "next/link";
import type { AnchorHTMLAttributes } from "react";
import { cx } from "../lib/cx";

export interface CTAButtonProps
  extends Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href"> {
  href: string;
  variant?: "primary" | "secondary" | "ghost";
  size?: "md" | "sm";
  children: React.ReactNode;
}

export function CTAButton({
  href,
  variant = "primary",
  size = "md",
  className,
  children,
  ...rest
}: CTAButtonProps) {
  const base =
    "group relative inline-flex items-center gap-2 rounded-full text-sm font-medium tracking-wide uppercase transition-all duration-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2";

  const sizes: Record<string, string> = {
    md: "px-7 py-3 text-sm",
    sm: "px-4 py-2 text-xs",
  };

  const variants: Record<string, string> = {
    primary:
      "bg-[var(--color-gold)] text-[var(--color-bg)] hover:bg-[var(--color-gold-soft)] shadow-[0_0_0_1px_var(--color-gold)] hover:shadow-[0_0_30px_var(--glow)] focus-visible:outline-[var(--color-gold)]",
    secondary:
      "bg-transparent text-[var(--color-text)] border border-[var(--color-border)] hover:border-[var(--color-gold)] hover:text-[var(--color-gold)] focus-visible:outline-[var(--color-gold)]",
    ghost:
      "bg-transparent text-[var(--color-gold)] hover:text-[var(--color-gold-soft)] focus-visible:outline-[var(--color-gold)]",
  };

  const isExternal = /^https?:\/\//.test(href);

  const content = (
    <>
      <span>{children}</span>
      <span
        aria-hidden
        className="inline-block transition-transform duration-300 group-hover:translate-x-1"
      >
        &rarr;
      </span>
    </>
  );

  if (isExternal) {
    return (
      <a
        href={href}
        className={cx(base, sizes[size], variants[variant], className)}
        target="_blank"
        rel="noopener noreferrer"
        {...rest}
      >
        {content}
      </a>
    );
  }

  return (
    <Link href={href} className={cx(base, sizes[size], variants[variant], className)} {...rest}>
      {content}
    </Link>
  );
}

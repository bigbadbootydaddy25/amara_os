import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AMARA OS — Acquisitions Intelligence",
  description: "Mission Control for deal-ready real estate acquisitions",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-[#050508] text-slate-100 antialiased">
        {children}
      </body>
    </html>
  );
}

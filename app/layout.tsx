import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "AMARA OS",
  description: "AMARA OS Command Interface",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body style={{ margin: 0, padding: 0 }}>{children}</body>
    </html>
  );
}

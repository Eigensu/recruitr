import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Binge Consulting — Recruitment",
  description:
    "A high-performance recruitment platform by Binge Consulting. Hospitality recruitment, reimagined.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

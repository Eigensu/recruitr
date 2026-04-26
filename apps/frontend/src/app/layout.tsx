import type { Metadata } from "next";
import { Arimo } from "next/font/google";
import "./globals.css";

const arimo = Arimo({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-arimo",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Binge Consulting — Recruitment",
  description:
    "A high-performance recruitment platform by Binge Consulting. Hospitality recruitment, reimagined.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={arimo.variable} data-scroll-behavior="smooth">
      <body>{children}</body>
    </html>
  );
}

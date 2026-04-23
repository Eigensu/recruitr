import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Eigensu — Gamified Recruitment CRM",
  description:
    "A high-performance, multi-tenant recruitment CRM with real-time gamification and drag-and-drop candidate pipeline management.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="bg-gray-950 text-gray-50 antialiased font-sans">{children}</body>
    </html>
  );
}

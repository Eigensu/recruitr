import type { Metadata } from "next";
import "./globals.css";
import { ThemeProvider } from "@/context/ThemeContext";

export const metadata: Metadata = {
  title: "Binge Consulting — Recruitment",
  description:
    "A high-performance recruitment platform by Binge Consulting. Hospitality recruitment, reimagined.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){var t='dark';try{var stored=localStorage.getItem('binge-theme');if(stored==='dark'||stored==='light'){t=stored;}else if(window.matchMedia){t=window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light';}}catch(e){t='dark';}document.documentElement.setAttribute('data-theme',t);})();`,
          }}
        />
      </head>
      <body>
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}

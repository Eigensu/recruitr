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
        {/* Start the heading-font download immediately, in parallel with HTML
            parsing, instead of waiting for the CSSOM to discover the
            @font-face rule. Without this, a cold cache (e.g. a hard refresh)
            shows the fallback sans-serif for the full font-display: swap
            window — regular + bold cover every font-heading usage in the app. */}
        <link
          rel="preload"
          href="/fonts/galderglynn-titling-regular.woff2"
          as="font"
          type="font/woff2"
          crossOrigin="anonymous"
        />
        <link
          rel="preload"
          href="/fonts/galderglynn-titling-bold.woff2"
          as="font"
          type="font/woff2"
          crossOrigin="anonymous"
        />
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

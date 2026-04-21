import type { Metadata } from "next";
import { Inter, Source_Serif_4 } from "next/font/google";
import "./globals.css";
import { ThemeProvider } from "@/components/theme-provider";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const sourceSerif = Source_Serif_4({
  subsets: ["latin"],
  variable: "--font-source-serif",
  display: "swap",
  weight: ["400", "600", "700"],
});

export const metadata: Metadata = {
  title: {
    default: "Tourism & Hospitality Research Navigator",
    template: "%s | Tourism & Hospitality Research Navigator",
  },
  description:
    "Search papers, authors, and journals across a curated whitelist of tourism and hospitality research.",
  openGraph: {
    type: "website",
    siteName: "Tourism & Hospitality Research Navigator",
    description:
      "A curated navigator for tourism and hospitality scholarship.",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${inter.variable} ${sourceSerif.variable}`}
    >
      <body className="min-h-screen flex flex-col bg-surface text-ink">
        <ThemeProvider>
          <SiteHeader />
          <main className="flex-1">{children}</main>
          <SiteFooter />
        </ThemeProvider>
      </body>
    </html>
  );
}

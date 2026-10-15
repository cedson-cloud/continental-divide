import type { Metadata } from "next";
import { Instrument_Sans, JetBrains_Mono } from "next/font/google";
import { AppNav } from "@/components/AppNav";
import { SITE_URL } from "@/lib/demo";
import "./globals.css";

const sans = Instrument_Sans({ subsets: ["latin"], variable: "--font-sans" });
const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono" });

// The link preview is opengraph-image.png beside this file, drawn from
// docs/images/link-preview.html.
export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: "Continental Divide",
  description:
    "Ask for an analytics event in a sentence. A model drafts it, fixed rules check it, " +
    "a person approves it, and it joins the tracking plan with code for engineers.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${sans.variable} ${mono.variable}`}>
      <body>
        <a href="#content" className="skip-link">
          Skip to content
        </a>
        <div className="app">
          <AppNav />
          <div id="content" className="app-main" tabIndex={-1}>
            {children}
          </div>
        </div>
      </body>
    </html>
  );
}

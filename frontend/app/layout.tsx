import type { Metadata } from "next";
import { Instrument_Sans, JetBrains_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const sans = Instrument_Sans({ subsets: ["latin"], variable: "--font-sans" });
const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono" });

export const metadata: Metadata = {
  title: "Continental Divide",
  description: "Event-tracking request intake, validation, approval, and publish.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${sans.variable} ${mono.variable}`}>
      <body>
        <header className="site-header">
          <div className="site-header-inner">
            <div className="brand">
              Continental Divide<span>tracking governance</span>
            </div>
            <nav className="nav">
              <Link href="/">Intake</Link>
              <Link href="/catalog">Catalog</Link>
              <Link href="/queue">Queue</Link>
              <Link href="/admin">Governance</Link>
            </nav>
          </div>
        </header>
        {children}
      </body>
    </html>
  );
}

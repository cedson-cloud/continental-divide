import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

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
    <html lang="en">
      <body>
        <header className="site-header">
          <div className="site-header-inner">
            <div className="brand">
              Continental Divide<span>tracking governance</span>
            </div>
            <nav className="nav">
              <Link href="/">Intake</Link>
              <Link href="/queue">Queue</Link>
            </nav>
          </div>
        </header>
        {children}
      </body>
    </html>
  );
}

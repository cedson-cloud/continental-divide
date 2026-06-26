import type { Metadata } from "next";
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
      <body>{children}</body>
    </html>
  );
}

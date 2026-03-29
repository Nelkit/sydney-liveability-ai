import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Sydney Liveability AI",
  description: "AI-driven spatial liveability engine for Sydney suburbs."
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

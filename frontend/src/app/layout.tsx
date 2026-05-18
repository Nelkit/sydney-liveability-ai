import type { Metadata } from "next";
import "./globals.css";

const BASE_URL = "https://sydney-liveability-ai.vercel.app";

export const metadata: Metadata = {
  metadataBase: new URL(BASE_URL),
  title: "Sydney Liveability AI",
  description: "Compare Sydney suburbs using civic data, crime statistics, and real resident sentiment. Tell me what matters to you — I'll build your profile and open the live map.",
  alternates: {
    canonical: BASE_URL,
  },
  openGraph: {
    title: "Find your suburb with AI-grounded data",
    description: "Compare Sydney suburbs using civic data, crime statistics, and real resident sentiment. Tell me what matters to you — I'll build your profile and open the live map.",
    url: BASE_URL,
    siteName: "Sydney Liveability AI",
    images: [
      {
        url: "/img/og-image.png",
        width: 1200,
        height: 630,
        alt: "Sydney Liveability AI — explore suburbs with AI",
      },
    ],
    locale: "en_AU",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Find your suburb with AI-grounded data",
    description: "Compare Sydney suburbs using civic data, crime statistics, and real resident sentiment. Tell me what matters to you — I'll build your profile and open the live map.",
    images: ["/img/og-image.png"],
  },
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

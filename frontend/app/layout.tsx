import type { Metadata, Viewport } from "next";
import { Fraunces, Outfit, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";

const display = Fraunces({
  subsets: ["latin"],
  weight: ["500", "600", "700"],
  variable: "--font-display",
});

const body = Outfit({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-body",
});

const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
});

const description =
  "SSRI (SubSurface Risk Intelligence) helps planners, engineers, and communities estimate subsidence, landslide, and sinkhole susceptibility from maps and satellite data.";

export const metadata: Metadata = {
  applicationName: "SSRI",
  title: {
    default: "SSRI — See the ground before you build",
    template: "%s — SSRI",
  },
  description,
  keywords: [
    "SSRI",
    "SubSurface Risk Intelligence",
    "subsidence",
    "landslide",
    "sinkhole",
    "ground risk",
  ],
  authors: [{ name: "SSRI" }],
  creator: "SSRI",
  openGraph: {
    type: "website",
    siteName: "SSRI",
    title: "SSRI — SubSurface Risk Intelligence",
    description,
  },
  twitter: {
    card: "summary",
    title: "SSRI — SubSurface Risk Intelligence",
    description,
  },
};

export const viewport: Viewport = {
  themeColor: "#1B4332",
  colorScheme: "light",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${display.variable} ${body.variable} ${mono.variable}`}>
      <body>{children}</body>
    </html>
  );
}

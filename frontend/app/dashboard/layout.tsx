import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Assessment map",
  description: "Map a place and estimate subsidence, landslide, and sinkhole susceptibility.",
};

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return children;
}

import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Datasets",
  description: "Datasets you have uploaded for SSRI training.",
};

export default function DatasetsLayout({ children }: { children: React.ReactNode }) {
  return children;
}

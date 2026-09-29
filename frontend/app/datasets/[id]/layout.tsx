import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Dataset",
  description: "A dataset version uploaded for SSRI training.",
};

export default function DatasetDetailLayout({ children }: { children: React.ReactNode }) {
  return children;
}

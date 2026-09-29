import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Manual training",
  description: "Upload a Stage 2.5 dataset or a compatible spatial CSV and train an SSRI model.",
};

export default function TrainingLayout({ children }: { children: React.ReactNode }) {
  return children;
}

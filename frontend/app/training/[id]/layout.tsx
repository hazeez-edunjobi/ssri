import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Training run",
  description: "Status of an SSRI training run. Completion does not mean the model is scientifically validated.",
};

export default function TrainingRunLayout({ children }: { children: React.ReactNode }) {
  return children;
}

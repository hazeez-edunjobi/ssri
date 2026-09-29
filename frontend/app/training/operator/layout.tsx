import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Operator training",
  description: "Advanced operator controls for SSRI Stage 2.5 training.",
};

export default function OperatorTrainingLayout({ children }: { children: React.ReactNode }) {
  return children;
}

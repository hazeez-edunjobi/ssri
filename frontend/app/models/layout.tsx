import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Models",
  description: "Checkpoints produced by SSRI training. A finished run is not scientifically validated.",
};

export default function ModelsLayout({ children }: { children: React.ReactNode }) {
  return children;
}

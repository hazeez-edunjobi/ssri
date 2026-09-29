import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Model",
  description: "An SSRI checkpoint. Training completion does not mean the model is scientifically validated.",
};

export default function ModelDetailLayout({ children }: { children: React.ReactNode }) {
  return children;
}

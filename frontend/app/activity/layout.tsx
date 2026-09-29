import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Activity",
  description: "Recent dataset, training, and model activity on your SSRI account.",
};

export default function ActivityLayout({ children }: { children: React.ReactNode }) {
  return children;
}

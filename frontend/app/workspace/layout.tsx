import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Workspace",
  description: "Your SSRI account home for datasets, training, and recent activity.",
};

export default function WorkspaceLayout({ children }: { children: React.ReactNode }) {
  return children;
}

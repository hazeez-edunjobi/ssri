import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Log in",
  description: "Log in to SSRI to open datasets, training runs, and the assessment map.",
};

export default function LoginLayout({ children }: { children: React.ReactNode }) {
  return children;
}

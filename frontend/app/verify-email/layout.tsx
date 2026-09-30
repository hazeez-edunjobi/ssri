import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Check your inbox",
  description: "Confirm the email address for your SSRI account.",
};

export default function VerifyEmailLayout({ children }: { children: React.ReactNode }) {
  return children;
}

import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Create account",
  description: "Create an SSRI account to check the ground before you build.",
};

export default function SignupLayout({ children }: { children: React.ReactNode }) {
  return children;
}

import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Update password",
  description: "Choose a new password for your SSRI account.",
};

export default function ResetPasswordLayout({ children }: { children: React.ReactNode }) {
  return children;
}

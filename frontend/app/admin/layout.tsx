import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Admin",
  description: "SSRI administration for accounts with the admin role.",
};

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return children;
}

import { Navbar } from "@/components/landing/Navbar";
import { Footer } from "@/components/landing/Footer";

type SiteShellProps = {
  children: React.ReactNode;
};

export function SiteShell({ children }: SiteShellProps) {
  return (
    <div className="min-h-screen bg-mist text-bark">
      <Navbar />
      {children}
      <Footer />
    </div>
  );
}

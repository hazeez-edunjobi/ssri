import { Loader } from "@/components/ui/loader";

export default function DashboardLoading() {
  return (
    <main className="min-h-screen bg-mist">
      <Loader
        variant="page"
        title="Opening assessment workspace"
        description="Loading the dashboard route before session and system preparation."
        stage="SSRI dashboard"
        data-testid="dashboard-route-loading"
      />
    </main>
  );
}

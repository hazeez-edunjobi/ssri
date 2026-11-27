import { Loader } from "@/components/ui/loader";

export default function DashboardLoading() {
  return (
    <main className="min-h-screen bg-mist">
      <Loader
        variant="page"
        title="Opening assessment workspace"
        description="Preparing the map and operator controls."
        data-testid="dashboard-route-loading"
      />
    </main>
  );
}

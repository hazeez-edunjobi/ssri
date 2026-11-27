import { Loader } from "@/components/ui/loader";

export default function AssessmentsLoading() {
  return (
    <main className="min-h-screen bg-mist">
      <Loader
        variant="page"
        title="Opening assessment history"
        description="Loading the operational archive."
        data-testid="assessments-route-loading"
      />
    </main>
  );
}

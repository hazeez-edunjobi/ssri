"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { PlatformShell } from "@/components/platform/PlatformShell";
import { platformGet, uploadDatasetVersion } from "@/lib/platformApi";

type Version = {
  id: string;
  version: number;
  file_name: string;
  validation_status: string;
  validation_errors: string[];
  crs: string | null;
  channel_count: number | null;
  content_sha256: string | null;
};

export default function DatasetDetailPage() {
  const params = useParams<{ id: string }>();
  const [name, setName] = useState("");
  const [versions, setVersions] = useState<Version[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function reload() {
    platformGet<{ dataset: { name: string }; versions: Version[] }>(`/datasets/${params.id}`)
      .then((body) => {
        setName(body.dataset.name);
        setVersions(body.versions);
      })
      .catch((err: Error) => setError(err.message));
  }

  useEffect(() => {
    if (params.id) reload();
  }, [params.id]);

  return (
    <PlatformShell>
      <h1 className="font-display text-2xl">{name || "Dataset"}</h1>
      <p className="mt-2 text-sm text-stone">
        Upload a zip with 13-channel feature stacks and labels. A new upload becomes the next version and does not replace earlier ones.
      </p>
      <label className="mt-6 block rounded-2xl border border-dashed border-meadow bg-chalk p-6 text-sm">
        {busy ? "Uploading…" : "Choose a .zip dataset"}
        <input
          className="mt-3 block text-xs"
          type="file"
          accept=".zip,application/zip"
          disabled={busy}
          onChange={async (event) => {
            const file = event.target.files?.[0];
            if (!file) return;
            setBusy(true);
            setError(null);
            try {
              await uploadDatasetVersion(params.id, file);
              reload();
            } catch (err) {
              setError(err instanceof Error ? err.message : "Upload failed");
            } finally {
              setBusy(false);
            }
          }}
        />
      </label>
      {error && <p className="mt-4 text-sm text-amber-900">{error}</p>}
      {versions.length === 0 ? (
        <p className="mt-6 text-sm text-stone">No versions yet.</p>
      ) : (
        <ul className="mt-6 space-y-3">
          {versions.map((version) => (
            <li key={version.id} className="rounded-2xl border border-meadow bg-chalk p-4 text-sm">
              <div>Version {version.version} · {version.file_name}</div>
              <div className="text-xs text-stone">
                {version.validation_status} · channels {version.channel_count ?? "—"} · CRS {version.crs || "—"}
              </div>
              {version.validation_errors.length > 0 && (
                <ul className="mt-2 text-xs text-amber-900">
                  {version.validation_errors.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
      )}
    </PlatformShell>
  );
}

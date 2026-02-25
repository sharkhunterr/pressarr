import { useQuery } from "@tanstack/react-query";
import { apiGet } from "../lib/api";

interface SystemStatus {
  version: string;
  uptime: number;
  startTime: string;
  magazineCount: number;
  issueCount: number;
  issueFileCount: number;
}

export function HomePage() {
  const { data: status } = useQuery({
    queryKey: ["system-status"],
    queryFn: () => apiGet<SystemStatus>("/api/v1/system/status"),
    refetchInterval: 30_000,
  });

  return (
    <div className="min-h-screen bg-zinc-950">
      {/* Header */}
      <header className="border-b border-zinc-800 px-6 py-4">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-zinc-100">
            <span className="text-accent">Press</span>arr
          </h1>
          {status && (
            <span className="text-xs text-zinc-500">v{status.version}</span>
          )}
        </div>
      </header>

      {/* Main content — empty library state */}
      <main className="flex flex-col items-center justify-center px-6 py-24">
        <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-12 text-center">
          <div className="mb-4 text-5xl">📰</div>
          <h2 className="mb-2 text-xl font-semibold text-zinc-200">
            Aucun magazine dans la bibliothèque
          </h2>
          <p className="text-sm text-zinc-500">
            Ajoutez votre premier magazine pour commencer.
          </p>
        </div>
      </main>
    </div>
  );
}

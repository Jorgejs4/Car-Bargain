import { fetchHealth } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function HealthPage() {
  let health: { database: string; redis: string } | null = null;
  let error: string | null = null;
  try {
    health = await fetchHealth();
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
  }

  const ok = health?.database === "ok" && health?.redis === "ok";

  return (
    <div className="mx-auto max-w-2xl px-4 py-8">
      <h1 className="mb-4 text-2xl font-bold">Salud del sistema</h1>
      {error ? (
        <div className="rounded-xl border border-red-300 bg-red-50 p-4 text-sm text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-300">
          No se pudo conectar con el backend: {error}
        </div>
      ) : (
        <div className="space-y-3">
          <div className="flex items-center justify-between rounded-xl border border-neutral-200 p-4 dark:border-neutral-800">
            <span className="font-medium">Base de datos (PostgreSQL)</span>
            <Status value={health?.database} />
          </div>
          <div className="flex items-center justify-between rounded-xl border border-neutral-200 p-4 dark:border-neutral-800">
            <span className="font-medium">Redis</span>
            <Status value={health?.redis} />
          </div>
          {ok && (
            <p className="rounded-xl border border-emerald-300 bg-emerald-50 p-4 text-sm text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
              Todo operativo.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function Status({ value }: { value: string | undefined }) {
  const ok = value === "ok";
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${
        ok
          ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"
          : "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300"
      }`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${ok ? "bg-emerald-500" : "bg-red-500"}`} />
      {value ?? "?"}
    </span>
  );
}

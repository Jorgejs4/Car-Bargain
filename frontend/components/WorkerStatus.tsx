"use client";

import { useCallback, useEffect, useState } from "react";
import { API_BASE_URL } from "@/lib/api";

export function WorkerStatus() {
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const refresh = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const res = await fetch(`${API_BASE_URL}/internal/worker-status`, { cache: "no-store" });
      if (!res.ok) throw new Error(`API ${res.status}`);
      setData(await res.json());
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => {
    const timer = window.setTimeout(() => { void refresh(); }, 0);
    return () => window.clearTimeout(timer);
  }, [refresh]);
  const count = (name: string) => typeof data?.[name] === "number" ? data[name] as number : 0;
  const taskGroups = (name: string) => {
    const value = data?.[name];
    return value && typeof value === "object" ? Object.entries(value as Record<string, number>) : [];
  };
  return <div className="space-y-4">
    <div className="flex justify-end"><button onClick={() => void refresh()} disabled={loading} className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50">{loading ? "Actualizando…" : "Actualizar"}</button></div>
    {error && <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">{error}</p>}
    {data && <>
      <div className={`rounded-lg p-3 text-sm ${data.online ? "bg-emerald-50 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300" : "bg-amber-50 text-amber-800 dark:bg-amber-950 dark:text-amber-300"}`}>{data.online ? `Worker conectado (${data.workers ?? 0})` : "Worker no responde"}</div>
      <div className="grid gap-3 sm:grid-cols-4">
        <Metric label="En ejecución" value={count("active_count")} />
        <Metric label="Pendientes / reservadas" value={count("queued_count")} />
        <Metric label="Programadas" value={count("scheduled_count")} />
        <Metric label="Concurrencia" value={count("concurrency")} />
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        <TaskList title="Ahora mismo" entries={taskGroups("active")} empty="Nada ejecutándose" />
        <TaskList title="Pendientes / en cola" entries={taskGroups("queued")} empty="No hay tareas reservadas" />
        <TaskList title="Programadas" entries={taskGroups("scheduled")} empty="No hay tareas programadas" />
      </div>
      <p className="text-xs text-neutral-500">{String(data.note ?? "")}</p>
    </>}
  </div>;
}

function Metric({ label, value }: { label: string; value: number }) {
  return <div className="rounded-xl border border-neutral-200 bg-white p-4 dark:border-neutral-800 dark:bg-neutral-900"><div className="text-2xl font-semibold">{value}</div><div className="text-xs text-neutral-500">{label}</div></div>;
}

function TaskList({ title, entries, empty }: { title: string; entries: [string, number][]; empty: string }) {
  return <section className="rounded-xl border border-neutral-200 bg-white p-4 dark:border-neutral-800 dark:bg-neutral-900"><h2 className="mb-3 font-medium">{title}</h2>{entries.length ? <ul className="space-y-2 text-sm">{entries.map(([task, count]) => <li key={task} className="flex justify-between gap-3"><span className="truncate">{task}</span><span className="font-semibold">{count}</span></li>)}</ul> : <p className="text-sm text-neutral-500">{empty}</p>}</section>;
}

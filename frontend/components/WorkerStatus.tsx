"use client";

import { useState } from "react";
import { API_BASE_URL } from "@/lib/api";

export function WorkerStatus() {
  const [key, setKey] = useState("");
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  async function refresh() {
    setLoading(true); setError(null);
    try {
      const res = await fetch(`${API_BASE_URL}/internal/worker-status`, { headers: { "X-Internal-Key": key }, cache: "no-store" });
      if (!res.ok) throw new Error(`API ${res.status}`);
      setData(await res.json());
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setLoading(false); }
  }
  return <div className="space-y-4">
    <div className="flex gap-2"><input type="password" value={key} onChange={(e) => setKey(e.target.value)} placeholder="INTERNAL_API_KEY" className="min-w-0 flex-1 rounded-lg border border-neutral-300 bg-white px-3 py-2 dark:border-neutral-700 dark:bg-neutral-900" /><button onClick={() => void refresh()} disabled={!key || loading} className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50">{loading ? "Consultando…" : "Consultar"}</button></div>
    {error && <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">{error}</p>}
    {data && <><div className={`rounded-lg p-3 text-sm ${data.online ? "bg-emerald-50 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300" : "bg-amber-50 text-amber-800 dark:bg-amber-950 dark:text-amber-300"}`}>{data.online ? "Worker conectado" : "Worker no responde"}</div><pre className="max-h-[32rem] overflow-auto rounded-xl bg-neutral-950 p-4 text-xs text-emerald-300">{JSON.stringify(data, null, 2)}</pre></>}
  </div>;
}

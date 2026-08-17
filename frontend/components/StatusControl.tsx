"use client";

import { useState } from "react";
import { API_BASE_URL, type ListingStatus } from "@/lib/api";

const statuses: ListingStatus[] = ["ACTIVE", "STALE", "REMOVED", "SOLD"];

export function StatusControl({ id, initial }: { id: number; initial: ListingStatus }) {
  const [status, setStatus] = useState(initial);
  const [saving, setSaving] = useState(false);
  async function change(next: ListingStatus) {
    setSaving(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/listings/${id}/status`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status: next }) });
      if (!response.ok) throw new Error("No se pudo cambiar el estado");
      setStatus(next);
    } finally { setSaving(false); }
  }
  return <label className="flex items-center gap-2 text-sm"><span className="text-neutral-500">Estado</span><select value={status} disabled={saving} onChange={(e) => void change(e.target.value as ListingStatus)} className="rounded-lg border border-neutral-300 bg-white px-3 py-2 dark:border-neutral-700 dark:bg-neutral-800">{statuses.map((item) => <option key={item}>{item}</option>)}</select></label>;
}

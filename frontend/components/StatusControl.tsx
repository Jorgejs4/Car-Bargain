"use client";

import { useState } from "react";
import { updateListingStatus, type ListingStatus } from "@/lib/api";

const labels: Record<ListingStatus, string> = {
  ACTIVE: "Activo",
  STALE: "Pendiente / antiguo",
  SOLD: "Vendido",
  REMOVED: "Retirado",
};

export function StatusControl({ listingId, currentStatus }: { listingId: number; currentStatus: ListingStatus }) {
  const [status, setStatus] = useState(currentStatus);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  async function changeStatus(next: ListingStatus) {
    if (next === status || !window.confirm(`¿Cambiar el estado a «${labels[next]}»?`)) return;
    setSaving(true);
    setMessage("");
    try {
      await updateListingStatus(listingId, next);
      setStatus(next);
      setMessage("Estado actualizado");
    } catch {
      setMessage("No se pudo actualizar el estado");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg border border-neutral-200 p-3 dark:border-neutral-800">
      <span className="text-sm font-medium">Estado manual:</span>
      <select
        value={status}
        disabled={saving}
        onChange={(event) => void changeStatus(event.target.value as ListingStatus)}
        className="rounded-md border border-neutral-300 bg-white px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-900"
      >
        {Object.entries(labels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </select>
      {message && <span className="text-xs text-neutral-500">{message}</span>}
    </div>
  );
}

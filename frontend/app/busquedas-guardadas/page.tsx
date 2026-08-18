"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { deleteSavedSearch, fetchSavedSearches, type SavedSearchItem } from "@/lib/api";

function searchHref(filters: SavedSearchItem["filters"]): string {
  const query = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== "" && value !== false && value != null) query.set(key, String(value));
  });
  return query.toString() ? `/?${query.toString()}` : "/";
}

export default function SavedSearchesPage() {
  const [searches, setSearches] = useState<SavedSearchItem[]>([]);

  function reload() {
    fetchSavedSearches().then(setSearches).catch(() => setSearches([]));
  }

  useEffect(reload, []);

  async function remove(id: number) {
    await deleteSavedSearch(id);
    setSearches((current) => current.filter((item) => item.id !== id));
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6 px-4 py-8">
      <div>
        <h1 className="text-2xl font-bold">Búsquedas guardadas</h1>
        <p className="text-sm text-neutral-500">Accede rápidamente a tus filtros habituales.</p>
      </div>
      {searches.length === 0 ? <p className="rounded-xl border border-dashed p-8 text-center text-neutral-500">No tienes búsquedas guardadas.</p> : (
        <div className="space-y-3">
          {searches.map((search) => (
            <div key={search.id} className="flex items-center justify-between gap-4 rounded-xl border p-4 dark:border-neutral-800">
              <div>
                <h2 className="font-semibold">{search.name}</h2>
                <p className="text-xs text-neutral-500">Actualizada {new Date(search.updated_at).toLocaleString("es-ES")}</p>
              </div>
              <div className="flex gap-2">
                <Link href={searchHref(search.filters)} className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700">Abrir</Link>
                <button type="button" onClick={() => remove(search.id)} className="rounded-lg border border-red-300 px-3 py-1.5 text-sm text-red-700 hover:bg-red-50 dark:border-red-800 dark:text-red-300">Eliminar</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

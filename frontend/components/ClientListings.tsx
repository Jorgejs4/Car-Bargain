"use client";

import { useEffect, useState } from "react";
import { fetchListings, type ListingFilters, type ListingListItem } from "@/lib/api";
import { ListingCard } from "@/components/ListingCard";

export function ClientListings({ filters }: { filters: ListingFilters }) {
  const [items, setItems] = useState<ListingListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    fetchListings(filters)
      .then((data) => setItems(data.items))
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [filters]);

  if (loading) return <p className="rounded-xl border p-8 text-center">Cargando ofertas…</p>;
  if (error) return <p className="rounded-xl border border-red-300 p-8 text-center text-red-700">No se pudieron cargar las ofertas.</p>;
  if (!items.length) return <p className="rounded-xl border border-dashed p-8 text-center text-neutral-500">No hay anuncios que coincidan con los filtros.</p>;

  return <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">{items.map((item) => <ListingCard key={item.id} listing={item} />)}</div>;
}

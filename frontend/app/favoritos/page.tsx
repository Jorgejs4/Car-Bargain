"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { fetchFavorites, fetchListingDetail, type ListingDetail } from "@/lib/api";
import { ListingCard } from "@/components/ListingCard";

export default function FavoritosPage() {
  const [items, setItems] = useState<ListingDetail[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchFavorites()
      .then((favorites) => Promise.all(favorites.map((item) => fetchListingDetail(item.listing_id))))
      .then(setItems)
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="mx-auto max-w-6xl space-y-6 px-4 py-8">
      <div>
        <h1 className="text-2xl font-bold">Ofertas favoritas</h1>
        <p className="text-sm text-neutral-500">Tus anuncios guardados para revisarlos más tarde.</p>
      </div>
      {loading ? <p className="rounded-xl border p-8 text-center">Cargando favoritos…</p> : items.length === 0 ? (
        <div className="rounded-xl border border-dashed p-8 text-center text-neutral-500">
          <p>Aún no tienes ofertas favoritas.</p>
          <Link href="/" className="mt-2 inline-block text-blue-600 hover:underline">Explorar anuncios</Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((item) => <ListingCard key={item.id} listing={item} favorite />)}
        </div>
      )}
    </div>
  );
}

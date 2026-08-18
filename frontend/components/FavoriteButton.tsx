"use client";

import { useEffect, useState } from "react";
import { addFavorite, fetchFavorites, removeFavorite } from "@/lib/api";

export function FavoriteButton({ listingId, initial }: { listingId: number; initial?: boolean }) {
  const [favorite, setFavorite] = useState(initial ?? false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (initial !== undefined) return;
    fetchFavorites().then((items) => setFavorite(items.some((item) => item.listing_id === listingId))).catch(() => {});
  }, [initial, listingId]);

  async function toggle(event: React.MouseEvent<HTMLButtonElement>) {
    event.preventDefault();
    event.stopPropagation();
    setBusy(true);
    try {
      if (favorite) await removeFavorite(listingId);
      else await addFavorite(listingId);
      setFavorite(!favorite);
    } finally {
      setBusy(false);
    }
  }

  return (
    <button
      type="button"
      aria-label={favorite ? "Quitar de favoritos" : "Añadir a favoritos"}
      title={favorite ? "Quitar de favoritos" : "Añadir a favoritos"}
      disabled={busy}
      onClick={toggle}
      className={`rounded-full border px-2.5 py-1.5 text-lg leading-none transition-colors ${favorite ? "border-amber-300 bg-amber-50 text-amber-500" : "border-neutral-300 bg-white text-neutral-400 hover:text-amber-500 dark:border-neutral-700 dark:bg-neutral-900"}`}
    >
      {favorite ? "★" : "☆"}
    </button>
  );
}

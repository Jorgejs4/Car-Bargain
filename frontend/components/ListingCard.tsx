import Link from "next/link";
import type { ListingListItem } from "@/lib/api";
import { DamageBadge, HistoricalBadge, ReviewBadge, StatusBadge } from "@/components/Badge";

function formatPrice(price: number | null, currency: string | null): string {
  if (price == null) return "—";
  const symbol = currency === "EUR" ? "€" : currency ?? "";
  return `${price.toLocaleString("es-ES", { maximumFractionDigits: 0 })} ${symbol}`;
}

export function ListingCard({ listing }: { listing: ListingListItem }) {
  const title =
    listing.title ??
    [listing.brand, listing.model, listing.generation, listing.variant]
      .filter(Boolean)
      .join(" ") ??
    "Sin título";
  const hasDamage =
    (listing.photo_signals?.has_visible_damage as boolean | undefined) ??
    false;
  const analyzedImages = (listing.photo_signals?.analyzed_images as number | undefined) ?? 0;

  return (
    <Link
      href={`/listings/${listing.id}`}
      className="group flex flex-col rounded-xl border border-neutral-200 bg-white p-4 transition-colors hover:border-blue-400 dark:border-neutral-800 dark:bg-neutral-900"
    >
      <div className="flex items-start justify-between gap-2">
        <h3 className="font-semibold leading-snug group-hover:text-blue-600 dark:group-hover:text-blue-400">
          {title}
        </h3>
        <StatusBadge status={listing.status} />
      </div>

      <div className="mt-1 text-sm text-neutral-500 dark:text-neutral-400">
        {listing.year ? `${listing.year} · ` : ""}
        {listing.mileage != null
          ? `${listing.mileage.toLocaleString("es-ES")} km`
          : "km —"}
        {listing.fuel ? ` · ${listing.fuel}` : ""}
        {listing.transmission ? ` · ${listing.transmission}` : ""}
      </div>

      <div className="mt-3 flex items-baseline justify-between">
        <span className="text-xl font-bold">
          {formatPrice(listing.price, listing.currency)}
        </span>
        <span className="text-xs text-neutral-500">{listing.source}</span>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        {listing.is_historical && <HistoricalBadge />}
        {hasDamage && analyzedImages > 0 && <DamageBadge />}
        {listing.needs_review && <ReviewBadge />}
      </div>

      {listing.risk_score != null && (
        <div className="mt-3">
          <div className="flex justify-between text-xs text-neutral-500">
            <span>Riesgo</span>
            <span>{listing.risk_score.toFixed(3)}</span>
          </div>
          <div className="mt-1 h-1.5 rounded-full bg-neutral-200 dark:bg-neutral-700">
            <div
              className="h-1.5 rounded-full bg-blue-600"
              style={{ width: `${Math.min(100, listing.risk_score * 100)}%` }}
            />
          </div>
        </div>
      )}
    </Link>
  );
}

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
  const textSignals = listing.text_signals;
  const snapshotSignals = listing.condition_signals;
  const hasTextProblem = textSignals?.has_problem === true
    || snapshotSignals?.has_problem === true
    || ["has_accident", "has_engine_issue", "has_mechanical_issue", "has_gearbox_issue", "has_paper_issue", "not_running"].some((key) => snapshotSignals?.[key] === true);
  const textProblems = (textSignals?.problem_types as string[] | undefined)
    ?? (snapshotSignals?.problem_types as string[] | undefined)
    ?? [];

  return (
    <Link
      href={`/listings/${listing.id}`}
      className="group flex flex-col rounded-xl border border-neutral-200 bg-white p-4 transition-colors hover:border-blue-400 dark:border-neutral-800 dark:bg-neutral-900"
    >
      <div className="flex items-start justify-between gap-2">
        <h3 className="font-semibold leading-snug group-hover:text-blue-600 dark:group-hover:text-blue-400">
          {hasTextProblem ? "AVERÍA / PROBLEMA DETECTADO · " : ""}{title}
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
        {listing.absolute_margin != null && listing.absolute_margin !== 0 && (
          <span className={`rounded-full px-2 py-0.5 text-xs font-bold ${listing.absolute_margin > 0 ? "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-300" : "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300"}`}>
            {listing.absolute_margin > 0 ? "-" : "+"}{Math.abs(listing.absolute_margin).toLocaleString("es-ES")}€
          </span>
        )}
        {listing.bargain_score != null && listing.bargain_score !== 0 && (
          <span className="text-xs text-neutral-500">
            {(listing.bargain_score * 100).toFixed(0)}%
          </span>
        )}
      </div>

{listing.country && listing.country !== "ES" && listing.total_cost_es != null && (
        <div className="mt-0.5 text-xs">
          {listing.cross_border_margin != null && listing.cross_border_margin > 0 ? (
            <span className="font-medium text-green-600 dark:text-green-400">
              Importar: ahorro {listing.cross_border_margin.toLocaleString("es-ES")}€ (
              {Math.round((listing.cross_border_margin / (listing.predicted_price_es ?? 1)) * 100)}%)
            </span>
          ) : (
            <span className="text-amber-600 dark:text-amber-400">
              {listing.total_cost_es.toLocaleString("es-ES")}€ total en España
            </span>
          )}
        </div>
      )}
      {listing.country && listing.country !== "ES" && listing.total_cost_es == null && (
        <div className="mt-0.5 text-xs text-neutral-400">
          Sin costes de importación calculados
        </div>
      )}
      {listing.absolute_margin == null && listing.bargain_score == null && (
        <div className="mt-1 text-xs text-neutral-400">
          Sin valoración (faltan comparables de confianza)
        </div>
      )}

      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        {hasTextProblem && (
          <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-bold text-red-800 dark:bg-red-950 dark:text-red-300">
            Problema: {textProblems.join(", ") || "revisar texto"}
          </span>
        )}
        {listing.is_historical && <HistoricalBadge />}
        {hasDamage && analyzedImages > 0 && <DamageBadge />}
        {listing.needs_review && <ReviewBadge />}
      </div>
    </Link>
  );
}

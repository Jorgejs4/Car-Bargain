import Link from "next/link";
import type { ListingListItem } from "@/lib/api";
import { DamageBadge, HistoricalBadge, ReviewBadge, StatusBadge } from "@/components/Badge";
import { conditionFindings, hasCosmeticText } from "@/lib/condition";

function formatPrice(price: number | null, currency: string | null): string {
  if (price == null) return "—";
  const symbol = currency === "EUR" ? "€" : currency ?? "";
  return `${price.toLocaleString("es-ES", { maximumFractionDigits: 0 })} ${symbol}`;
}

function preferredImageUrl(url: string): string {
  return url.replace(/\/\d+x\d+\.(?:webp|jpg|jpeg)(?=$|\?)/i, "/1200x900.webp");
}

export function ListingCard({ listing }: { listing: ListingListItem }) {
  const vehicleName = [listing.brand, listing.model]
    .filter(Boolean)
    .join(" ") || listing.title || "Vehículo sin identificar";
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
  const findings = conditionFindings(textSignals, snapshotSignals, listing.photo_signals);
  const hasCosmetic = hasCosmeticText(textSignals) || hasCosmeticText(snapshotSignals)
    || ((listing.photo_signals?.cosmetic_defects as string[] | undefined)?.length ?? 0) > 0;
  const hasConditionEvidence = Boolean(textSignals || snapshotSignals || analyzedImages > 0);
  const conditionLabel = hasTextProblem || hasDamage
    ? "Con averías"
    : hasConditionEvidence
      ? "Sin averías detectadas"
      : "Estado desconocido";
  const estimatedMargin = listing.absolute_margin ?? (
    listing.country !== "ES" ? listing.cross_border_margin : null
  );

  return (
    <Link
      href={`/listings/${listing.id}`}
      className="group flex flex-col rounded-xl border border-neutral-200 bg-white p-4 transition-colors hover:border-blue-400 dark:border-neutral-800 dark:bg-neutral-900"
    >
      {listing.image_url && (
        <img
          src={preferredImageUrl(listing.image_url)}
          alt={vehicleName}
          className="mb-3 aspect-[4/3] w-full rounded-lg object-cover"
          loading="lazy"
        />
      )}
      <div className="flex items-start justify-between gap-2">
        <h3 className="font-semibold leading-snug group-hover:text-blue-600 dark:group-hover:text-blue-400">
          {vehicleName} · {formatPrice(listing.price, listing.currency)} · {conditionLabel}
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

      <div className="mt-3 space-y-1 text-sm">
        <div>
          <span className="font-semibold">Precio: </span>
          {formatPrice(listing.price, listing.currency)}
        </div>
        {listing.country && listing.country !== "ES" && listing.total_cost_es != null && (
          <div>
            <span className="font-semibold">Total en España: </span>
            {formatPrice(listing.total_cost_es, "EUR")}
          </div>
        )}
        {estimatedMargin != null && (
          <div className={estimatedMargin >= 0 ? "font-semibold text-green-700 dark:text-green-400" : "font-semibold text-red-700 dark:text-red-400"}>
            Margen absoluto estimado: {estimatedMargin >= 0 ? "+" : ""}{formatPrice(estimatedMargin, "EUR")}
          </div>
        )}
      </div>

      {listing.country && listing.country !== "ES" && listing.total_cost_es == null && (
        <div className="mt-0.5 text-xs text-neutral-400">
          Sin costes de importación calculados
        </div>
      )}
      {estimatedMargin == null && listing.bargain_score == null && (
        <div className="mt-1 text-xs text-neutral-400">
          Sin valoración (faltan comparables de confianza)
        </div>
      )}

      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        {findings.length > 0 && (
          <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-bold text-red-800 dark:bg-red-950 dark:text-red-300">
            Avería: {findings.map((finding) => `${finding.label} (${finding.source})`).join("; ")}
          </span>
        )}
        {hasCosmetic && findings.length === 0 && (
          <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-bold text-amber-800 dark:bg-amber-950 dark:text-amber-300">
            Posible daño estético
          </span>
        )}
        {listing.is_historical && <HistoricalBadge />}
        {hasDamage && analyzedImages > 0 && <DamageBadge />}
        {listing.needs_review && <ReviewBadge />}
      </div>
    </Link>
  );
}

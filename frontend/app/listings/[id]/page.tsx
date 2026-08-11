import Link from "next/link";
import { notFound } from "next/navigation";
import { fetchListingDetail } from "@/lib/api";
import { DamageBadge, ReviewBadge, StatusBadge } from "@/components/Badge";
import { PriceChart } from "@/components/PriceChart";

function fmtMoney(v: number | null, currency: string | null): string {
  if (v == null) return "—";
  const symbol = currency === "EUR" ? "€" : currency ?? "";
  return `${v.toLocaleString("es-ES", { maximumFractionDigits: 0 })} ${symbol}`;
}

function fmtKm(v: number | null): string {
  return v == null ? "—" : `${v.toLocaleString("es-ES")} km`;
}

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleString("es-ES", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

const EVENT_LABELS: Record<string, string> = {
  LISTED: "Publicado",
  PRICE_CHANGED: "Cambio de precio",
  DESCRIPTION_CHANGED: "Cambio de descripción",
  MILEAGE_CHANGED: "Cambio de kilometraje",
  STATUS_CHANGED: "Cambio de estado",
  REMOVED: "Eliminado",
  REAPPEARED: "Reaparecido",
};

function SignalRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-4 border-b border-neutral-100 py-1.5 text-sm last:border-0 dark:border-neutral-800">
      <span className="text-neutral-500">{label}</span>
      <span className="font-medium">{value}</span>
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-xl border border-neutral-200 bg-white p-5 dark:border-neutral-800 dark:bg-neutral-900">
      <h2 className="mb-3 text-sm font-bold uppercase tracking-wide text-neutral-500">
        {title}
      </h2>
      {children}
    </section>
  );
}

export const dynamic = "force-dynamic";

export default async function ListingPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  let listing;
  try {
    listing = await fetchListingDetail(Number(id));
  } catch (e) {
    if (e instanceof Error && e.message.includes("404")) notFound();
    throw e;
  }
  if (!listing) notFound();

  const vehicle = listing.vehicle;
  const title =
    listing.title ??
    [vehicle?.brand, vehicle?.model, vehicle?.generation, vehicle?.variant]
      .filter(Boolean)
      .join(" ") ??
    `Anuncio ${listing.id}`;
  const hasDamage =
    (listing.photo_signals?.has_visible_damage as boolean | undefined) ?? false;
  const damageTypes = (listing.photo_signals?.damage_types as string[] | undefined) ?? [];
  const cvProb = listing.photo_signals?.photo_damage_prob as number | undefined;
  const analyzedImages = listing.photo_signals?.analyzed_images as number | undefined;
  const accFree = listing.condition_signals?.accident_free as boolean | undefined;
  const accConf = listing.condition_signals?.confidence as number | undefined;
  const keywords = (listing.condition_signals?.keywords_found as string[] | undefined) ?? [];

  return (
    <div className="mx-auto max-w-6xl space-y-6 px-4 py-8">
      <Link href="/" className="text-sm text-blue-600 hover:underline dark:text-blue-400">
        ← Volver a anuncios
      </Link>

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">{title}</h1>
          <p className="text-sm text-neutral-500 dark:text-neutral-400">
            {listing.brand && listing.model ? `${listing.brand} ${listing.model}` : "Vehículo"}
            {vehicle?.year ? ` · ${vehicle.year}` : ""}
            {listing.country ? ` · ${listing.country}` : ""} · {listing.source}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge status={listing.status} />
          {hasDamage && <DamageBadge />}
          {listing.needs_review && <ReviewBadge />}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 rounded-xl border border-neutral-200 bg-white p-5 md:grid-cols-4 dark:border-neutral-800 dark:bg-neutral-900">
        <div>
          <p className="text-xs text-neutral-500">Precio actual</p>
          <p className="text-2xl font-bold text-blue-600 dark:text-blue-400">
            {fmtMoney(listing.price, listing.currency)}
          </p>
        </div>
        <div>
          <p className="text-xs text-neutral-500">Kilometraje</p>
          <p className="text-xl font-semibold">{fmtKm(listing.mileage)}</p>
        </div>
        <div>
          <p className="text-xs text-neutral-500">Riesgo</p>
          <p className="text-xl font-semibold">
            {listing.risk_score != null ? listing.risk_score.toFixed(3) : "—"}
          </p>
        </div>
        <div>
          <p className="text-xs text-neutral-500">Primera vez visto</p>
          <p className="text-sm font-semibold">{fmtDate(listing.first_seen_at)}</p>
        </div>
      </div>

      {listing.url && (
        <a
          href={listing.url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-block rounded-lg border border-blue-300 px-4 py-2 text-sm font-medium text-blue-600 hover:bg-blue-50 dark:border-blue-800 dark:text-blue-400 dark:hover:bg-blue-950"
        >
          Ver anuncio original ↗
        </a>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Section title="Vehículo">
          {vehicle ? (
            <div className="space-y-0.5">
              <SignalRow label="Marca" value={vehicle.brand} />
              <SignalRow label="Modelo" value={vehicle.model ?? "—"} />
              <SignalRow label="Generación" value={vehicle.generation ?? "—"} />
              <SignalRow label="Variante" value={vehicle.variant ?? "—"} />
              <SignalRow label="Año" value={vehicle.year ?? "—"} />
              <SignalRow label="Matriculación" value={vehicle.registration_date ?? "—"} />
              <SignalRow label="Combustible" value={vehicle.fuel ?? "—"} />
              <SignalRow label="Cambio" value={vehicle.transmission ?? "—"} />
              <SignalRow label="Tracción" value={vehicle.drivetrain ?? "—"} />
              <SignalRow label="Potencia" value={vehicle.power_kw != null ? `${vehicle.power_kw} kW` : "—"} />
              <SignalRow label="Cilindrada" value={vehicle.engine_cc != null ? `${vehicle.engine_cc} cc` : "—"} />
              <SignalRow label="Emisiones" value={vehicle.co2_g_km != null ? `${vehicle.co2_g_km} g/km` : "—"} />
              <SignalRow label="Carrocería" value={vehicle.body_type ?? "—"} />
            </div>
          ) : (
            <p className="text-sm text-neutral-500">Sin datos de vehículo.</p>
          )}
        </Section>

        <Section title="Detección de daños (CV)">
          {listing.photo_signals ? (
            <div className="space-y-0.5">
              <SignalRow
                label="Probabilidad de daño"
                value={cvProb != null ? `${(cvProb * 100).toFixed(0)}%` : "—"}
              />
              <SignalRow label="Daño visible" value={hasDamage ? "Sí" : "No"} />
              <SignalRow
                label="Tipos de daño"
                value={damageTypes.length ? damageTypes.join(", ") : "Ninguno"}
              />
              <SignalRow label="Imágenes analizadas" value={analyzedImages ?? "—"} />
            </div>
          ) : (
            <p className="text-sm text-neutral-500">
              Sin análisis de imágenes (CV no disponible o no ejecutado).
            </p>
          )}

          <h3 className="mt-4 mb-2 text-xs font-bold uppercase tracking-wide text-neutral-500">
            Señales de texto
          </h3>
          {listing.condition_signals ? (
            <div className="space-y-0.5">
              <SignalRow
                label="Sin accidentes"
                value={accFree == null ? "Desconocido" : accFree ? "Sí" : "No"}
              />
              <SignalRow
                label="Confianza"
                value={accConf != null ? `${(accConf * 100).toFixed(0)}%` : "—"}
              />
              <SignalRow
                label="Palabras clave"
                value={keywords.length ? keywords.join(", ") : "Ninguna"}
              />
            </div>
          ) : (
            <p className="text-sm text-neutral-500">Sin señales de texto.</p>
          )}
        </Section>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Section title="Historial de precios">
          {listing.snapshots.length > 0 ? (
            <>
              <PriceChart
                points={listing.snapshots.map((s) => ({
                  scraped_at: s.scraped_at,
                  price: s.price,
                  mileage: s.mileage,
                }))}
              />
              <div className="mt-4 max-h-64 space-y-1 overflow-auto text-sm">
                {listing.snapshots
                  .slice()
                  .reverse()
                  .map((s) => (
                    <div
                      key={s.id}
                      className="flex justify-between border-b border-neutral-100 py-1 last:border-0 dark:border-neutral-800"
                    >
                      <span className="text-neutral-500">{fmtDate(s.scraped_at)}</span>
                      <span className="font-medium">{fmtMoney(s.price, s.currency)}</span>
                      <span className="text-neutral-500">{fmtKm(s.mileage)}</span>
                    </div>
                  ))}
              </div>
            </>
          ) : (
            <p className="text-sm text-neutral-500">Sin snapshots registrados.</p>
          )}
        </Section>

        <Section title="Eventos">
          {listing.events.length > 0 ? (
            <ul className="space-y-3">
              {listing.events
                .slice()
                .sort((a, b) => b.event_timestamp.localeCompare(a.event_timestamp))
                .map((ev) => (
                  <li key={ev.id} className="text-sm">
                    <div className="flex items-center justify-between">
                      <span className="font-medium">
                        {EVENT_LABELS[ev.event_type] ?? ev.event_type}
                      </span>
                      <span className="text-xs text-neutral-500">{fmtDate(ev.event_timestamp)}</span>
                    </div>
                    {ev.new_value && (
                      <pre className="mt-1 overflow-x-auto rounded bg-neutral-100 p-2 text-xs dark:bg-neutral-800">
                        {JSON.stringify(ev.new_value, null, 2)}
                      </pre>
                    )}
                  </li>
                ))}
            </ul>
          ) : (
            <p className="text-sm text-neutral-500">Sin eventos registrados.</p>
          )}
        </Section>
      </div>

      <Section title="Análisis por imagen">
        {listing.photo_analyses.length > 0 ? (
          <ul className="space-y-2">
            {listing.photo_analyses.map((a) => (
              <li key={a.id} className="flex items-center justify-between gap-4 text-sm">
                <span className="truncate text-neutral-500">{a.image_url}</span>
                <span className="flex shrink-0 items-center gap-2">
                  <span className="font-medium">{a.label ?? "—"}</span>
                  {a.probability != null && (
                    <span className="text-xs text-neutral-500">
                      {(a.probability * 100).toFixed(0)}%
                    </span>
                  )}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-neutral-500">Sin análisis por imagen.</p>
        )}
      </Section>
    </div>
  );
}

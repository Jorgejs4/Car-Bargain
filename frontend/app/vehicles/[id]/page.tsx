import Link from "next/link";
import { notFound } from "next/navigation";
import {
  fetchVehicleDetail,
  fetchVehicleHistory,
  fetchVehicleMarket,
} from "@/lib/api";
import { StatusBadge } from "@/components/Badge";
import { PriceChart } from "@/components/PriceChart";

function fmtMoney(v: number | null, currency: string | null): string {
  if (v == null) return "—";
  const symbol = currency === "EUR" ? "€" : currency ?? "";
  return `${v.toLocaleString("es-ES", { maximumFractionDigits: 0 })} ${symbol}`;
}

function fmtKm(v: number | null): string {
  return v == null ? "—" : `${v.toLocaleString("es-ES")} km`;
}

function MarketBox({
  label,
  value,
  highlight = false,
}: {
  label: string;
  value: React.ReactNode;
  highlight?: boolean;
}) {
  return (
    <div
      className={`rounded-xl border p-4 ${
        highlight
          ? "border-blue-400 bg-blue-50 dark:border-blue-800 dark:bg-blue-950"
          : "border-neutral-200 bg-white dark:border-neutral-800 dark:bg-neutral-900"
      }`}
    >
      <p className="text-xs text-neutral-500">{label}</p>
      <p className="mt-1 text-xl font-bold">{value}</p>
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
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

export default async function VehiclePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const vehicleId = Number(id);

  let vehicle;
  try {
    vehicle = await fetchVehicleDetail(vehicleId);
  } catch (e) {
    if (e instanceof Error && e.message.includes("404")) notFound();
    throw e;
  }
  if (!vehicle) notFound();

  const [history, market] = await Promise.all([
    fetchVehicleHistory(vehicleId),
    fetchVehicleMarket(vehicleId),
  ]);

  const modelLabel = [vehicle.model, vehicle.generation, vehicle.variant]
    .filter(Boolean)
    .join(" ");

  return (
    <div className="mx-auto max-w-6xl space-y-6 px-4 py-8">
      <Link href="/" className="text-sm text-blue-600 hover:underline dark:text-blue-400">
        ← Volver a anuncios
      </Link>

      <div>
        <h1 className="text-2xl font-bold">
          {vehicle.brand} {modelLabel}
        </h1>
        <p className="text-sm text-neutral-500 dark:text-neutral-400">
          {vehicle.year ? `${vehicle.year} · ` : ""}
          {vehicle.fuel ? `${vehicle.fuel} · ` : ""}
          {vehicle.transmission ? `${vehicle.transmission} · ` : ""}
          {vehicle.power_kw != null ? `${vehicle.power_kw} kW` : ""}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <MarketBox label="Anuncios activos" value={vehicle.listings.length} />
        <MarketBox
          label="Precio mediano"
          value={fmtMoney(market.p50, market.currency)}
          highlight
        />
        <MarketBox label="Precio medio" value={fmtMoney(market.mean_price, market.currency)} />
        <MarketBox label="Mínimo" value={fmtMoney(market.min_price, market.currency)} />
      </div>

      <Section title="Datos del vehículo">
        <div className="space-y-0.5">
          <Row label="Año" value={vehicle.year ?? "—"} />
          <Row label="Matriculación" value={vehicle.registration_date ?? "—"} />
          <Row label="Combustible" value={vehicle.fuel ?? "—"} />
          <Row label="Cambio" value={vehicle.transmission ?? "—"} />
          <Row label="Tracción" value={vehicle.drivetrain ?? "—"} />
          <Row label="Potencia" value={vehicle.power_kw != null ? `${vehicle.power_kw} kW` : "—"} />
          <Row label="Cilindrada" value={vehicle.engine_cc != null ? `${vehicle.engine_cc} cc` : "—"} />
          <Row label="Emisiones" value={vehicle.co2_g_km != null ? `${vehicle.co2_g_km} g/km` : "—"} />
          <Row label="Carrocería" value={vehicle.body_type ?? "—"} />
        </div>
      </Section>

      {market.count > 0 && (
        <Section title="Distribución de mercado">
          <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
            <MarketBox label="P10" value={fmtMoney(market.p10, market.currency)} />
            <MarketBox label="P50" value={fmtMoney(market.p50, market.currency)} highlight />
            <MarketBox label="P90" value={fmtMoney(market.p90, market.currency)} />
            <MarketBox label="Máximo" value={fmtMoney(market.max_price, market.currency)} />
            <MarketBox label="Muestra" value={market.count} />
          </div>
        </Section>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Section title="Anuncios">
          {vehicle.listings.length > 0 ? (
            <ul className="space-y-2">
              {vehicle.listings.map((l) => (
                <li key={l.id}>
                  <Link
                    href={`/listings/${l.id}`}
                    className="flex items-center justify-between rounded-lg border border-neutral-200 p-3 transition-colors hover:border-blue-400 dark:border-neutral-800"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold">
                        {l.title ?? `${l.brand} ${l.model}`}
                      </p>
                      <p className="text-xs text-neutral-500">
                        {l.source} · {l.mileage != null ? fmtKm(l.mileage) : "km —"}
                      </p>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      <span className="font-bold">{fmtMoney(l.price, l.currency)}</span>
                      <StatusBadge status={l.status} />
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-neutral-500">Sin anuncios activos.</p>
          )}
        </Section>

        <Section title="Histórico por anuncio">
          {history.length > 0 ? (
            <ul className="space-y-4">
              {history.map((entry) => (
                <li key={entry.listing_id}>
                  <Link
                    href={`/listings/${entry.listing_id}`}
                    className="mb-1 inline-flex items-center gap-2 text-xs text-neutral-500 hover:text-blue-600 dark:hover:text-blue-400"
                  >
                    <span className="font-medium text-neutral-700 dark:text-neutral-300">
                      {entry.source} {entry.source_listing_id}
                    </span>
                    · ver anuncio →
                  </Link>
                  <PriceChart
                    points={entry.snapshots.map((s) => ({
                      scraped_at: s.scraped_at,
                      price: s.price,
                      mileage: s.mileage,
                    }))}
                  />
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-neutral-500">Sin histórico registrado.</p>
          )}
        </Section>
      </div>
    </div>
  );
}

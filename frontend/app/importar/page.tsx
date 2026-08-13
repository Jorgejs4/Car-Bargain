import Link from "next/link";
import { fetchListings, type ListingFilters } from "@/lib/api";
import { ListingCard } from "@/components/ListingCard";

function num(v: string | string[] | undefined): number | undefined {
  if (typeof v !== "string" || v === "") return undefined;
  const n = Number(v);
  return Number.isFinite(n) ? n : undefined;
}

function parseFilters(searchParams: Record<string, string | string[] | undefined>): ListingFilters {
  const sortParam = typeof searchParams.sort === "string" ? searchParams.sort : "cross_border-desc";
  const [sort_by, sort_order] = sortParam.includes("-") ? sortParam.split("-", 2) : ["cross_border", "desc"];
  return {
    page: num(searchParams.page) ?? 1,
    brand: typeof searchParams.brand === "string" ? searchParams.brand || undefined : undefined,
    model: typeof searchParams.model === "string" ? searchParams.model || undefined : undefined,
    price_min: num(searchParams.price_min),
    price_max: num(searchParams.price_max),
    mileage_max: num(searchParams.mileage_max),
    year_min: num(searchParams.year_min),
    fuel: typeof searchParams.fuel === "string" ? searchParams.fuel || undefined : undefined,
    transmission:
      typeof searchParams.transmission === "string" ? searchParams.transmission || undefined : undefined,
    region: "EU",
    sort_by,
    sort_order,
    min_cross_border_margin: 0,
    only_clean: true,
    needs_review: searchParams.needs_review === "true" ? true : undefined,
  };
}

function buildPageUrl(
  page: number,
  searchParams: Record<string, string | string[] | undefined>
): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(searchParams)) {
    if (key === "page" || typeof value !== "string") continue;
    if (value) params.set(key, value);
  }
  params.set("page", String(page));
  return `/importar?${params.toString()}`;
}

export const dynamic = "force-dynamic";

export default async function ImportarPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const resolved = await searchParams;
  const filters = parseFilters(resolved);
  const data = await fetchListings(filters);

  return (
    <div className="mx-auto max-w-6xl space-y-6 px-4 py-8">
      <div>
        <h1 className="text-2xl font-bold">Chollos de importación</h1>
        <p className="text-sm text-neutral-500 dark:text-neutral-400">
          Unidades europeas (no españolas) con valor en España por encima del
          precio total de traerlas (compra + importación). Solo con comparables
          de confianza en el mercado español.
        </p>
        <p className="mt-1 text-sm text-neutral-500 dark:text-neutral-400">
          {data.total} anuncios · ordenados por mejor margen de importación · página{" "}
          {data.page} de {Math.max(1, data.pages)}
        </p>
      </div>

      {data.items.length === 0 ? (
        <p className="rounded-xl border border-dashed border-neutral-300 p-8 text-center text-neutral-500 dark:border-neutral-700">
          No hay chollos de importación ahora mismo. Cuando se scrapeen anuncios
          europeos con buen margen aparecerán aquí.
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.items.map((listing) => (
            <ListingCard key={listing.id} listing={listing} />
          ))}
        </div>
      )}

      {data.pages > 1 && (
        <nav className="flex items-center justify-center gap-2">
          {data.page > 1 && (
            <Link
              href={buildPageUrl(data.page - 1, resolved)}
              className="rounded-lg border border-neutral-300 px-3 py-1.5 text-sm hover:bg-neutral-100 dark:border-neutral-700 dark:hover:bg-neutral-800"
            >
              ← Anterior
            </Link>
          )}
          <span className="px-2 text-sm text-neutral-500">
            {data.page} / {data.pages}
          </span>
          {data.page < data.pages && (
            <Link
              href={buildPageUrl(data.page + 1, resolved)}
              className="rounded-lg border border-neutral-300 px-3 py-1.5 text-sm hover:bg-neutral-100 dark:border-neutral-700 dark:hover:bg-neutral-800"
            >
              Siguiente →
            </Link>
          )}
        </nav>
      )}
    </div>
  );
}

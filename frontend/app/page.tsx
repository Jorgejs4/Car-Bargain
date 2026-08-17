import Link from "next/link";
import { fetchListings, type ListingFilters } from "@/lib/api";
import { ListingCard } from "@/components/ListingCard";
import FilterForm from "@/components/FilterForm";

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
    seller_type:
      typeof searchParams.seller_type === "string" ? searchParams.seller_type || undefined : undefined,
    region:
      typeof searchParams.region === "string" ? searchParams.region || undefined : undefined,
    sort_by: sort_by,
    sort_order: sort_order,
    min_bargain_score:
      searchParams.min_bargain_score === undefined ? 0 : num(searchParams.min_bargain_score),
    min_absolute_margin:
      num(searchParams.min_absolute_margin),
    only_clean: true,
    needs_review:
      searchParams.needs_review === "true" ? true : undefined,
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
  return `/?${params.toString()}`;
}

export const dynamic = "force-dynamic";

export default async function Home({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const resolved = await searchParams;
  const filters = parseFilters(resolved);
  let data;
  let apiUnavailable = false;
  let apiError = "";
  try {
    data = await fetchListings(filters);
  } catch (error) {
    apiUnavailable = true;
    apiError = error instanceof Error ? error.message : String(error);
    data = { items: [], total: 0, page: filters.page ?? 1, pages: 0 };
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6 px-4 py-8">
      <div>
        <h1 className="text-2xl font-bold">Gangas detectadas</h1>
        <p className="text-sm text-neutral-500 dark:text-neutral-400">
          {data.total} anuncios · ordenados por mejor oportunidad · página {data.page} de {Math.max(1, data.pages)}
        </p>
      </div>

      <FilterForm />

      {apiUnavailable && (
        <p className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900">
          La API está temporalmente no disponible. La página se ha cargado, pero no se pueden mostrar ofertas ahora mismo.
          {apiError && <span className="mt-1 block text-xs">{apiError}</span>}
        </p>
      )}

      {data.items.length === 0 ? (
        <p className="rounded-xl border border-dashed border-neutral-300 p-8 text-center text-neutral-500 dark:border-neutral-700">
          No hay anuncios que coincidan con los filtros.
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

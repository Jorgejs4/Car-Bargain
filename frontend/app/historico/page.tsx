import Link from "next/link";
import { fetchHistoricalListings, type ListingFilters } from "@/lib/api";
import { ListingCard } from "@/components/ListingCard";

export const dynamic = "force-dynamic";

export default async function HistoricoPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const resolved = await searchParams;
  const page = Math.max(1, Number(resolved.page) || 1);
  const filters: ListingFilters = { page, page_size: 24 };
  const data = await fetchHistoricalListings(filters);

  function buildPageUrl(nextPage: number): string {
    const params = new URLSearchParams();
    params.set("page", String(nextPage));
    return `/historico?${params.toString()}`;
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6 px-4 py-8">
      <div>
        <h1 className="text-2xl font-bold">Histórico de ofertas</h1>
        <p className="text-sm text-neutral-500 dark:text-neutral-400">
          Todas las ofertas vistas (activas, caducadas y archivadas) ·{" "}
          {data.total} anuncios · página {data.page} de{" "}
          {Math.max(1, data.pages)}
        </p>
      </div>

      {data.items.length === 0 ? (
        <p className="rounded-xl border border-dashed border-neutral-300 p-8 text-center text-neutral-500 dark:border-neutral-700">
          No hay ofertas en el histórico.
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
              href={buildPageUrl(data.page - 1)}
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
              href={buildPageUrl(data.page + 1)}
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
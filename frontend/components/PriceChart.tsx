interface PricePoint {
  scraped_at: string;
  price: number | null;
  mileage: number | null;
}

function toLocal(iso: string): string {
  return new Date(iso).toLocaleDateString("es-ES", {
    day: "2-digit",
    month: "short",
  });
}

export function PriceChart({ points }: { points: PricePoint[] }) {
  const prices = points
    .filter((p): p is PricePoint & { price: number } => p.price != null)
    .map((p) => p.price);

  if (prices.length === 0) {
    return (
      <p className="text-sm text-neutral-500 dark:text-neutral-400">
        Sin precios registrados.
      </p>
    );
  }

  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const range = max - min || 1;

  return (
    <div className="flex h-40 items-end gap-1">
      {points.map((p, i) => {
        const height =
          p.price == null ? 4 : 8 + ((p.price - min) / range) * 92;
        const first = points[0];
        const last = points[points.length - 1];
        const isExtreme =
          (first != null && p.scraped_at === first.scraped_at) ||
          (last != null && p.scraped_at === last.scraped_at);
        return (
          <div
            key={i}
            className={`flex-1 rounded-t transition-colors ${
              isExtreme ? "bg-blue-600" : "bg-blue-400/70"
            }`}
            style={{ height: `${height}%` }}
            title={`${toLocal(p.scraped_at)}: ${
              p.price != null ? `${p.price} €` : "—"
            } (${p.mileage != null ? `${p.mileage.toLocaleString("es-ES")} km` : "—"})`}
          />
        );
      })}
    </div>
  );
}

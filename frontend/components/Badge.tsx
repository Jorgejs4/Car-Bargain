import type { ListingStatus } from "@/lib/api";

const STATUS_STYLES: Record<ListingStatus, string> = {
  ACTIVE: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300",
  STALE: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300",
  REMOVED: "bg-neutral-200 text-neutral-700 dark:bg-neutral-800 dark:text-neutral-300",
  SOLD: "bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-300",
};

export function StatusBadge({ status }: { status: ListingStatus }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[status]}`}
    >
      {status}
    </span>
  );
}

export function DamageBadge() {
  return (
    <span className="inline-flex items-center rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-800 dark:bg-red-950 dark:text-red-300">
      Posible daño
    </span>
  );
}

export function ReviewBadge() {
  return (
    <span className="inline-flex items-center rounded-full bg-orange-100 px-2 py-0.5 text-xs font-medium text-orange-800 dark:bg-orange-950 dark:text-orange-300">
      Revisar
    </span>
  );
}

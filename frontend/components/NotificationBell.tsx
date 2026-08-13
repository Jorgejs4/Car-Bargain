"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { fetchNotifications, markNotificationRead, type NotificationItem } from "@/lib/api";

function fmtPrice(p: unknown): string {
  if (typeof p !== "number") return "—";
  return `${p.toLocaleString("es-ES")}€`;
}

export function NotificationBell() {
  const router = useRouter();
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const list = await fetchNotifications(true);
      setItems(list);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const initial = window.setTimeout(() => { void load(); }, 0);
    const t = setInterval(load, 60000);
    return () => {
      window.clearTimeout(initial);
      clearInterval(t);
    };
  }, [load]);

  const unread = items.length;

  async function openItem(n: NotificationItem) {
    if (n.status === "pending") {
      try {
        await markNotificationRead(n.id);
        setItems((prev) => prev.filter((x) => x.id !== n.id));
      } catch {
        // ignore
      }
    }
    router.push(`/listings/${n.listing_id}`);
    setOpen(false);
  }

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="relative rounded-full p-2 text-neutral-600 hover:bg-neutral-100 dark:text-neutral-400 dark:hover:bg-neutral-800"
        aria-label="Notificaciones"
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M6 8a6 6 0 1 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
          <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
        </svg>
        {unread > 0 && (
          <span className="absolute right-0 top-0 inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-red-600 px-1 text-[10px] font-bold text-white">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 z-20 mt-2 w-80 max-w-[calc(100vw-2rem)] rounded-xl border border-neutral-200 bg-white shadow-xl dark:border-neutral-800 dark:bg-neutral-900">
          <div className="flex items-center justify-between border-b border-neutral-100 px-4 py-2 dark:border-neutral-800">
            <span className="text-sm font-semibold">Notificaciones</span>
            <Link
              href="/preferencias"
              onClick={() => setOpen(false)}
              className="text-xs text-blue-600 hover:underline dark:text-blue-400"
            >
              Preferencias
            </Link>
          </div>
          {loading && items.length === 0 ? (
            <div className="p-4 text-sm text-neutral-500">Cargando…</div>
          ) : items.length === 0 ? (
            <div className="p-4 text-sm text-neutral-500">No hay gangas nuevas.</div>
          ) : (
            <ul className="max-h-96 divide-y divide-neutral-100 overflow-auto dark:divide-neutral-800">
              {items.map((n) => (
                <li
                  key={n.id}
                  className="cursor-pointer p-3 hover:bg-neutral-50 dark:hover:bg-neutral-800"
                  onClick={() => openItem(n)}
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="text-sm font-medium">{n.title}</span>
                    <span className="shrink-0 text-xs text-green-600 dark:text-green-400">
                      {fmtPrice((n.body as Record<string, unknown> | null)?.absolute_margin)}
                    </span>
                  </div>
                  <div className="mt-1 text-xs text-neutral-500">
                    {fmtPrice((n.body as Record<string, unknown> | null)?.price)} ·{" "}
                    {(n.body as Record<string, unknown> | null)?.country as string}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { evaluateAlerts, fetchPreferences, savePreferences, type AlertPreferences } from "@/lib/api";

function numOrNull(v: string): number | null {
  if (v === "" || v === undefined) return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

const EMPTY: AlertPreferences = {
  max_purchase_price: null,
  max_total_cost: null,
  min_profit: null,
  min_roi: null,
  min_bargain_score: null,
  max_risk_score: null,
  brands: [],
  fuel: null,
  transmission: null,
  max_mileage: null,
  year_min: null,
  region: null,
  notify_web: true,
  notify_email: false,
};

export default function PreferenciasPage() {
  const [prefs, setPrefs] = useState<AlertPreferences>(EMPTY);
  const [brandsInput, setBrandsInput] = useState("");
  const [saving, setSaving] = useState(false);
  const [evaluating, setEvaluating] = useState(false);
  const [lastResult, setLastResult] = useState<{checked: number; matched: number; notified: number; deduped: number} | null>(null);
  const [savedAt, setSavedAt] = useState<string | null>(null);

  useEffect(() => {
    fetchPreferences()
      .then((p) => {
        setPrefs({ ...EMPTY, ...p, brands: p.brands ?? [] });
        setBrandsInput((p.brands ?? []).join(", "));
      })
      .catch(() => {});
  }, []);

  function update<K extends keyof AlertPreferences>(key: K, value: AlertPreferences[K]) {
    setPrefs((p) => ({ ...p, [key]: value }));
  }

  async function onSave() {
    setSaving(true);
    try {
      const payload: AlertPreferences = {
        ...prefs,
        brands: brandsInput
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
      };
      const saved = await savePreferences(payload);
      setPrefs({ ...EMPTY, ...saved, brands: saved.brands ?? [] });
      setSavedAt(new Date().toLocaleTimeString("es-ES"));
    } finally {
      setSaving(false);
    }
  }

  async function onEvaluate() {
    setEvaluating(true);
    try {
      const r = await evaluateAlerts();
      setLastResult(r);
    } finally {
      setEvaluating(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6 px-4 py-8">
      <div>
        <Link href="/" className="text-sm text-blue-600 hover:underline dark:text-blue-400">
          ← Volver
        </Link>
        <h1 className="mt-2 text-2xl font-bold">Preferencias de alertas</h1>
        <p className="text-sm text-neutral-500 dark:text-neutral-400">
          Te avisaremos cuando aparezca un anuncio que cumpla todos estos filtros.
        </p>
      </div>

      <section className="rounded-xl border border-neutral-200 bg-white p-5 dark:border-neutral-800 dark:bg-neutral-900">
        <h2 className="mb-3 text-sm font-bold uppercase tracking-wide text-neutral-500">Presupuesto</h2>
        <div className="grid gap-3 md:grid-cols-2">
          <label className="flex flex-col gap-1 text-xs font-medium text-neutral-500">
            Precio max. del coche (€)
            <input
              type="number"
              className="rounded-lg border border-neutral-300 bg-white px-2.5 py-1.5 text-sm dark:border-neutral-700 dark:bg-neutral-800"
              value={prefs.max_purchase_price ?? ""}
              onChange={(e) => update("max_purchase_price", numOrNull(e.target.value))}
              placeholder="15000"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs font-medium text-neutral-500">
            Coste total max. en España (€)
            <input
              type="number"
              className="rounded-lg border border-neutral-300 bg-white px-2.5 py-1.5 text-sm dark:border-neutral-700 dark:bg-neutral-800"
              value={prefs.max_total_cost ?? ""}
              onChange={(e) => update("max_total_cost", numOrNull(e.target.value))}
              placeholder="20000"
            />
          </label>
        </div>
      </section>

      <section className="rounded-xl border border-neutral-200 bg-white p-5 dark:border-neutral-800 dark:bg-neutral-900">
        <h2 className="mb-3 text-sm font-bold uppercase tracking-wide text-neutral-500">Rentabilidad</h2>
        <div className="grid gap-3 md:grid-cols-2">
          <label className="flex flex-col gap-1 text-xs font-medium text-neutral-500">
            Margen min. absoluto (€)
            <input
              type="number"
              className="rounded-lg border border-neutral-300 bg-white px-2.5 py-1.5 text-sm dark:border-neutral-700 dark:bg-neutral-800"
              value={prefs.min_profit ?? ""}
              onChange={(e) => update("min_profit", numOrNull(e.target.value))}
              placeholder="500"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs font-medium text-neutral-500">
            Margen min. relativo (0-1)
            <input
              type="number"
              step="0.01"
              className="rounded-lg border border-neutral-300 bg-white px-2.5 py-1.5 text-sm dark:border-neutral-700 dark:bg-neutral-800"
              value={prefs.min_roi ?? ""}
              onChange={(e) => update("min_roi", numOrNull(e.target.value))}
              placeholder="0.10"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs font-medium text-neutral-500">
            Score ganga min. (0-1)
            <input
              type="number"
              step="0.01"
              className="rounded-lg border border-neutral-300 bg-white px-2.5 py-1.5 text-sm dark:border-neutral-700 dark:bg-neutral-800"
              value={prefs.min_bargain_score ?? ""}
              onChange={(e) => update("min_bargain_score", numOrNull(e.target.value))}
              placeholder="0.15"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs font-medium text-neutral-500">
            Riesgo max. (0-1)
            <input
              type="number"
              step="0.01"
              className="rounded-lg border border-neutral-300 bg-white px-2.5 py-1.5 text-sm dark:border-neutral-700 dark:bg-neutral-800"
              value={prefs.max_risk_score ?? ""}
              onChange={(e) => update("max_risk_score", numOrNull(e.target.value))}
              placeholder="0.7"
            />
          </label>
        </div>
      </section>

      <section className="rounded-xl border border-neutral-200 bg-white p-5 dark:border-neutral-800 dark:bg-neutral-900">
        <h2 className="mb-3 text-sm font-bold uppercase tracking-wide text-neutral-500">Técnicos</h2>
        <div className="grid gap-3 md:grid-cols-2">
          <label className="flex flex-col gap-1 text-xs font-medium text-neutral-500">
            Marcas (separadas por coma, vacío = todas)
            <input
              className="rounded-lg border border-neutral-300 bg-white px-2.5 py-1.5 text-sm dark:border-neutral-700 dark:bg-neutral-800"
              value={brandsInput}
              onChange={(e) => setBrandsInput(e.target.value)}
              placeholder="BMW, Audi, Ford"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs font-medium text-neutral-500">
            Combustible
            <select
              className="rounded-lg border border-neutral-300 bg-white px-2.5 py-1.5 text-sm dark:border-neutral-700 dark:bg-neutral-800"
              value={prefs.fuel ?? ""}
              onChange={(e) => update("fuel", e.target.value || null)}
            >
              <option value="">Todos</option>
              <option value="diesel">Diesel</option>
              <option value="petrol">Gasolina</option>
              <option value="electric">Eléctrico</option>
              <option value="hybrid">Híbrido</option>
              <option value="plug-in-hybrid">Híbrido enchufable</option>
              <option value="lpg">GLP</option>
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs font-medium text-neutral-500">
            Cambio
            <select
              className="rounded-lg border border-neutral-300 bg-white px-2.5 py-1.5 text-sm dark:border-neutral-700 dark:bg-neutral-800"
              value={prefs.transmission ?? ""}
              onChange={(e) => update("transmission", e.target.value || null)}
            >
              <option value="">Todos</option>
              <option value="manual">Manual</option>
              <option value="automatic">Automático</option>
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs font-medium text-neutral-500">
            Km max.
            <input
              type="number"
              className="rounded-lg border border-neutral-300 bg-white px-2.5 py-1.5 text-sm dark:border-neutral-700 dark:bg-neutral-800"
              value={prefs.max_mileage ?? ""}
              onChange={(e) => update("max_mileage", numOrNull(e.target.value) as number | null)}
              placeholder="200000"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs font-medium text-neutral-500">
            Año min.
            <input
              type="number"
              className="rounded-lg border border-neutral-300 bg-white px-2.5 py-1.5 text-sm dark:border-neutral-700 dark:bg-neutral-800"
              value={prefs.year_min ?? ""}
              onChange={(e) => update("year_min", numOrNull(e.target.value) as number | null)}
              placeholder="2015"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs font-medium text-neutral-500">
            Región
            <select
              className="rounded-lg border border-neutral-300 bg-white px-2.5 py-1.5 text-sm dark:border-neutral-700 dark:bg-neutral-800"
              value={prefs.region ?? ""}
              onChange={(e) => update("region", e.target.value || null)}
            >
              <option value="">Todas</option>
              <option value="ES">España</option>
              <option value="EU">Europa</option>
            </select>
          </label>
        </div>
      </section>

      <section className="rounded-xl border border-neutral-200 bg-white p-5 dark:border-neutral-800 dark:bg-neutral-900">
        <h2 className="mb-3 text-sm font-bold uppercase tracking-wide text-neutral-500">Canales</h2>
        <div className="flex gap-4 text-sm">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              className="h-4 w-4 accent-blue-600"
              checked={prefs.notify_web}
              onChange={(e) => update("notify_web", e.target.checked)}
            />
            Web (campanita)
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              className="h-4 w-4 accent-blue-600"
              checked={prefs.notify_email}
              onChange={(e) => update("notify_email", e.target.checked)}
            />
            Email
          </label>
        </div>
        <p className="mt-2 text-xs text-neutral-500">
          El envío por email requiere configurar SMTP en <code className="rounded bg-neutral-100 px-1 py-0.5 dark:bg-neutral-800">.env</code>{" "}
          (<code className="rounded bg-neutral-100 px-1 py-0.5 dark:bg-neutral-800">SMTP_HOST</code>,{" "}
          <code className="rounded bg-neutral-100 px-1 py-0.5 dark:bg-neutral-800">SMTP_USER</code>,{" "}
          <code className="rounded bg-neutral-100 px-1 py-0.5 dark:bg-neutral-800">SMTP_PASSWORD</code>,{" "}
          <code className="rounded bg-neutral-100 px-1 py-0.5 dark:bg-neutral-800">ALERT_EMAIL_TO</code>). Sin SMTP, las alertas llegan solo por la campanita web.
        </p>
      </section>

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={onSave}
          disabled={saving}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {saving ? "Guardando…" : "Guardar preferencias"}
        </button>
        <button
          type="button"
          onClick={onEvaluate}
          disabled={evaluating}
          className="rounded-lg border border-blue-600 px-4 py-2 text-sm font-medium text-blue-600 hover:bg-blue-50 disabled:opacity-50 dark:text-blue-400 dark:hover:bg-blue-950"
        >
          {evaluating ? "Evaluando…" : "Evaluar gangas ahora"}
        </button>
        {savedAt && <span className="self-center text-xs text-neutral-500">Guardado a las {savedAt}</span>}
      </div>

      {lastResult && (
        <div className="rounded-xl border border-green-200 bg-green-50 p-4 text-sm text-green-800 dark:border-green-900 dark:bg-green-950 dark:text-green-200">
          Evaluados {lastResult.checked} listings · {lastResult.matched} coinciden · {lastResult.notified} nuevas notificaciones · {lastResult.deduped} ya existentes
        </div>
      )}
    </div>
  );
}

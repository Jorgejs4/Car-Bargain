"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

const FUELS = ["diesel", "petrol", "electric", "hybrid", "lpg", "hydrogen"];
const TRANSMISSIONS = ["automatic", "manual"];
const SELLER_TYPES = ["dealer", "private", "commercial"];

function parseNum(v: string | null): string {
  return v ?? "";
}

export function FilterFormInner() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [brand, setBrand] = useState(parseNum(searchParams.get("brand")));
  const [model, setModel] = useState(parseNum(searchParams.get("model")));
  const [priceMin, setPriceMin] = useState(parseNum(searchParams.get("price_min")));
  const [priceMax, setPriceMax] = useState(parseNum(searchParams.get("price_max")));
  const [mileageMax, setMileageMax] = useState(parseNum(searchParams.get("mileage_max")));
  const [yearMin, setYearMin] = useState(parseNum(searchParams.get("year_min")));
  const [fuel, setFuel] = useState(parseNum(searchParams.get("fuel")));
  const [transmission, setTransmission] = useState(parseNum(searchParams.get("transmission")));
  const [sellerType, setSellerType] = useState(parseNum(searchParams.get("seller_type")));
  const [needsReview, setNeedsReview] = useState(
    searchParams.get("needs_review") === "true"
  );

  function apply() {
    const params = new URLSearchParams();
    const set = (key: string, value: string) => {
      if (value) params.set(key, value);
    };
    set("brand", brand);
    set("model", model);
    set("price_min", priceMin);
    set("price_max", priceMax);
    set("mileage_max", mileageMax);
    set("year_min", yearMin);
    set("fuel", fuel);
    set("transmission", transmission);
    set("seller_type", sellerType);
    if (needsReview) params.set("needs_review", "true");
    const qs = params.toString();
    router.push(qs ? `/?${qs}` : "/");
  }

  function reset() {
    setBrand("");
    setModel("");
    setPriceMin("");
    setPriceMax("");
    setMileageMax("");
    setYearMin("");
    setFuel("");
    setTransmission("");
    setSellerType("");
    setNeedsReview(false);
    router.push("/");
  }

  const inputCls =
    "rounded-lg border border-neutral-300 bg-white px-2.5 py-1.5 text-sm outline-none focus:border-blue-500 dark:border-neutral-700 dark:bg-neutral-800";

  return (
    <div className="rounded-xl border border-neutral-200 bg-white p-4 dark:border-neutral-800 dark:bg-neutral-900">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <label className="flex flex-col gap-1 text-xs font-medium text-neutral-500">
          Marca
          <input className={inputCls} value={brand} onChange={(e) => setBrand(e.target.value)} placeholder="BMW" />
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-neutral-500">
          Modelo
          <input className={inputCls} value={model} onChange={(e) => setModel(e.target.value)} placeholder="320d" />
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-neutral-500">
          Precio mín.
          <input className={inputCls} type="number" min={0} value={priceMin} onChange={(e) => setPriceMin(e.target.value)} placeholder="10000" />
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-neutral-500">
          Precio máx.
          <input className={inputCls} type="number" min={0} value={priceMax} onChange={(e) => setPriceMax(e.target.value)} placeholder="25000" />
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-neutral-500">
          Km máx.
          <input className={inputCls} type="number" min={0} value={mileageMax} onChange={(e) => setMileageMax(e.target.value)} placeholder="80000" />
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-neutral-500">
          Año mín.
          <input className={inputCls} type="number" min={1990} max={2026} value={yearMin} onChange={(e) => setYearMin(e.target.value)} placeholder="2015" />
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-neutral-500">
          Combustible
          <select className={inputCls} value={fuel} onChange={(e) => setFuel(e.target.value)}>
            <option value="">Todos</option>
            {FUELS.map((f) => (
              <option key={f} value={f}>{f}</option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-neutral-500">
          Cambio
          <select className={inputCls} value={transmission} onChange={(e) => setTransmission(e.target.value)}>
            <option value="">Todos</option>
            {TRANSMISSIONS.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-neutral-500">
          Vendedor
          <select className={inputCls} value={sellerType} onChange={(e) => setSellerType(e.target.value)}>
            <option value="">Todos</option>
            {SELLER_TYPES.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </label>
        <label className="flex items-end gap-2 pb-1.5 text-xs font-medium text-neutral-500">
          <input
            type="checkbox"
            className="h-4 w-4 accent-blue-600"
            checked={needsReview}
            onChange={(e) => setNeedsReview(e.target.checked)}
          />
          Solo revisar
        </label>
      </div>
      <div className="mt-3 flex gap-2">
        <button
          onClick={apply}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          Aplicar filtros
        </button>
        <button
          onClick={reset}
          className="rounded-lg border border-neutral-300 px-4 py-2 text-sm font-medium hover:bg-neutral-100 dark:border-neutral-700 dark:hover:bg-neutral-800"
        >
          Limpiar
        </button>
      </div>
    </div>
  );
}

export default function FilterForm() {
  return (
    <Suspense fallback={<div className="h-24" />}>
      <FilterFormInner />
    </Suspense>
  );
}

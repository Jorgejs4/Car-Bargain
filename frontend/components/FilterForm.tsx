"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { fetchBrands, fetchModels } from "@/lib/api";

const FUELS = ["diesel", "petrol", "electric", "hybrid", "lpg", "hydrogen"];
const TRANSMISSIONS = ["automatic", "manual"];
const SELLER_TYPES = ["dealer", "private", "commercial"];
const REGIONS = [
  { value: "", label: "Todos" },
  { value: "ES", label: "Espana" },
  { value: "EU", label: "Europa" },
];
const SORT_OPTIONS = [
  { value: "absolute_margin-desc", label: "Mayor ahorro EUR" },
  { value: "cross_border-desc", label: "Mejor cross-border EUR" },
  { value: "bargain-desc", label: "Mejor ganga %" },
  { value: "price-asc", label: "Precio bajo" },
  { value: "price-desc", label: "Precio alto" },
  { value: "total_cost-asc", label: "Precio total bajo" },
  { value: "mileage-asc", label: "Menos KM" },
  { value: "mileage-desc", label: "Mas KM" },
  { value: "year-desc", label: "Mas nuevos" },
  { value: "year-asc", label: "Mas viejos" },
];

export function FilterFormInner() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const [brand, setBrand] = useState(searchParams.get("brand") ?? "");
  const [model, setModel] = useState(searchParams.get("model") ?? "");
  const [priceMin, setPriceMin] = useState(searchParams.get("price_min") ?? "");
  const [priceMax, setPriceMax] = useState(searchParams.get("price_max") ?? "");
  const [mileageMax, setMileageMax] = useState(searchParams.get("mileage_max") ?? "");
  const [yearMin, setYearMin] = useState(searchParams.get("year_min") ?? "");
  const [fuel, setFuel] = useState(searchParams.get("fuel") ?? "");
  const [transmission, setTransmission] = useState(searchParams.get("transmission") ?? "");
  const [sellerType, setSellerType] = useState(searchParams.get("seller_type") ?? "");
  const [region, setRegion] = useState(searchParams.get("region") ?? "");
  const [sortBy, setSortBy] = useState(searchParams.get("sort") ?? "absolute_margin-desc");
  const [needsReview, setNeedsReview] = useState(searchParams.get("needs_review") === "true");
  const [onlyBargains, setOnlyBargains] = useState(
    searchParams.get("min_bargain_score") !== null || pathname === "/",
  );
  const [minAbsMargin, setMinAbsMargin] = useState(searchParams.get("min_absolute_margin") ?? "");

  const [brands, setBrands] = useState<string[]>([]);
  const [models, setModels] = useState<string[]>([]);

  useEffect(() => {
    fetchBrands().then(setBrands).catch(() => {});
  }, []);

  useEffect(() => {
    if (!brand) return;
    void fetchModels(brand).then(setModels).catch(() => setModels([]));
  }, [brand]);

  function apply() {
    const params = new URLSearchParams();
    const set = (key: string, value: string) => { if (value) params.set(key, value); };
    set("brand", brand);
    set("model", model);
    set("price_min", priceMin);
    set("price_max", priceMax);
    set("mileage_max", mileageMax);
    set("year_min", yearMin);
    set("fuel", fuel);
    set("transmission", transmission);
    set("seller_type", sellerType);
    set("region", region);
    set("sort", sortBy);
    if (needsReview) params.set("needs_review", "true");
    if (onlyBargains) params.set("min_bargain_score", "0");
    if (minAbsMargin) params.set("min_absolute_margin", minAbsMargin);
    const qs = params.toString();
    const path = window.location.pathname;
    router.push(qs ? `${path}?${qs}` : path);
  }

  function reset() {
    setBrand(""); setModel(""); setPriceMin(""); setPriceMax("");
    setMileageMax(""); setYearMin(""); setFuel(""); setTransmission("");
    setSellerType(""); setRegion(""); setSortBy("absolute_margin-desc");
    setNeedsReview(false); setOnlyBargains(pathname === "/"); setMinAbsMargin(""); setModels([]);
    router.push(window.location.pathname);
  }

  const inputCls = "rounded-lg border border-neutral-300 bg-white px-2.5 py-1.5 text-sm outline-none focus:border-blue-500 dark:border-neutral-700 dark:bg-neutral-800";
  const selectCls = inputCls;

  return (
    <div className="rounded-xl border border-neutral-200 bg-white p-4 dark:border-neutral-800 dark:bg-neutral-900">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <label className="flex flex-col gap-1 text-xs font-medium text-neutral-500">
          Marca
          <select className={selectCls} value={brand} onChange={(e) => { setBrand(e.target.value); setModel(""); }}>
            <option value="">Todas</option>
            {brands.map((b) => (<option key={b} value={b}>{b}</option>))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-neutral-500">
          Modelo
          <select className={selectCls} value={model} onChange={(e) => setModel(e.target.value)} disabled={!brand || models.length === 0}>
            <option value="">Todos</option>
            {models.map((m) => (<option key={m} value={m}>{m}</option>))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-neutral-500">
          Region
          <select className={selectCls} value={region} onChange={(e) => setRegion(e.target.value)}>
            {REGIONS.map((r) => (<option key={r.value} value={r.value}>{r.label}</option>))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-neutral-500">
          Ordenar
          <select className={selectCls} value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
            {SORT_OPTIONS.map((s) => (<option key={s.value} value={s.value}>{s.label}</option>))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-neutral-500">
          Precio min.
          <input className={inputCls} type="number" min={0} value={priceMin} onChange={(e) => setPriceMin(e.target.value)} placeholder="10000" />
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-neutral-500">
          Precio max.
          <input className={inputCls} type="number" min={0} value={priceMax} onChange={(e) => setPriceMax(e.target.value)} placeholder="25000" />
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-neutral-500">
          Km max.
          <input className={inputCls} type="number" min={0} value={mileageMax} onChange={(e) => setMileageMax(e.target.value)} placeholder="80000" />
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-neutral-500">
          Ano min.
          <input className={inputCls} type="number" min={1990} max={2026} value={yearMin} onChange={(e) => setYearMin(e.target.value)} placeholder="2015" />
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-neutral-500">
          Combustible
          <select className={selectCls} value={fuel} onChange={(e) => setFuel(e.target.value)}>
            <option value="">Todos</option>
            {FUELS.map((f) => (<option key={f} value={f}>{f}</option>))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-neutral-500">
          Cambio
          <select className={selectCls} value={transmission} onChange={(e) => setTransmission(e.target.value)}>
            <option value="">Todos</option>
            {TRANSMISSIONS.map((t) => (<option key={t} value={t}>{t}</option>))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-neutral-500">
          Vendedor
          <select className={selectCls} value={sellerType} onChange={(e) => setSellerType(e.target.value)}>
            <option value="">Todos</option>
            {SELLER_TYPES.map((seller) => (<option key={seller} value={seller}>{seller}</option>))}
          </select>
        </label>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-4">
        <label className="flex items-center gap-2 text-xs font-medium text-neutral-500">
          <input type="checkbox" className="h-4 w-4 accent-green-600" checked={onlyBargains} onChange={(e) => setOnlyBargains(e.target.checked)} />
          Solo gangas
        </label>
        <label className="flex items-center gap-2 text-xs font-medium text-neutral-500">
          Ahorro min.
          <input className={inputCls + " w-24"} type="number" min={0} value={minAbsMargin} onChange={(e) => setMinAbsMargin(e.target.value)} placeholder="500€" />
        </label>
      </div>
      <div className="mt-3 flex gap-2">
        <button onClick={apply} className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">
          Aplicar filtros
        </button>
        <button onClick={reset} className="rounded-lg border border-neutral-300 px-4 py-2 text-sm font-medium hover:bg-neutral-100 dark:border-neutral-700 dark:hover:bg-neutral-800">
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

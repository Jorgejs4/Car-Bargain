export type ListingStatus = "ACTIVE" | "STALE" | "REMOVED" | "SOLD";

export type ListingEventType =
  | "LISTED"
  | "PRICE_CHANGED"
  | "DESCRIPTION_CHANGED"
  | "MILEAGE_CHANGED"
  | "STATUS_CHANGED"
  | "REMOVED"
  | "REAPPEARED";

export interface ListingListItem {
  id: number;
  source: string;
  source_listing_id: string;
  url: string | null;
  seller_type: string | null;
  country: string | null;
  status: ListingStatus;
  is_historical: boolean;
  brand: string | null;
  model: string | null;
  generation: string | null;
  variant: string | null;
  year: number | null;
  fuel: string | null;
  transmission: string | null;
  power_kw: number | null;
  title: string | null;
  price: number | null;
  currency: string | null;
  mileage: number | null;
  condition_signals: Record<string, unknown> | null;
  photo_signals: Record<string, unknown> | null;
  text_signals: Record<string, unknown> | null;
  needs_review: boolean;
  risk_score: number | null;
  bargain_score: number | null;
  absolute_margin: number | null;
  predicted_price: number | null;
  predicted_price_es: number | null;
  cross_border_margin: number | null;
  cross_border_score: number | null;
  estimated_import_cost: number | null;
  total_cost_es: number | null;
  first_seen_at: string;
  last_seen_at: string | null;
}

export interface VehicleRead {
  id: number;
  brand: string;
  model: string | null;
  generation: string | null;
  variant: string | null;
  year: number | null;
  registration_date: string | null;
  fuel: string | null;
  transmission: string | null;
  drivetrain: string | null;
  power_kw: number | null;
  engine_cc: number | null;
  co2_g_km: number | null;
  body_type: string | null;
  created_at: string;
  updated_at: string;
}

export interface ListingSnapshotRead {
  id: number;
  listing_id: number;
  scraped_at: string;
  price: number | null;
  currency: string | null;
  mileage: number | null;
  title: string | null;
  description: string | null;
  seller_type: string | null;
  location: string | null;
  condition_signals: Record<string, unknown> | null;
  created_at: string;
}

export interface ListingEventRead {
  id: number;
  listing_id: number;
  event_type: ListingEventType;
  event_timestamp: string;
  old_value: Record<string, unknown> | null;
  new_value: Record<string, unknown> | null;
}

export interface PhotoAnalysisRead {
  id: number;
  listing_id: number;
  image_url: string;
  local_path: string | null;
  label: string | null;
  probability: number | null;
  model_version: string | null;
  analyzed_at: string;
  created_at: string;
}

export interface ListingDetail extends ListingListItem {
  vehicle: VehicleRead | null;
  current_snapshot: ListingSnapshotRead | null;
  snapshots: ListingSnapshotRead[];
  events: ListingEventRead[];
  photo_analyses: PhotoAnalysisRead[];
  import_breakdown: ImportBreakdown | null;
  market: MarketStats | null;
}

export interface ImportBreakdown {
  source_country: string;
  transport_cost: number;
  registration_tax: number;
  itv_inspection: number;
  registration_fees: number;
  total_import_cost: number;
  total_cost_es: number;
  rules_version: string;
}

export interface PricePoint {
  scraped_at: string;
  price: number | null;
  currency: string | null;
  mileage: number | null;
}

export interface VehicleDetail extends VehicleRead {
  listings: ListingListItem[];
}

export interface VehicleHistoryEntry {
  listing_id: number;
  source: string;
  source_listing_id: string;
  url: string | null;
  status: string;
  snapshots: PricePoint[];
}

export interface MarketStats {
  vehicle_id: number;
  count: number;
  min_price: number | null;
  p10: number | null;
  p50: number | null;
  p90: number | null;
  max_price: number | null;
  mean_price: number | null;
  currency: string | null;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface ListingFilters {
  page?: number;
  page_size?: number;
  status?: ListingStatus;
  brand?: string;
  model?: string;
  country?: string;
  region?: string;
  price_min?: number;
  price_max?: number;
  mileage_max?: number;
  year_min?: number;
  fuel?: string;
  transmission?: string;
  seller_type?: string;
  source?: string;
  needs_review?: boolean;
  only_clean?: boolean;
  min_bargain_score?: number;
  min_absolute_margin?: number;
  min_cross_border_margin?: number;
  sort_by?: string;
  sort_order?: string;
}

const PUBLIC_API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ??
  "https://p01--car-bargains-backend-service--g8btymwgmj8f.code.run";
const SERVER_API_BASE_URL =
  process.env.API_INTERNAL_URL ?? PUBLIC_API_BASE_URL;
const normalizeApiBaseUrl = (value: string) =>
  /^https?:\/\//i.test(value) ? value : `https://${value}`;
export const API_BASE_URL =
  normalizeApiBaseUrl(
    typeof window === "undefined" ? SERVER_API_BASE_URL : PUBLIC_API_BASE_URL,
  );

async function getJson<T>(path: string, init?: RequestInit | AbortSignal): Promise<T> {
  const opts: RequestInit = init instanceof AbortSignal
    ? { signal: init }
    : (init ?? {});
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...opts,
    cache: "no-store",
    headers: { Accept: "application/json", ...(opts.headers ?? {}) },
  });
  if (!res.ok) {
    throw new Error(`API ${res.status} en ${path}`);
  }
  return res.json() as Promise<T>;
}

function buildQuery(params: object): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

export interface HealthStatus {
  database: string;
  redis: string;
}

export async function fetchHealth(signal?: AbortSignal): Promise<HealthStatus> {
  return getJson<HealthStatus>(`/health`, signal);
}

export async function fetchListings(
  filters: ListingFilters = {},
  signal?: AbortSignal
): Promise<Page<ListingListItem>> {
  return getJson<Page<ListingListItem>>(
    `/api/v1/listings${buildQuery(filters)}`,
    signal
  );
}

export async function fetchHistoricalListings(
  filters: ListingFilters = {},
  signal?: AbortSignal
): Promise<Page<ListingListItem>> {
  return getJson<Page<ListingListItem>>(
    `/api/v1/listings/historical${buildQuery(filters)}`,
    signal
  );
}

export async function fetchListingDetail(
  id: number,
  signal?: AbortSignal
): Promise<ListingDetail> {
  return getJson<ListingDetail>(`/api/v1/listings/${id}`, signal);
}

export async function fetchVehicleDetail(
  id: number,
  signal?: AbortSignal
): Promise<VehicleDetail> {
  return getJson<VehicleDetail>(`/api/v1/vehicles/${id}`, signal);
}

export async function fetchVehicleHistory(
  id: number,
  signal?: AbortSignal
): Promise<VehicleHistoryEntry[]> {
  return getJson<VehicleHistoryEntry[]>(`/api/v1/vehicles/${id}/history`, signal);
}

export async function fetchVehicleMarket(
  id: number,
  signal?: AbortSignal
): Promise<MarketStats> {
  return getJson<MarketStats>(`/api/v1/vehicles/${id}/market`, signal);
}

export async function fetchBrands(
  signal?: AbortSignal
): Promise<string[]> {
  return getJson<string[]>("/api/v1/vehicles/brands", signal);
}

export async function fetchModels(
  brand: string,
  signal?: AbortSignal
): Promise<string[]> {
  return getJson<string[]>(`/api/v1/vehicles/models?brand=${encodeURIComponent(brand)}`, signal);
}

export interface AlertPreferences {
  id?: number;
  user_key?: string;
  max_purchase_price: number | null;
  max_total_cost: number | null;
  min_profit: number | null;
  min_roi: number | null;
  min_bargain_score: number | null;
  max_risk_score: number | null;
  brands: string[] | null;
  fuel: string | null;
  transmission: string | null;
  max_mileage: number | null;
  year_min: number | null;
  region: string | null;
  notify_web: boolean;
  notify_email: boolean;
}

export async function fetchPreferences(signal?: AbortSignal): Promise<AlertPreferences> {
  return getJson<AlertPreferences>("/api/v1/users/me/preferences", signal);
}

export async function savePreferences(payload: AlertPreferences): Promise<AlertPreferences> {
  return getJson<AlertPreferences>("/api/v1/users/me/preferences", {
    method: "PUT",
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
  });
}

export async function evaluateAlerts(): Promise<{checked: number; matched: number; notified: number; deduped: number}> {
  return getJson("/api/v1/users/me/preferences/evaluate", { method: "POST" });
}

export interface NotificationItem {
  id: number;
  listing_id: number;
  title: string;
  body: Record<string, unknown> | null;
  status: string;
  created_at: string;
}

export async function fetchNotifications(unread = false): Promise<NotificationItem[]> {
  return getJson<NotificationItem[]>(`/api/v1/users/me/notifications?unread=${unread}`);
}

export async function markNotificationRead(id: number): Promise<void> {
  await getJson(`/api/v1/users/me/notifications/${id}/read`, { method: "POST" });
}

/** Helper fetch contra la API GEIS (/api/v1), con manejo de errores en español. */

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, message: string, body?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
}

type QueryParams = Record<string, string | number | boolean | undefined | null>;

function toQuery(params?: QueryParams): string {
  if (!params) return '';
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === '') continue;
    sp.append(k, String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : '';
}

export interface ApiOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  body?: unknown;
  query?: QueryParams;
  headers?: Record<string, string>;
  signal?: AbortSignal;
}

export async function api<T>(path: string, opts: ApiOptions = {}): Promise<T> {
  const url = `/api/v1${path}${toQuery(opts.query)}`;
  let res: Response;
  try {
    res = await fetch(url, {
      method: opts.method ?? 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...(opts.headers ?? {}),
      },
      body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
      signal: opts.signal,
    });
  } catch (e) {
    throw new ApiError(0, 'No se pudo conectar con el servidor. Verifica que el backend esté corriendo en :8000.');
  }
  const text = await res.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }
  if (!res.ok) {
    const msg =
      typeof data === 'object' && data !== null && 'detail' in data
        ? String((data as Record<string, unknown>).detail)
        : typeof data === 'object' && data !== null && 'message' in data
          ? String((data as Record<string, unknown>).message)
          : `Error ${res.status} en la petición`;
    throw new ApiError(res.status, msg, data);
  }
  return data as T;
}

export const get = <T>(path: string, query?: QueryParams, opts?: Omit<ApiOptions, 'method' | 'query'>) =>
  api<T>(path, { ...opts, method: 'GET', query });
export const post = <T>(path: string, body?: unknown, opts?: Omit<ApiOptions, 'method' | 'body'>) =>
  api<T>(path, { ...opts, method: 'POST', body });
export const put = <T>(path: string, body?: unknown, opts?: Omit<ApiOptions, 'method' | 'body'>) =>
  api<T>(path, { ...opts, method: 'PUT', body });
export const patch = <T>(path: string, body?: unknown, opts?: Omit<ApiOptions, 'method' | 'body'>) =>
  api<T>(path, { ...opts, method: 'PATCH', body });
export const del = <T>(path: string, opts?: Omit<ApiOptions, 'method'>) =>
  api<T>(path, { ...opts, method: 'DELETE' });

/**
 * Variante de descarga: devuelve el cuerpo como Blob (CSV/Excel/PDF).
 * NO pasa por JSON.parse: la versión normal corrompería binarios.
 */
export async function apiBlob(path: string, opts: ApiOptions = {}): Promise<Blob> {
  const url = `/api/v1${path}${toQuery(opts.query)}`;
  let res: Response;
  try {
    res = await fetch(url, {
      method: opts.method ?? 'GET',
      headers: { 'Content-Type': 'application/json', ...(opts.headers ?? {}) },
      body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
      signal: opts.signal,
    });
  } catch {
    throw new ApiError(0, 'No se pudo conectar con el servidor. Verifica que el backend esté corriendo en :8000.');
  }
  if (!res.ok) {
    const text = await res.text();
    let msg = `Error ${res.status} en la descarga`;
    try {
      const data = JSON.parse(text);
      if (typeof data === 'object' && data !== null && 'detail' in data) msg = String(data.detail);
    } catch { /* el cuerpo de error no era JSON */ }
    throw new ApiError(res.status, msg, text);
  }
  return res.blob();
}

/** Mensaje legible para mostrar en Alert. */
export function errorMessage(e: unknown): string {
  if (e instanceof ApiError) return e.message;
  if (e instanceof Error) return e.message;
  return 'Ocurrió un error inesperado.';
}

/* ---------- Tipos compartidos (alineados con el SRS §5) ---------- */

export interface Lineage {
  editions?: Record<string, string> | string[];
  params_version?: string | number;
  calculated_at?: string;
  model_version?: string;
}

export interface Lead {
  id?: string;
  denue_id?: string;
  razon_social?: string;
  nombre?: string;
  scian_code?: string;
  scian_desc?: string;
  estrato?: string;
  municipio?: string;
  direccion?: string;
  telefono?: string;
  correo?: string;
  sitio_web?: string;
  lat?: number;
  lon?: number;
  idt?: number;
  score?: number;
  score_breakdown?: Record<string, number>;
  distancia_km?: number;
  estado?: string;
}

export interface Verdict {
  veredicto?: 'AVANZAR' | 'NEGOCIAR' | 'EXPLORAR_OTRA_ZONA' | string;
  confianza?: string;
  factores?: string[];
  riesgo?: string;
}

/** Investigación (alineada con InvestigationOut del backend). */
export interface Investigation {
  investigation_id: string;
  user_id?: string;
  title?: string;
  investigation_type?: string;
  vertical?: string | null;
  territory_kind?: string;
  center_lat?: number | null;
  center_lon?: number | null;
  radii_m?: number[] | null;
  params?: Record<string, unknown>;
  scores?: Record<string, number | string> | null;
  verdict?: string | null;
  status?: string;
  created_at?: string;
  lineage?: Lineage | null;
}

export interface Territory {
  id: string;
  nombre?: string;
  tipo?: string;
  geojson?: unknown;
  area_km2?: number;
  created_at?: string;
}

/* ---------- Módulo Radar (fusión GEIS × Biokool — ECOSISTEMA-FUSION.md) ---------- */

/** Lead curado del módulo Radar (`GET /leads/curados`). */
export interface LeadCurado {
  lead_id: number;
  nombre: string;
  giro?: string;
  direccion?: string;
  telefono?: string;
  web?: string;
  rating?: number;
  linea_recomendada?: 'koolkat' | 'solar' | 'evaporativa' | string;
  etapa?: string;
  temp_zona?: number;
  notas?: string;
  score?: number;
  score_components?: Record<string, unknown>;
  lat?: number;
  lon?: number;
  source?: string;
  enriquecido_apollo?: boolean;
  crm_synced_at?: string | null;
}

export type EtapaRadar = 'nuevo' | 'contactado' | 'reunion' | 'propuesta' | 'ganado' | 'perdido';

export const ETAPAS_RADAR: { id: EtapaRadar; label: string }[] = [
  { id: 'nuevo', label: 'Nuevo' },
  { id: 'contactado', label: 'Contactado' },
  { id: 'reunion', label: 'Reunión' },
  { id: 'propuesta', label: 'Propuesta' },
  { id: 'ganado', label: 'Ganado' },
  { id: 'perdido', label: 'Perdido' },
];

export function lineaColor(linea?: string): string {
  switch ((linea ?? '').toLowerCase()) {
    case 'koolkat': return '#E8590C';      // naranja — control térmico
    case 'solar': return '#E8A13D';        // amarillo — paneles solares
    case 'evaporativa': return '#0E5FD8';  // azul — bioclimatización
    default: return '#8a93a6';
  }
}

/** Ejecución de un pipeline (`GET /pipelines/runs`). */
export interface PipelineRun {
  run_id: number;
  pipeline: string;
  estado: 'running' | 'ok' | 'error' | string;
  detalle?: unknown;
  started_at?: string;
  finished_at?: string;
}

/** Provider de la capa anti-cautiverio (`GET /providers`). */
export interface Provider {
  name: string;
  kind: string;
  mode: 'local' | 'cloud' | 'disabled' | string;
  provider: string;
  config?: Record<string, unknown>;
  enabled?: boolean;
  updated_at?: string;
}

/** Semáforo del sistema (`GET /system/health`). */
export interface SystemHealth {
  postgres?: string;
  n8n?: string;
  scraper?: string;
  providers?: Record<string, string | boolean>;
  [k: string]: unknown;
}

/** Estado de la integración LinkedIn (`GET /integrations/linkedin/status`). */
export interface LinkedInStatus {
  conectado?: boolean;
  connected?: boolean;
  [k: string]: unknown;
}

/* ---------- Módulo Configuración inicial + IA interna ---------- */

/** Perfil de empresa activo (`GET /company/profile`). 404 si aún no hay ninguno. */
export interface CompanyProfile {
  id: string;
  version: number;
  nombre: string;
  vertical_id?: string;
  markdown?: string;
  is_active?: boolean;
  created_at?: string;
}

export interface CompanyProfileSummary {
  id: string;
  version: number;
  nombre: string;
  vertical_id?: string;
  is_active: boolean;
  created_at?: string;
}

export interface PutCompanyProfileOut {
  id: string;
  version: number;
  faltantes: string[];
}

export interface TamDefault {
  producto?: string;
  nombre?: string;
  ticket_min_mxn?: number | string;
  ticket_max_mxn?: number | string;
  ciclo_venta_dias?: number | string;
  [k: string]: unknown;
}

/** Configuración derivada del perfil (`POST /company/profile/derive`). */
export interface VerticalConfig {
  vertical_id: string;
  nombre_empresa?: string;
  scian_targets: string[];
  demand_intensity: Record<string, number>;
  scoring_weights: Record<string, number>;
  tam_defaults: TamDefault[];
  line_rules: string[];
  outreach_channels: string[];
  vocabulary: Record<string, string>;
  icp_keywords: string[];
}

export interface AiProviderStatus {
  name: string;
  configured: boolean;
  last_ok?: string | null;
}

export interface AiStatus {
  providers: AiProviderStatus[];
}

export interface AiChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

export interface AiChatReply {
  reply: string;
  tools_used: string[];
}

export interface AiFillResult {
  markdown: string;
  pendientes: string[];
}

/** Lanza ApiError 404 si no existe perfil activo. */
export function getCompanyProfile() {
  return get<CompanyProfile>('/company/profile');
}

/** Guarda (crea versión) el perfil en markdown. */
export function putCompanyProfile(markdown: string) {
  return put<PutCompanyProfileOut>('/company/profile', { markdown });
}

/** Deriva la configuración operativa a partir del markdown del perfil. */
export function deriveCompanyConfig(markdown?: string) {
  return post<VerticalConfig>('/company/profile/derive', markdown === undefined ? {} : { markdown });
}

/** Activa una versión del perfil como la vigente. */
export function activateCompanyProfile(id: string) {
  return post<{ ok?: boolean }>(`/company/profile/activate/${id}`, {});
}

/** Historial de versiones del perfil. */
export function listCompanyProfiles() {
  return get<CompanyProfileSummary[]>('/company/profiles');
}

/** Estado de los providers de IA (configurado / no configurado). */
export function getAiStatus() {
  return get<AiStatus>('/ai/status');
}

/** Chat con el operador interno. 501 si la IA no está configurada. */
export function postAiChat(message: string, history: AiChatMessage[]) {
  return post<AiChatReply>('/ai/chat', { message, history });
}

/** Pide a la IA que llene la plantilla del perfil desde URL, texto o archivo. */
export function postAiFillProfile(payload: { url?: string; text?: string; filename?: string }) {
  return post<AiFillResult>('/ai/fill-profile', payload);
}

/* ---------- Corrección profunda: conteo, comparación y borrado ---------- */

/** Total real de leads curadas Radar (prod.leads). */
export function getLeadsCount(params?: { etapa?: string; linea?: string; source?: string }) {
  return get<{ total: number }>('/leads/count', params ?? {});
}

export interface CompareItem {
  id: string;
  nombre?: string;
  territorio?: string;
  veredicto?: string;
  ism?: number | null;
  tam?: number | null;
  competencia?: number | null;
  poblacion?: number | null;
  huff_score?: number | null;
  [k: string]: unknown;
}

export interface CompareResponse {
  items: CompareItem[];
  lineage?: Lineage | Record<string, unknown> | null;
}

export function compareInvestigations(ids: string[]) {
  return post<CompareResponse>('/analysis/compare', { investigation_ids: ids });
}

export function deleteInvestigation(id: string) {
  return del<void>('/investigations/' + id);
}

/* ---------- Adaptador de leads unificados (tarea E) ---------- */

export interface LeadUnificado {
  origen: 'espacial' | 'radar';
  clave: string;
  nombre: string;
  giro?: string;
  linea?: string;
  etapa?: string;
  score?: number;
  desglose: Record<string, unknown>;
  telefono?: string;
  correo?: string;
  web?: string;
  direccion?: string;
  municipio?: string;
  lat?: number;
  lon?: number;
  temp_zona?: number;
  notas?: string;
  enriquecido_apollo?: boolean;
  crm_synced_at?: string | null;
  lead_id?: number;
  denue_id?: string;
  estrato?: string;
  idt?: number;
  source?: string;
  rating?: number;
  // datos crudos para la ficha
  crudoEspacial?: Lead;
  crudoRadar?: LeadCurado;
}

export function desdeEspacial(l: Lead): LeadUnificado {
  const denueId = l.denue_id ?? l.id ?? '';
  const desglose: Record<string, unknown> = l.score_breakdown ? { ...l.score_breakdown } : {};
  return {
    origen: 'espacial',
    clave: `espacial-${denueId || (l.razon_social ?? l.nombre ?? Math.random().toString(36))}`,
    nombre: l.razon_social ?? l.nombre ?? 'Establecimiento',
    giro: l.scian_desc,
    linea: undefined,
    etapa: undefined,
    score: l.score,
    desglose,
    telefono: l.telefono,
    correo: l.correo,
    web: l.sitio_web,
    direccion: l.direccion,
    municipio: l.municipio,
    lat: l.lat,
    lon: l.lon,
    temp_zona: undefined,
    notas: undefined,
    enriquecido_apollo: undefined,
    crm_synced_at: undefined,
    lead_id: undefined,
    denue_id: denueId || undefined,
    estrato: l.estrato,
    idt: l.idt,
    source: undefined,
    crudoEspacial: l,
  };
}

export function desdeRadar(l: LeadCurado): LeadUnificado {
  const desglose: Record<string, unknown> = l.score_components ? { ...l.score_components } : {};
  return {
    origen: 'radar',
    clave: `radar-${l.lead_id}`,
    nombre: l.nombre,
    giro: l.giro,
    linea: l.linea_recomendada,
    etapa: l.etapa,
    score: l.score,
    desglose,
    telefono: l.telefono,
    correo: undefined,
    web: l.web,
    direccion: l.direccion,
    municipio: undefined,
    lat: l.lat,
    lon: l.lon,
    temp_zona: l.temp_zona,
    notas: l.notas,
    enriquecido_apollo: l.enriquecido_apollo,
    crm_synced_at: l.crm_synced_at,
    lead_id: l.lead_id,
    denue_id: undefined,
    estrato: undefined,
    idt: undefined,
    source: l.source,
    rating: l.rating,
    crudoRadar: l,
  };
}

/**
 * Capa API de la Sección 2 (Radar) — Sección 2 · Frontend worker.
 *
 * TODAS las llamadas nuevas de Panel Radar / Leads / Operación / Sistema /
 * Mapa Radar viven aquí. Reutiliza el helper base de `@/lib/api`
 * (`get`/`post`/`put`, base `/api/v1`, errores en español).
 *
 * Endpoints REALES del backend (verificados en backend/app/api/v1/):
 * - POST /leads/enrich-geo                 (leads.py)
 * - GET  /catalogs/geo-filters             (catalogs.py, cascada)
 * - GET  /leads/curados | /leads/count     (leads.py, filtros geo AND)
 * - GET  /pipelines/runs | POST /pipelines/run/{stage} | GET /pipelines/workflows (pipelines.py)
 * - GET  /providers | PUT /providers/{name} (providers.py — es PUT, no PATCH)
 * - GET  /integrations/linkedin/status | /auth | POST /disconnect (integrations/linkedin.py)
 * - GET  /system/health                    (system.py)
 * - POST /signals                          (signals.py)
 * - GET  /geo/weather                      (geo_weather.py)
 * - GET  /reports/{id} | POST /reports     (reports.py; NO existe GET por investigación)
 */
import * as React from 'react';
import { get, post, put, type LeadCurado, type PipelineRun, type Provider } from '@/lib/api';

/* ------------------------------------------------------------------ geo */

export interface GeoFilters {
  entidades: string[];
  municipios: string[];
  colonias: string[];
  cps: string[];
  scians: string[];
}

export interface GeoSel {
  entidad: string;
  municipio: string;
  colonia: string;
  cp: string;
  scian: string;
}

export const GEO_VACIO: GeoSel = { entidad: '', municipio: '', colonia: '', cp: '', scian: '' };

/** Lead curado con la geografía derivada (migración 0005) ya expuesta por la API. */
export type LeadCuradoGeo = LeadCurado & {
  entidad?: string | null;
  municipio?: string | null;
  colonia?: string | null;
  cp?: string | null;
  scian?: string | null;
  created_at?: string;
  updated_at?: string;
};

export interface EnrichGeoOut {
  actualizados: number;
  pendientes: number;
  detalle: { con_geometria: number; solo_cp: number; sin_datos: number };
}

export type GeoParams = Partial<Record<'entidad' | 'municipio' | 'colonia' | 'cp' | 'scian', string>>;

export function getGeoFilters(sel?: { entidad?: string; municipio?: string; colonia?: string }) {
  return get<GeoFilters>('/catalogs/geo-filters', {
    entidad: sel?.entidad || undefined,
    municipio: sel?.municipio || undefined,
    colonia: sel?.colonia || undefined,
  });
}

export function postEnrichGeo(limite = 500) {
  return post<EnrichGeoOut>('/leads/enrich-geo', { limite });
}

export function getLeadsCountGeo(params?: {
  etapa?: string; linea?: string; source?: string;
} & GeoParams) {
  return get<{ total: number }>('/leads/count', params ?? {});
}

export function getCuradosGeo(params?: {
  etapa?: string; linea?: string; source?: string; limit?: number; cursor?: string;
} & GeoParams) {
  return get<{ items?: LeadCuradoGeo[]; next_cursor?: string | null } | LeadCuradoGeo[]>(
    '/leads/curados', params ?? {},
  );
}

/**
 * Hook de la cascada geográfica Entidad → Municipio → Colonia → CP + SCIAN.
 * Al cambiar un nivel limpia los inferiores y recarga las opciones desde
 * `GET /catalogs/geo-filters` con los niveles superiores como restricción.
 */
export function useGeoFiltros(inicial?: Partial<GeoSel>) {
  const [sel, setSel] = React.useState<GeoSel>({ ...GEO_VACIO, ...(inicial ?? {}) });
  const [opts, setOpts] = React.useState<GeoFilters>({
    entidades: [], municipios: [], colonias: [], cps: [], scians: [],
  });
  const [cargandoOpts, setCargandoOpts] = React.useState(false);
  // Recarga manual de la cascada (botón «actualizar» o tras ETL de geo).
  const [version, setVersion] = React.useState(0);
  // Secuencia para descartar respuestas viejas si el usuario teclea rápido.
  const seq = React.useRef(0);

  const cargarOpts = React.useCallback((base: { entidad?: string; municipio?: string; colonia?: string }) => {
    const id = ++seq.current;
    setCargandoOpts(true);
    getGeoFilters(base)
      .then((data) => { if (id === seq.current) setOpts(data); })
      .catch(() => { /* la cascada es opcional: sin backend, los selects quedan vacíos */ })
      .finally(() => { if (id === seq.current) setCargandoOpts(false); });
  }, []);

  // Un solo efecto: reacciona a los niveles de la cascada con debounce, para
  // que los campos de texto libre (municipio/colonia/CP) no disparen una
  // petición por tecla. Los cambios se aplican sin efectos secundarios
  // dentro del updater de `setSel` (StrictMode hacía doble fetch).
  React.useEffect(() => {
    const t = setTimeout(() => {
      cargarOpts({
        entidad: sel.entidad || undefined,
        municipio: sel.municipio || undefined,
        colonia: sel.colonia || undefined,
      });
    }, 250);
    return () => clearTimeout(t);
  }, [sel.entidad, sel.municipio, sel.colonia, version, cargarOpts]);

  const cambiar = React.useCallback((campo: keyof GeoSel, valor: string) => {
    setSel((prev) => {
      const next: GeoSel = { ...prev, [campo]: valor };
      if (campo === 'entidad') { next.municipio = ''; next.colonia = ''; next.cp = ''; next.scian = ''; }
      if (campo === 'municipio') { next.colonia = ''; next.cp = ''; next.scian = ''; }
      if (campo === 'colonia') { next.cp = ''; next.scian = ''; }
      return next;
    });
  }, []);

  const limpiar = React.useCallback(() => {
    setSel(GEO_VACIO);
  }, []);

  const recargar = React.useCallback(() => {
    setVersion((n) => n + 1);
  }, []);

  const params = React.useMemo<GeoParams>(() => {
    const p: GeoParams = {};
    if (sel.entidad) p.entidad = sel.entidad;
    if (sel.municipio) p.municipio = sel.municipio;
    if (sel.colonia) p.colonia = sel.colonia;
    if (sel.cp) p.cp = sel.cp;
    if (sel.scian) p.scian = sel.scian;
    return p;
  }, [sel]);

  const activo = Object.keys(params).length > 0;

  return { sel, opts, cargandoOpts, cambiar, limpiar, recargar, params, activo };
}

/* -------------------------------------------------------------- pipelines */

export interface WorkflowOut {
  id: string;
  nombre: string;
  descripcion?: string | null;
}

export function getWorkflows() {
  return get<WorkflowOut[] | { items?: WorkflowOut[] }>('/pipelines/workflows');
}

export function getRuns(limit = 100) {
  return get<PipelineRun[] | { items?: PipelineRun[] }>('/pipelines/runs', { limit });
}

export function runsComoArray(r: PipelineRun[] | { items?: PipelineRun[] } | null | undefined): PipelineRun[] {
  if (!r) return [];
  return Array.isArray(r) ? r : (r.items ?? []);
}

/** Desempaca el detalle de una corrida (JSONB) a texto legible, como el original. */
export function detalleRunTexto(detalle: unknown): string {
  if (detalle === null || detalle === undefined) return '—';
  if (typeof detalle === 'string') return detalle;
  if (typeof detalle === 'object') {
    const o = detalle as Record<string, unknown>;
    for (const k of ['error', 'mensaje', 'message', 'nota', 'note']) {
      if (o[k] != null && String(o[k]).trim() !== '') return String(o[k]);
    }
    const partes = Object.entries(o)
      .filter(([, v]) => v !== null && v !== undefined && v !== '')
      .map(([k, v]) => `${k}: ${typeof v === 'object' ? JSON.stringify(v) : String(v)}`);
    return partes.length ? partes.join(' · ') : '—';
  }
  return String(detalle);
}

/* -------------------------------------------------------------- providers */

export function getProviders() {
  return get<Provider[] | { items?: Provider[] }>('/providers');
}

export function providersComoArray(r: Provider[] | { items?: Provider[] } | null | undefined): Provider[] {
  if (!r) return [];
  return Array.isArray(r) ? r : (r.items ?? []);
}

/** Actualiza un provider. El backend expone PUT /providers/{name} (no PATCH). */
export function putProvider(name: string, body: { mode?: string; provider?: string; config?: Record<string, unknown>; enabled?: boolean }) {
  return put<Provider>(`/providers/${name}`, body);
}

/* --------------------------------------------------------------- linkedin */

/** Estado real de GET /integrations/linkedin/status en este backend. */
export interface LinkedInStatusReal {
  connected?: boolean;
  conectado?: boolean;
  scopes_requeridos?: string[];
  nota?: string;
  // Campos del dashboard original que este backend podría exponer a futuro:
  expirado?: boolean;
  expira?: string | null;
  org_id?: string | null;
  tieneClientId?: boolean;
  tieneClientSecret?: boolean;
  stats?: Record<string, unknown>[];
  warmSignals?: Record<string, unknown>[];
  [k: string]: unknown;
}

export function getLinkedInStatus() {
  return get<LinkedInStatusReal>('/integrations/linkedin/status');
}

export function getLinkedInAuth() {
  return get<{ auth_url?: string; url?: string; scopes?: string[] }>('/integrations/linkedin/auth');
}

export function postLinkedInDisconnect() {
  return post<{ connected?: boolean; nota?: string }>('/integrations/linkedin/disconnect');
}

/** ¿El status reporta el token como expirado? (solo si el backend lo expone). */
export function linkedinExpirado(li: LinkedInStatusReal | null | undefined): boolean {
  if (!li) return false;
  return li.expirado === true || (li as Record<string, unknown>).expired === true;
}

/* ---------------------------------------------------------------- señales */

export function postSignal(payload: { titulo: string; detalle?: string; empresa_ref?: string; fuente?: string }) {
  return post('/signals', payload);
}

/* ------------------------------------------------------------------ clima */

export interface WeatherOut {
  lat: number;
  lon: number;
  temperature_c?: number | null;
  fetched_at?: string;
  cached?: boolean;
}

export function getWeather(lat: number, lon: number) {
  return get<WeatherOut>('/geo/weather', { lat, lon });
}

/* --------------------------------------------------------------- reportes */

export interface AtractorItem {
  nombre?: string;
  categoria?: string;
  categoria_etiqueta?: string;
  distancia_m?: number;
  url_maps?: string;
}

export interface IsocronaItem {
  modo?: string;
  minutos?: number;
  geometria?: GeoJSON.Polygon | GeoJSON.MultiPolygon | null;
  poblacion?: number | null;
  competidores?: number | null;
  [k: string]: unknown;
}

export interface ReporteParaMapa {
  report_id?: string;
  title?: string;
  verdict?: string | null;
  payload?: {
    atractores_trafico?: { items?: AtractorItem[] };
    area_alcance_tiempo?: { isocronas?: IsocronaItem[]; alcance_tipo?: string };
    mapas?: { centro?: { lat?: number; lon?: number } };
    [k: string]: unknown;
  };
}

/** GET /reports/{report_id} — único GET de reporte por id que existe. */
export function getReporte(id: string) {
  return get<ReporteParaMapa>(`/reports/${id}`);
}

/** POST /reports — genera (y persiste) el reporte de una investigación. */
export function postReporte(body: {
  investigation_id?: string; title?: string; giro?: string; scian?: string;
  lat?: number; lon?: number; radios?: number[];
}) {
  return post<ReporteParaMapa>('/reports', body);
}

/** Extrae lat/lon de la URL de Maps de un atractor (`query=lat,lon`). */
export function coordsDeUrlMaps(url?: string): [number, number] | null {
  if (!url) return null;
  const m = url.match(/query=(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)/);
  if (!m) return null;
  const lat = Number(m[1]);
  const lon = Number(m[2]);
  return Number.isFinite(lat) && Number.isFinite(lon) ? [lat, lon] : null;
}

/* ------------------------------------------------- contacto (inventario) */

/**
 * Normalización de teléfono MX (inventario Radar #95, `normPhone`):
 * quita no-dígitos; 10 dígitos → prefijo 52; 12 que empiezan en 52 → tal
 * cual; 11 que empiezan en 1 → tal cual; ≥10 → tal cual; <10 → null.
 */
export function normPhone(tel?: string | null): string | null {
  const d = (tel ?? '').replace(/\D/g, '');
  if (!d) return null;
  if (d.length === 10) return `52${d}`;
  if (d.length === 12 && d.startsWith('52')) return d;
  if (d.length === 11 && d.startsWith('1')) return d;
  if (d.length >= 10) return d;
  return null;
}

/** Normalización de URL de sitio (inventario #96): agrega https:// si falta. */
export function normWeb(web?: string | null): string | null {
  const w = (web ?? '').trim();
  if (!w) return null;
  return /^https?:\/\//i.test(w) ? w : `https://${w}`;
}

/**
 * «Por qué este lead» (inventario Radar #97, `whyLinea`):
 * solar = temporada de planeación oct–feb y giro apto (regex con `super`);
 * koolkat = temporada de calor feb–jun / control térmico industrial;
 * evaporativa = confort todo el año.
 */
export function whyLinea(giro: string | undefined | null, linea: string | undefined | null): string {
  const g = (giro ?? '').toLowerCase();
  const l = (linea ?? '').toLowerCase();
  const mes = new Date().getMonth(); // 0 = enero
  if (l === 'solar') {
    const apto = /gasolin|estacionamiento|comercial|plaza|tienda|super/.test(g);
    const temporada = mes >= 9 || mes <= 1
      ? 'Estamos en temporada de planeación solar (oct–feb): el cliente define su capex de invierno.'
      : 'La temporada fuerte de planeación solar es oct–feb; el resto del año se siembra la propuesta.';
    return apto
      ? `${temporada} Su giro tiene superficies al aire libre amplias: tu sombra genera — los canopies dan sombra a clientes y autos mientras producen electricidad.`
      : `${temporada} Se le recomienda Solar por su superficie y consumo eléctrico relevante.`;
  }
  if (l === 'koolkat') {
    const temporada = mes >= 1 && mes <= 5
      ? 'Estamos en temporada de calor (feb–jun): la urgencia térmica es máxima y el ángulo es bajar el OPEX eléctrico.'
      : 'Fuera de temporada de calor (feb–jun) se prepara la propuesta; el ángulo es bajar el OPEX eléctrico.';
    return `${temporada} Koolkat es control térmico industrial: baja la temperatura de naves y CEDIS sin el costo de un aire acondicionado tradicional.`;
  }
  if (l === 'evaporativa') {
    return 'La bioclimatización evaporativa funciona todo el año: confort y productividad con aire fresco y sin obra mayor. Es la línea recomendada para este giro y su zona.';
  }
  return 'Línea aún sin recomendar: la etapa 02 (Dedup + score) asigna Koolkat, Solar o Evaporativa según el mes, el giro y la temperatura de la zona.';
}

import * as React from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { MapContainer, TileLayer, CircleMarker, Marker, Popup, GeoJSON, Circle } from 'react-leaflet';
import L from 'leaflet';
import { Topbar } from '@/components/layout/Topbar';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Field } from '@/components/ui/Field';
import { Spinner } from '@/components/ui/Spinner';
import { Empty } from '@/components/ui/Empty';
import { Badge } from '@/components/ui/Badge';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/Accordion';
import { Separator } from '@/components/ui/Separator';
import { CodeBlock } from '@/components/ui/CodeBlock';
import { Chart } from '@/components/ui/Chart';
import { EstimadoBadge } from '@/components/ui/Estimado';
import { MapaExpandible } from '@/components/map/MapaExpandible';
import {
  get, geocode, createReport, getReport, getInvestigation, createReportShare, revokeReportShare,
  errorMessage, type ReportOutS1,
} from '@/lib/api';
import { verdictColor } from '@/lib/geo';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';

/* ================= Tipos del payload (builder.py + context.py) ================= */

export interface Segmento { segmento?: string; poblacion?: number; pct?: number | null }
export interface Competidor { nombre?: string; distancia_m?: number; estado?: string; is_active?: boolean; url_maps?: string; lat?: number; lon?: number }
export interface Atractor { nombre?: string; categoria?: string; categoria_etiqueta?: string; distancia_m?: number; url_maps?: string; lat?: number; lon?: number }
export interface CategoriaEntorno { categoria?: string; etiqueta?: string; conteo?: number; ejemplos?: string[] }
export interface Ancla { nombre?: string; tipo?: string; etiqueta?: string; w?: number; radio_m?: number; distancia_m?: number | null }
export interface Isocrona { modo?: string; modo_real?: string; minutos?: number; poblacion?: number | null; competidores?: number | null; geometria?: GeoJSON.Geometry | null }
export interface Vialidad { nombre?: string; tipo?: string; distancia_m?: number; tiempo_auto_min?: number | null }
export interface MovilidadBloque { rango?: number[]; rango_vehiculos_dia?: number[]; rango_personas_dia?: number[]; etiqueta?: string; nivel?: number; estimado?: boolean; metodo?: string }
export interface FuenteDato { fuente?: string; rol?: string }

export interface ReportPayloadFull {
  cabecera?: { etiqueta?: string; titulo?: string; empresa?: string; giro?: string; scian?: string; ubicacion?: string; lat?: number; lon?: number; fecha?: string; radios_m?: number[] };
  veredicto?: { decision?: string; confianza?: string; factores?: string[]; riesgos?: string[] };
  perfil_cliente?: { editorial?: string | null; estado?: string; nota?: string };
  clientes_zona?: { nota?: string; segmentos?: Segmento[]; poblacion_total?: number | null; poblacion_objetivo?: number | null };
  hogares_familias?: { viviendas_habitadas?: number | null; promedio_ocupantes?: number | null; pct_internet?: number | null; pct_computadora?: number | null; pct_automovil?: number | null };
  atractores_trafico?: { nota?: string; items?: Atractor[] };
  competencia?: { por_anillo?: { radio_m?: number; conteo?: number; ism?: number; ism_banda?: string }[]; lista?: Competidor[]; anillo_exterior?: number | null };
  mapas?: { capas?: string[]; centro?: { lat?: number; lon?: number } };
  entorno_comercial?: { total_negocios?: number | null; categorias?: CategoriaEntorno[]; radio_m?: number; solo_activos?: boolean; nota?: string };
  poblacion_viviendas?: { advertencia?: string; detalle?: { grupos_edad?: Record<string, number>; por_sexo?: Record<string, number>; pea_ocupada?: number; radio_m?: number }; viviendas?: Record<string, unknown> };
  movimiento_acceso?: { nse_etiqueta?: string | null; nse_nota?: string; vialidades?: Vialidad[]; movilidad?: { vehicular?: MovilidadBloque; peatonal?: MovilidadBloque; actividad?: { pea_ocupada?: number | null; pct_sobre_pob_15_mas?: number | null; nota?: string } } };
  area_alcance_tiempo?: { alcance_tipo?: 'isocronas' | 'radios' | string; isocronas?: Isocrona[]; como_usarla?: string };
  datos_sector?: { giro?: string; scian?: string[] | string; ticket_promedio?: number | null; hora_pico?: string; delivery_pct?: number | null; top_productos?: string[]; fuente?: string };
  delivery?: { aplica?: boolean; radio_inicial_km?: number[] | number; tiempo_objetivo_min?: number[] | number; delivery_pct?: number | null; nota?: string };
  punto_equilibrio?: { costos_fijos?: Record<string, number>; costos_variables?: Record<string, number>; total_costos_fijos?: number; total_costos_variables?: number; margen_contribucion?: number; ventas_equilibrio_mensual?: number; formula?: string; renta_formula?: string };
  negocios_ancla?: { nota?: string; items?: Ancla[] };
  modelos?: {
    ism?: { formula?: string; por_anillo?: { radio_m?: number; D?: number; O?: number; ISM?: number; banda?: string }[] };
    huff?: { formula?: string; cuota_punto?: number; rango_cuota?: unknown; alpha?: number; lambda?: number };
    tam?: { formula?: string; tam_mxn_anual?: number; rango_mxn?: number[]; advertencia?: string; supuestos?: string[] };
  };
  fuentes_datos?: { fuentes?: (FuenteDato | string)[]; ediciones?: unknown[]; fecha_calculo?: string; model_version?: string };
  metodologia_advertencias?: { estimado_vs_observado?: string[]; nota_general?: string };
  plan_contacto?: unknown;
}

/* ================= Utilidades ================= */

export const mxn = (v?: number | null) =>
  typeof v === 'number'
    ? new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN', maximumFractionDigits: 0 }).format(v)
    : '—';

export const fmtNum = (v?: number | null) => (typeof v === 'number' ? v.toLocaleString('es-MX') : '—');

export function fmtDist(m?: number | null): string {
  if (typeof m !== 'number') return '—';
  if (m < 1000) return `${Math.round(m)} m`;
  return `${(m / 1000).toFixed(2).replace(/\.?0+$/, '')} km`;
}

/** Coordenadas de un ítem: campos lat/lon o las embebidas en su URL de Maps (query=lat,lon). */
export function coordsDe(item: { lat?: number; lon?: number; url_maps?: string }): [number, number] | null {
  if (typeof item.lat === 'number' && typeof item.lon === 'number') return [item.lat, item.lon];
  if (item.url_maps) {
    const m = item.url_maps.match(/query=(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)/);
    if (m) return [Number(m[1]), Number(m[2])];
  }
  return null;
}

function iconoNumerado(n: number, color: string): L.DivIcon {
  return L.divIcon({
    className: 'geis-marker-num',
    html: `<span style="display:flex;align-items:center;justify-content:center;width:24px;height:24px;border-radius:9999px;background:${color};color:#fff;font-size:12px;font-weight:700;border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.4)">${n}</span>`,
    iconSize: [24, 24],
    iconAnchor: [12, 12],
  });
}

function iconoCentro(): L.DivIcon {
  return L.divIcon({
    className: 'geis-marker-centro',
    html: `<span style="display:flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:9999px;background:#111827;color:#fff;font-size:15px;border:2px solid #fff;box-shadow:0 1px 5px rgba(0,0,0,.5)">★</span>`,
    iconSize: [28, 28],
    iconAnchor: [14, 14],
  });
}

const PALETA_CATEGORIAS = ['#0E5FD8', '#E8590C', '#2F9E44', '#9333EA', '#E8A13D', '#0EA5A4', '#D64545', '#64748B', '#B45309', '#2563EB'];
function colorCategoria(cat: string | undefined, idx: number): string {
  if (idx >= 0 && idx < PALETA_CATEGORIAS.length) return PALETA_CATEGORIAS[idx];
  let h = 0;
  for (const c of cat ?? '') h = (h * 31 + c.charCodeAt(0)) % 360;
  return `hsl(${h} 65% 45%)`;
}

function rangoTexto(r?: number[]): string | null {
  if (!r || r.length === 0) return null;
  if (r.length === 1) return fmtNum(r[0]);
  return `${fmtNum(r[0])} – ${fmtNum(r[1])}`;
}

function AprendeLink({ ancla, texto = '¿qué es esto?' }: { ancla: string; texto?: string }) {
  return (
    <Link to={`/aprende#${ancla}`} className="text-xs font-medium text-primary hover:underline">
      {texto} →
    </Link>
  );
}

function Bloque({ titulo, extra, children }: { titulo: string; extra?: React.ReactNode; children: React.ReactNode }) {
  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle>{titulo}</CardTitle>
          {extra}
        </div>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

function SinDatos({ texto = 'Dato no disponible en este reporte.' }: { texto?: string }) {
  return <p className="text-sm text-muted-foreground">{texto}</p>;
}

/* ================= Calculadoras ================= */

function CalculadoraRenta({ interactivo }: { interactivo: boolean }) {
  const [precio, setPrecio] = React.useState('');
  const [superficie, setSuperficie] = React.useState('');
  const p = Number(precio);
  const s = Number(superficie);
  const renta = precio !== '' && superficie !== '' && p > 0 && s > 0 ? p * s : null;
  if (!interactivo) {
    return <p className="text-sm text-muted-foreground">Renta mensual = precio por m² × superficie (m²). Calculadora interactiva en la vista en pantalla del reporte.</p>;
  }
  return (
    <div className="space-y-3">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Precio por m² (MXN/mes)" htmlFor="calc-precio">
          <Input id="calc-precio" type="number" min="0" step="any" placeholder="Ej. 250" value={precio} onChange={(e) => setPrecio(e.target.value)} />
        </Field>
        <Field label="Superficie del local (m²)" htmlFor="calc-superficie">
          <Input id="calc-superficie" type="number" min="0" step="any" placeholder="Ej. 60" value={superficie} onChange={(e) => setSuperficie(e.target.value)} />
        </Field>
      </div>
      <p className="text-sm">
        Renta mensual estimada: <strong className="font-mono text-lg">{renta !== null ? mxn(renta) : '—'}</strong>
        <span className="ml-2 text-xs text-muted-foreground">precio/m² × superficie (§3.12.1)</span>
      </p>
    </div>
  );
}

const ETIQUETAS_COSTO: Record<string, string> = {
  nomina: 'Nómina', renta: 'Renta', servicios: 'Servicios', contador: 'Contador',
  impuestos: 'Impuestos', insumos: 'Insumos', mantenimiento: 'Mantenimiento', imprevistos: 'Imprevistos',
};

function CalculadoraEquilibrio({ data, interactivo }: { data: NonNullable<ReportPayloadFull['punto_equilibrio']>; interactivo: boolean }) {
  const iniciales = React.useMemo(() => ({ ...(data.costos_fijos ?? {}) }), [data]);
  const [costos, setCostos] = React.useState<Record<string, string>>(() =>
    Object.fromEntries(Object.entries(iniciales).map(([k, v]) => [k, String(v)])),
  );
  const [margenTxt, setMargenTxt] = React.useState(String(data.margen_contribucion ?? ''));
  React.useEffect(() => {
    setCostos(Object.fromEntries(Object.entries(iniciales).map(([k, v]) => [k, String(v)])));
    setMargenTxt(String(data.margen_contribucion ?? ''));
  }, [iniciales, data.margen_contribucion]);

  const total = Object.values(costos).reduce((acc, v) => acc + (Number(v) || 0), 0);
  const margen = Number(margenTxt);
  const ventas = margen > 0 ? total / margen : null;

  if (!interactivo) {
    return (
      <div className="space-y-2 text-sm">
        <dl className="grid gap-1 sm:grid-cols-2">
          {Object.entries(data.costos_fijos ?? {}).map(([k, v]) => (
            <div key={k} className="flex justify-between border-b py-1"><dt className="text-muted-foreground">{ETIQUETAS_COSTO[k] ?? etiqueta(k)}</dt><dd className="font-mono">{mxn(v)}</dd></div>
          ))}
        </dl>
        <p>Total de costos fijos: <strong className="font-mono">{mxn(data.total_costos_fijos)}</strong> · Margen de contribución: <strong className="font-mono">{data.margen_contribucion ?? '—'}</strong></p>
        {data.costos_variables && Object.keys(data.costos_variables).length > 0 && (
          <p className="text-xs text-muted-foreground">
            Costos variables (ya incluidos en el margen de contribución):{' '}
            {Object.entries(data.costos_variables).map(([k, v]) => `${ETIQUETAS_COSTO[k] ?? etiqueta(k)} ${mxn(v)}`).join(' · ')}
          </p>
        )}
        <p>Ventas de equilibrio mensual: <strong className="font-mono text-base">{mxn(data.ventas_equilibrio_mensual)}</strong></p>
      </div>
    );
  }
  return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">Plantilla del giro, precargada desde el reporte. Edita cualquier costo o el margen y el equilibrio se recalcula en vivo: ventas = costos fijos ÷ margen.</p>
      <div className="grid gap-3 sm:grid-cols-2">
        {Object.entries(costos).map(([k, v]) => (
          <Field key={k} label={`${ETIQUETAS_COSTO[k] ?? etiqueta(k)} (MXN/mes)`} htmlFor={`costo-${k}`}>
            <Input id={`costo-${k}`} type="number" min="0" step="any" value={v} onChange={(e) => setCostos((c) => ({ ...c, [k]: e.target.value }))} />
          </Field>
        ))}
        <Field label="Margen de contribución (0–1)" htmlFor="costo-margen">
          <Input id="costo-margen" type="number" min="0" max="1" step="0.01" value={margenTxt} onChange={(e) => setMargenTxt(e.target.value)} />
        </Field>
      </div>
      {data.costos_variables && Object.keys(data.costos_variables).length > 0 && (
        <p className="text-xs text-muted-foreground">
          Costo variable de referencia (no se suma a los fijos; ya está en el margen):{' '}
          {Object.entries(data.costos_variables).map(([k, v]) => `${ETIQUETAS_COSTO[k] ?? etiqueta(k)} ${mxn(v)}`).join(' · ')}
        </p>
      )}
      <p className="text-sm">
        Total de costos fijos: <strong className="font-mono">{mxn(total)}</strong> · Ventas de equilibrio mensual:{' '}
        <strong className="font-mono text-lg">{ventas !== null ? mxn(ventas) : '—'}</strong>
        {margen <= 0 && <span className="ml-2 text-xs text-destructive">El margen debe ser mayor que 0.</span>}
      </p>
    </div>
  );
}

/** snake_case → etiqueta legible. */
export function etiqueta(k: string): string {
  return k.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase());
}

function RenderGenerico({ contenido }: { contenido: unknown }) {
  if (contenido === null || contenido === undefined) return null;
  if (typeof contenido === 'string') return <p className="whitespace-pre-line text-sm leading-relaxed">{contenido}</p>;
  if (Array.isArray(contenido)) {
    if (contenido.length === 0) return <SinDatos />;
    return (
      <ul className="list-disc space-y-1 pl-5 text-sm">
        {contenido.map((it, i) => (
          <li key={i}>{typeof it === 'object' ? Object.entries(it as Record<string, unknown>).map(([k, v]) => `${etiqueta(k)}: ${typeof v === 'object' ? JSON.stringify(v) : String(v)}`).join(' · ') : String(it)}</li>
        ))}
      </ul>
    );
  }
  if (typeof contenido === 'object') {
    const entries = Object.entries(contenido as Record<string, unknown>).filter(([, v]) => v !== null && v !== undefined);
    if (entries.length === 0) return <SinDatos />;
    return (
      <dl className="space-y-1.5 text-sm">
        {entries.map(([k, v]) => (
          <div key={k} className="flex justify-between gap-4 border-b py-1 last:border-0">
            <dt className="text-muted-foreground">{etiqueta(k)}</dt>
            <dd className="text-right font-medium">{typeof v === 'object' ? JSON.stringify(v) : String(v)}</dd>
          </div>
        ))}
      </dl>
    );
  }
  return <p className="text-sm">{String(contenido)}</p>;
}

/* ================= Mapas del reporte ================= */

function MapaCompetencia({ centro, lista }: { centro: [number, number]; lista: Competidor[] }) {
  const conCoords = lista.map((c, i) => ({ c, n: i + 1, coords: coordsDe(c) })).filter((x) => x.coords) as { c: Competidor; n: number; coords: [number, number] }[];
  return (
    <MapaExpandible titulo="Competencia en la zona">
      <div className="mapa-lienzo h-72 w-full overflow-hidden rounded-lg border">
        <MapContainer center={centro} zoom={14} className="h-full w-full" style={{ height: '100%' }}>
          <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
          <Circle center={centro} radius={1000} pathOptions={{ color: '#D64545', weight: 1.5, fillOpacity: 0.04, dashArray: '6 4' }} />
          <Circle center={centro} radius={2000} pathOptions={{ color: '#E8A13D', weight: 1.5, fillOpacity: 0.02, dashArray: '6 4' }} />
          <Marker position={centro} icon={iconoCentro()}>
            <Popup><p className="text-sm font-semibold">Punto analizado</p></Popup>
          </Marker>
          {conCoords.map(({ c, n, coords }) => (
            <Marker key={n} position={coords} icon={iconoNumerado(n, (c.distancia_m ?? 0) <= 1000 ? '#D64545' : '#E8A13D')}>
              <Popup>
                <div className="text-sm">
                  <p className="font-semibold">{n}. {c.nombre ?? 'Competidor'}</p>
                  <p className="text-xs text-muted-foreground">A {fmtDist(c.distancia_m)} · {c.estado ?? ''}</p>
                </div>
              </Popup>
            </Marker>
          ))}
        </MapContainer>
      </div>
      <p className="mt-2 flex flex-wrap gap-4 text-xs text-muted-foreground">
        <span><span className="mr-1 inline-block h-2.5 w-2.5 rounded-full" style={{ background: '#111827' }} /> Punto analizado</span>
        <span><span className="mr-1 inline-block h-2.5 w-2.5 rounded-full" style={{ background: '#D64545' }} /> Competidor ≤ 1 km</span>
        <span><span className="mr-1 inline-block h-2.5 w-2.5 rounded-full" style={{ background: '#E8A13D' }} /> Competidor 1–2 km</span>
        <span>Los números corresponden a la lista de competencia.</span>
      </p>
      {conCoords.length < lista.length && (
        <p className="mt-1 text-xs text-muted-foreground">Nota: {lista.length - conCoords.length} competidor(es) sin coordenadas en el payload no se dibujan en el mapa (sí aparecen en la lista).</p>
      )}
    </MapaExpandible>
  );
}

const CATEGORIAS_9: { id: string; etiqueta: string }[] = [
  { id: 'similares', etiqueta: 'Similares (mismo giro)' },
  { id: 'restaurantes', etiqueta: 'Restaurantes, cafés y pastelerías' },
  { id: 'compras_diarias', etiqueta: 'Compras y servicios diarios' },
  { id: 'salud', etiqueta: 'Hospitales y farmacias' },
  { id: 'educacion', etiqueta: 'Escuelas y universidades' },
  { id: 'bancos', etiqueta: 'Bancos' },
  { id: 'gimnasios', etiqueta: 'Gimnasios' },
  { id: 'especializados', etiqueta: 'Servicios especializados' },
  { id: 'plazas_gasolineras', etiqueta: 'Plazas y gasolineras' },
];

function MapaAtractores({ centro, items }: { centro: [number, number]; items: Atractor[] }) {
  const [activas, setActivas] = React.useState<Set<string> | null>(null);
  const presentes = React.useMemo(() => {
    const s = new Set<string>();
    for (const it of items) if (it.categoria) s.add(it.categoria);
    return s;
  }, [items]);
  const visibles = items.filter((it) => !it.categoria || (activas === null || activas.has(it.categoria)));
  const toggle = (cat: string) => {
    setActivas((prev) => {
      const base = prev ?? new Set(presentes);
      const next = new Set(base);
      if (next.has(cat)) next.delete(cat); else next.add(cat);
      return next;
    });
  };
  return (
    <MapaExpandible titulo="Atractores de tráfico">
      <div className="mb-2 flex flex-wrap gap-1.5">
        {CATEGORIAS_9.map((cat, i) => {
          const tiene = presentes.has(cat.id);
          const activa = tiene && (activas === null || activas.has(cat.id));
          return (
            <button
              key={cat.id}
              type="button"
              disabled={!tiene}
              onClick={() => toggle(cat.id)}
              className={cn('rounded-full border px-2.5 py-1 text-xs font-medium transition-colors', !tiene && 'cursor-not-allowed opacity-40', tiene && activa && 'text-white', tiene && !activa && 'bg-muted text-muted-foreground')}
              style={tiene && activa ? { backgroundColor: colorCategoria(cat.id, i), borderColor: colorCategoria(cat.id, i) } : undefined}
              title={tiene ? 'Activar / desactivar categoría' : 'Sin atractores de esta categoría en el payload'}
            >
              <span className="mr-1 inline-block h-2 w-2 rounded-full" style={{ background: colorCategoria(cat.id, i) }} />
              {cat.etiqueta}
            </button>
          );
        })}
      </div>
      <div className="mapa-lienzo h-72 w-full overflow-hidden rounded-lg border">
        <MapContainer center={centro} zoom={14} className="h-full w-full" style={{ height: '100%' }}>
          <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
          <Marker position={centro} icon={iconoCentro()}>
            <Popup><p className="text-sm font-semibold">Punto analizado</p></Popup>
          </Marker>
          {visibles.map((it, i) => {
            const coords = coordsDe(it);
            if (!coords) return null;
            const idxCat = CATEGORIAS_9.findIndex((c) => c.id === it.categoria);
            return (
              <CircleMarker key={i} center={coords} radius={7} pathOptions={{ color: '#fff', weight: 1.5, fillColor: colorCategoria(it.categoria, idxCat), fillOpacity: 0.95 }}>
                <Popup>
                  <div className="text-sm">
                    <p className="font-semibold">{it.nombre ?? 'Atractor'}</p>
                    <p className="text-xs text-muted-foreground">{it.categoria_etiqueta ?? it.categoria ?? ''} · a {fmtDist(it.distancia_m)}</p>
                  </div>
                </Popup>
              </CircleMarker>
            );
          })}
        </MapContainer>
      </div>
    </MapaExpandible>
  );
}

function MapaIsocronas({ centro, isocronas }: { centro: [number, number]; isocronas: Isocrona[] }) {
  const [sel, setSel] = React.useState(0);
  const iso = isocronas[Math.min(sel, Math.max(0, isocronas.length - 1))];
  return (
    <MapaExpandible titulo="Área de alcance por tiempo">
      <div className="mb-2 flex flex-wrap gap-1.5">
        {isocronas.map((it, i) => (
          <Button key={i} size="sm" variant={i === sel ? 'default' : 'outline'} onClick={() => setSel(i)}>
            {etiquetaModo(it)} · {it.minutos ?? '—'} min
          </Button>
        ))}
      </div>
      <div className="mapa-lienzo h-72 w-full overflow-hidden rounded-lg border">
        <MapContainer center={centro} zoom={13} className="h-full w-full" style={{ height: '100%' }}>
          <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
          {iso?.geometria && (
            <GeoJSON key={`${sel}-${iso.modo}-${iso.minutos}`} data={iso.geometria} pathOptions={{ color: '#0E5FD8', weight: 2, fillColor: '#0E5FD8', fillOpacity: 0.15 }} />
          )}
          <Marker position={centro} icon={iconoCentro()}>
            <Popup><p className="text-sm font-semibold">Punto analizado</p></Popup>
          </Marker>
        </MapContainer>
      </div>
      {iso && iso.modo_real && iso.modo && iso.modo_real !== iso.modo && (
        <p className="mt-2 text-xs text-muted-foreground">El servicio de ruteo no ofreció «{iso.modo}»; el polígono se calculó con el modo real «{iso.modo_real}».</p>
      )}
      {!iso?.geometria && <p className="mt-2 text-xs text-muted-foreground">La isócrona seleccionada no trae geometría en el payload; la tabla siguiente conserva sus cifras.</p>}
    </MapaExpandible>
  );
}

function etiquetaModo(iso: Isocrona): string {
  const m = (iso.modo ?? '').toLowerCase();
  if (m.includes('peat') || m.includes('camin') || m.includes('pedestrian') || m.includes('walk')) return 'Caminando';
  if (m.includes('moto') || m.includes('bicycle') || m.includes('bici')) return 'Moto';
  if (m.includes('auto') || m.includes('car') || m.includes('driv')) return 'Auto';
  return iso.modo ?? 'Modo';
}

/* ================= Cuerpo completo del reporte ================= */

export interface ReporteCuerpoProps {
  payload: ReportPayloadFull;
  /** true en pantalla (calculadoras y mapas interactivos); false en impresión / vista compartida. */
  interactivo?: boolean;
  /** Modo inmobiliario (investigación real_estate): prioriza entorno/anclas/vialidades y oculta bloques operativos. */
  modoInmobiliario?: boolean;
  /** Botones de cabecera (WhatsApp / PDF / link invitado) que inyecta la página. */
  acciones?: React.ReactNode;
}

export function ReporteCuerpo({ payload, interactivo = true, modoInmobiliario = false, acciones }: ReporteCuerpoProps) {
  const cab = payload.cabecera;
  const ver = payload.veredicto;
  const decision = ver?.decision ?? 'Sin veredicto';
  const centro: [number, number] | null =
    typeof cab?.lat === 'number' && typeof cab?.lon === 'number'
      ? [cab.lat, cab.lon]
      : typeof payload.mapas?.centro?.lat === 'number' && typeof payload.mapas?.centro?.lon === 'number'
        ? [payload.mapas.centro.lat, payload.mapas.centro.lon]
        : null;

  const comp = payload.competencia;
  const listaComp = comp?.lista ?? [];
  const atractores = payload.atractores_trafico?.items ?? [];
  const categorias = payload.entorno_comercial?.categorias ?? [];
  const segmentos = payload.clientes_zona?.segmentos ?? [];
  const hogares = payload.hogares_familias;
  const mov = payload.movimiento_acceso;
  const movilidad = mov?.movilidad;
  const alcance = payload.area_alcance_tiempo;
  const esIsocronas = alcance?.alcance_tipo === 'isocronas' && (alcance?.isocronas?.length ?? 0) > 0;
  const anclas = payload.negocios_ancla?.items ?? [];
  const detalle = payload.poblacion_viviendas?.detalle;
  const gruposEdad = detalle?.grupos_edad ?? {};
  const maxEdad = Math.max(1, ...Object.values(gruposEdad));
  const fuentes = payload.fuentes_datos?.fuentes ?? [];

  const bloques: { key: string; node: React.ReactNode }[] = [];

  // ── Perfil del cliente (editorial) ────────────────────────────────
  if (payload.perfil_cliente?.editorial) {
    bloques.push({
      key: 'perfil',
      node: (
        <Bloque titulo="Perfil del cliente">
          <p className="whitespace-pre-line text-sm leading-relaxed">{payload.perfil_cliente.editorial}</p>
        </Bloque>
      ),
    });
  }

  // ── Competencia ───────────────────────────────────────────────────
  bloques.push({
    key: 'competencia',
    node: (
      <Bloque titulo="Competencia en la zona" extra={<AprendeLink ancla="competencia" />}>
        <div className="space-y-4">
          {centro && listaComp.length > 0 && interactivo && <MapaCompetencia centro={centro} lista={listaComp} />}
          {comp?.por_anillo && comp.por_anillo.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead><tr className="border-b text-left text-xs uppercase tracking-wider text-muted-foreground">
                  <th className="py-2 pr-4">Radio</th><th className="py-2 pr-4">Competidores</th><th className="py-2 pr-4">ISM <EstimadoBadge /></th><th className="py-2">Banda</th>
                </tr></thead>
                <tbody>
                  {comp.por_anillo.map((a, i) => (
                    <tr key={i} className="border-b last:border-0">
                      <td className="py-2 pr-4 font-mono">{a.radio_m ?? '—'} m</td>
                      <td className="py-2 pr-4 font-mono">{a.conteo ?? '—'}</td>
                      <td className="py-2 pr-4 font-mono">{typeof a.ism === 'number' ? a.ism.toFixed(2) : '—'}</td>
                      <td className="py-2">{a.ism_banda ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <SinDatos texto="Sin conteo de competencia por anillo en este reporte." />}
          {typeof comp?.anillo_exterior === 'number' && (
            <Alert variant="info">
              <AlertDescription>
                Anillo exterior (entre el radio menor y el mayor): <strong>{comp.anillo_exterior} competidor(es)</strong> adicionales. Es el diferencial entre ambos radios, no el acumulado.
              </AlertDescription>
            </Alert>
          )}
          {listaComp.length > 0 ? (
            <ol className="space-y-1.5">
              {listaComp.map((c, i) => (
                <li key={i} className="flex flex-wrap items-center gap-2 rounded-md border px-3 py-2 text-sm">
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white" style={{ background: (c.distancia_m ?? 0) <= 1000 ? '#D64545' : '#E8A13D' }}>{i + 1}</span>
                  <span className="min-w-0 flex-1 font-medium">{c.nombre ?? 'Competidor'}</span>
                  <span className="font-mono text-xs text-muted-foreground">{fmtDist(c.distancia_m)}</span>
                  {c.estado && <Badge variant={c.is_active === false ? 'secondary' : 'success'}>{c.estado}</Badge>}
                  {c.url_maps && <a href={c.url_maps} target="_blank" rel="noreferrer" className="text-xs font-medium text-primary hover:underline">Maps ↗</a>}
                </li>
              ))}
            </ol>
          ) : <SinDatos texto="El payload no trae la lista nominal de competidores (solo el conteo por anillo)." />}
        </div>
      </Bloque>
    ),
  });

  // ── Atractores ────────────────────────────────────────────────────
  bloques.push({
    key: 'atractores',
    node: (
      <Bloque titulo="Atractores de tráfico">
        <div className="space-y-4">
          {payload.atractores_trafico?.nota && <Alert variant="info"><AlertDescription>{payload.atractores_trafico.nota}</AlertDescription></Alert>}
          {atractores.length > 0 ? (
            <>
              {centro && interactivo && <MapaAtractores centro={centro} items={atractores} />}
              <ol className="space-y-1.5">
                {atractores.map((a, i) => (
                  <li key={i} className="flex flex-wrap items-center gap-2 rounded-md border px-3 py-2 text-sm">
                    <span className="w-6 shrink-0 text-center font-mono text-xs text-muted-foreground">{i + 1}</span>
                    <span className="min-w-0 flex-1 font-medium">{a.nombre ?? 'Atractor'}</span>
                    {(a.categoria_etiqueta ?? a.categoria) && <Badge variant="outline">{a.categoria_etiqueta ?? a.categoria}</Badge>}
                    <span className="font-mono text-xs text-muted-foreground">{fmtDist(a.distancia_m)}</span>
                    {a.url_maps && (
                      <a href={a.url_maps} target="_blank" rel="noreferrer">
                        <Button size="sm" variant="outline" type="button">Maps ↗</Button>
                      </a>
                    )}
                  </li>
                ))}
              </ol>
            </>
          ) : <SinDatos texto="Sin atractores registrados en el radio de análisis." />}
        </div>
      </Bloque>
    ),
  });

  // ── Entorno comercial ─────────────────────────────────────────────
  bloques.push({
    key: 'entorno',
    node: (
      <Bloque titulo="Entorno comercial">
        <div className="space-y-4">
          <p className="text-sm">
            Negocios activos en el radio mayor{payload.entorno_comercial?.radio_m ? ` (${fmtDist(payload.entorno_comercial.radio_m)})` : ''}:{' '}
            <strong className="font-mono text-base">{fmtNum(payload.entorno_comercial?.total_negocios)}</strong>
          </p>
          {payload.entorno_comercial?.nota && (
            <p className="text-xs text-muted-foreground">{payload.entorno_comercial.nota}</p>
          )}
          {categorias.some((c) => (c.conteo ?? 0) > 0) ? (
            <>
              <Chart
                height={280}
                option={{
                  tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
                  legend: { bottom: 0, type: 'scroll' },
                  series: [{
                    type: 'pie', radius: ['45%', '70%'],
                    data: categorias.filter((c) => (c.conteo ?? 0) > 0).map((c, i) => ({ name: c.etiqueta ?? c.categoria ?? 'Categoría', value: c.conteo ?? 0, itemStyle: { color: colorCategoria(c.categoria, i) } })),
                    label: { formatter: '{b}: {c}' },
                  }],
                }}
              />
              <Accordion type="multiple" className="w-full">
                {categorias.map((c, i) => (
                  <AccordionItem key={c.categoria ?? i} value={c.categoria ?? `cat-${i}`}>
                    <AccordionTrigger>
                      <span>{c.etiqueta ?? c.categoria ?? 'Categoría'} <Badge variant="secondary" className="ml-2">{c.conteo ?? 0}</Badge></span>
                    </AccordionTrigger>
                    <AccordionContent>
                      {(c.ejemplos ?? []).length > 0 ? (
                        <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
                          {c.ejemplos!.slice(0, 3).map((e, j) => <li key={j}>{e}</li>)}
                        </ul>
                      ) : <SinDatos texto="Sin ejemplos registrados para esta categoría." />}
                    </AccordionContent>
                  </AccordionItem>
                ))}
              </Accordion>
            </>
          ) : <SinDatos texto="Sin desglose del entorno por categoría en este reporte." />}
        </div>
      </Bloque>
    ),
  });

  // ── Segmentos / clientes de la zona ───────────────────────────────
  bloques.push({
    key: 'segmentos',
    node: (
      <Bloque titulo="Clientes y resultado de la zona" extra={<AprendeLink ancla="poblacion" />}>
        <div className="space-y-4">
          {payload.clientes_zona?.nota && <Alert variant="warning"><AlertDescription>{payload.clientes_zona.nota}</AlertDescription></Alert>}
          <dl className="grid gap-2 text-sm sm:grid-cols-2">
            <div className="flex justify-between border-b py-1"><dt className="text-muted-foreground">Población total del radio</dt><dd className="font-mono">{fmtNum(payload.clientes_zona?.poblacion_total)}</dd></div>
            <div className="flex justify-between border-b py-1"><dt className="text-muted-foreground">Población objetivo (30–59)</dt><dd className="font-mono">{fmtNum(payload.clientes_zona?.poblacion_objetivo)}</dd></div>
          </dl>
          {segmentos.length > 0 ? (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {segmentos.map((s, i) => (
                <div key={i} className="rounded-lg border p-3">
                  <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{s.segmento ?? `Segmento ${i + 1}`}</p>
                  <p className="mt-1 font-mono text-2xl font-bold">{fmtNum(s.poblacion)}</p>
                  <p className="text-xs text-muted-foreground">{typeof s.pct === 'number' ? `${s.pct.toFixed(1)} % de la población de la zona` : 'Sin % en el payload'}</p>
                  {typeof s.pct === 'number' && (
                    <div className="mt-2 h-2 overflow-hidden rounded-full bg-muted"><div className="h-full rounded-full bg-primary" style={{ width: `${Math.min(100, s.pct)}%` }} /></div>
                  )}
                </div>
              ))}
            </div>
          ) : <SinDatos texto="Sin segmentos de demanda en este reporte." />}
        </div>
      </Bloque>
    ),
  });

  // ── Población y viviendas (detalle edad/sexo) ─────────────────────
  bloques.push({
    key: 'poblacion',
    node: (
      <Bloque titulo="Población y viviendas" extra={<AprendeLink ancla="poblacion" />}>
        <div className="space-y-4">
          {payload.poblacion_viviendas?.advertencia && <Alert variant="warning"><AlertDescription>{payload.poblacion_viviendas.advertencia}</AlertDescription></Alert>}
          {Object.keys(gruposEdad).length > 0 ? (
            <div className="space-y-2">
              <p className="text-sm font-semibold">Grupos de edad {detalle?.radio_m ? `(radio ${fmtDist(detalle.radio_m)})` : ''}</p>
              {Object.entries(gruposEdad).map(([k, v]) => (
                <div key={k} className="flex items-center gap-3 text-sm">
                  <span className="w-32 shrink-0 text-muted-foreground">{etiqueta(k)}</span>
                  <div className="h-3 flex-1 overflow-hidden rounded-full bg-muted"><div className="h-full rounded-full bg-primary" style={{ width: `${(v / maxEdad) * 100}%` }} /></div>
                  <span className="w-20 shrink-0 text-right font-mono text-xs">{fmtNum(v)}</span>
                </div>
              ))}
              {detalle?.por_sexo && (
                <p className="pt-1 text-sm text-muted-foreground">
                  Por sexo: femenina <strong className="font-mono">{fmtNum(detalle.por_sexo.femenina)}</strong> · masculina <strong className="font-mono">{fmtNum(detalle.por_sexo.masculina)}</strong>
                </p>
              )}
            </div>
          ) : <SinDatos texto="Sin detalle poblacional por edad/sexo en este reporte." />}
        </div>
      </Bloque>
    ),
  });

  // ── Hogares + NSE ─────────────────────────────────────────────────
  bloques.push({
    key: 'hogares',
    node: (
      <Bloque titulo="Hogares, familias y NSE">
        <div className="space-y-4">
          {hogares && (hogares.viviendas_habitadas != null || hogares.promedio_ocupantes != null) ? (
            <dl className="grid gap-2 text-sm sm:grid-cols-2">
              <div className="flex justify-between border-b py-1"><dt className="text-muted-foreground">Viviendas habitadas</dt><dd className="font-mono">{fmtNum(hogares.viviendas_habitadas)}</dd></div>
              <div className="flex justify-between border-b py-1"><dt className="text-muted-foreground">Personas por vivienda</dt><dd className="font-mono">{typeof hogares.promedio_ocupantes === 'number' ? hogares.promedio_ocupantes.toFixed(2) : '—'}</dd></div>
              <div className="flex justify-between border-b py-1"><dt className="text-muted-foreground">% con internet</dt><dd className="font-mono">{typeof hogares.pct_internet === 'number' ? `${hogares.pct_internet.toFixed(1)} %` : '—'}</dd></div>
              <div className="flex justify-between border-b py-1"><dt className="text-muted-foreground">% con computadora</dt><dd className="font-mono">{typeof hogares.pct_computadora === 'number' ? `${hogares.pct_computadora.toFixed(1)} %` : '—'}</dd></div>
              <div className="flex justify-between border-b py-1"><dt className="text-muted-foreground">% con automóvil</dt><dd className="font-mono">{typeof hogares.pct_automovil === 'number' ? `${hogares.pct_automovil.toFixed(1)} %` : '—'}</dd></div>
            </dl>
          ) : <SinDatos texto="Sin datos de hogares en este reporte." />}
          {mov?.nse_etiqueta ? (
            <div className="rounded-lg border-2 border-primary/40 bg-primary/5 p-3">
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Perfil de gasto detectado</p>
              <p className="mt-1 text-lg font-bold">{mov.nse_etiqueta}</p>
              <p className="mt-1 text-xs text-muted-foreground">{mov.nse_nota ?? 'Etiqueta simplificada, no letra AMAI oficial.'} Referencia: regla AMAI 2024.</p>
            </div>
          ) : <SinDatos texto="Sin banda NSE predominante detectada en las AGEB del radio." />}
        </div>
      </Bloque>
    ),
  });

  // ── Movimiento y acceso ───────────────────────────────────────────
  bloques.push({
    key: 'movimiento',
    node: (
      <Bloque titulo="Movimiento y acceso" extra={<span className="flex items-center gap-3"><EstimadoBadge /><AprendeLink ancla="movimiento" /></span>}>
        <div className="space-y-4">
          <div>
            <p className="mb-2 text-sm font-semibold">Vialidades cercanas</p>
            {(mov?.vialidades ?? []).length > 0 ? (
              <ul className="space-y-1.5">
                {mov!.vialidades!.map((v, i) => (
                  <li key={i} className="flex flex-wrap items-center gap-2 rounded-md border px-3 py-2 text-sm">
                    <span className="min-w-0 flex-1 font-medium">{v.nombre ?? 'Vialidad'}</span>
                    {v.tipo && <Badge variant="outline">{v.tipo}</Badge>}
                    <span className="font-mono text-xs text-muted-foreground">a {fmtDist(v.distancia_m)}</span>
                    {typeof v.tiempo_auto_min === 'number' && <span className="text-xs text-muted-foreground">· {v.tiempo_auto_min} min en auto</span>}
                  </li>
                ))}
              </ul>
            ) : <SinDatos texto="Sin vialidades principales registradas cerca del punto (fuente OSM/Overpass)." />}
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {(['vehicular', 'peatonal'] as const).map((tipo) => {
              const b = movilidad?.[tipo];
              const rango = b?.rango ?? (tipo === 'vehicular' ? b?.rango_vehiculos_dia : b?.rango_personas_dia);
              return (
                <div key={tipo} className="rounded-lg border p-3">
                  <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Movilidad {tipo} estimada</p>
                  {b ? (
                    <>
                      <p className="mt-1 font-mono text-lg font-bold">{b.etiqueta ?? (rangoTexto(rango) ?? '—')}</p>
                      {typeof b.nivel === 'number' && (
                        <>
                          <div className="mt-2 h-2 overflow-hidden rounded-full bg-muted"><div className="h-full rounded-full bg-primary" style={{ width: `${Math.max(0, Math.min(100, b.nivel))}%` }} /></div>
                          <p className="mt-1 text-xs text-muted-foreground">Nivel {b.nivel}/100 · estimado por modelo (proxy §3.10), no es un conteo observado</p>
                        </>
                      )}
                      {b.metodo && <p className="mt-1 text-[11px] text-muted-foreground">{b.metodo}</p>}
                    </>
                  ) : <SinDatos texto={`Sin proxy de movilidad ${tipo} en este reporte.`} />}
                </div>
              );
            })}
          </div>
          <div className="rounded-lg border p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Actividad económica</p>
              <AprendeLink ancla="actividad" />
            </div>
            {movilidad?.actividad ? (
              <p className="mt-1 text-sm">
                PEA ocupada residente: <strong className="font-mono">{fmtNum(movilidad.actividad.pea_ocupada)}</strong>
                {typeof movilidad.actividad.pct_sobre_pob_15_mas === 'number' && <> · <strong className="font-mono">{movilidad.actividad.pct_sobre_pob_15_mas.toFixed(1)} %</strong> de la población de 15 años y más</>}
                {movilidad.actividad.nota && <span className="block pt-1 text-xs text-muted-foreground">{movilidad.actividad.nota}</span>}
              </p>
            ) : <SinDatos texto="Sin dato de actividad económica en este reporte." />}
          </div>
        </div>
      </Bloque>
    ),
  });

  // ── Alcance por tiempo ────────────────────────────────────────────
  bloques.push({
    key: 'alcance',
    node: (
      <Bloque titulo={esIsocronas ? 'Área de alcance por tiempo (isócronas)' : 'Área de alcance (radios)'}>
        <div className="space-y-4">
          {esIsocronas ? (
            <>
              {centro && interactivo && <MapaIsocronas centro={centro} isocronas={alcance!.isocronas!} />}
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead><tr className="border-b text-left text-xs uppercase tracking-wider text-muted-foreground">
                    <th className="py-2 pr-4">Modo</th><th className="py-2 pr-4">Tiempo</th><th className="py-2 pr-4">Población alcanzable</th><th className="py-2">Competidores dentro</th>
                  </tr></thead>
                  <tbody>
                    {alcance!.isocronas!.map((iso, i) => (
                      <tr key={i} className="border-b last:border-0">
                        <td className="py-2 pr-4">{etiquetaModo(iso)}{iso.modo_real && iso.modo && iso.modo_real !== iso.modo ? ` (real: ${iso.modo_real})` : ''}</td>
                        <td className="py-2 pr-4 font-mono">{iso.minutos ?? '—'} min</td>
                        <td className="py-2 pr-4 font-mono">{fmtNum(typeof iso.poblacion === 'number' ? Math.round(iso.poblacion) : iso.poblacion)}</td>
                        <td className="py-2 font-mono">{fmtNum(iso.competidores)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="rounded-md bg-muted/50 p-3 text-sm text-muted-foreground">
                <p className="font-semibold text-foreground">Cómo usar este alcance</p>
                <p className="mt-1">{alcance?.como_usarla ?? 'Cada isócrona delimita la población alcanzable en ese tiempo de viaje.'} Caminando defines tu mercado de barrio; en moto, tu radio realista de delivery; en auto, el mercado destino que vale campañas y señalización.</p>
              </div>
            </>
          ) : (
            <>
              <Alert variant="info">
                <AlertDescription>El servicio de isócronas no devolvió polígonos para este punto: el alcance se expresa en <strong>radios</strong> (círculos), no en tiempos de viaje. No son isócronas.</AlertDescription>
              </Alert>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead><tr className="border-b text-left text-xs uppercase tracking-wider text-muted-foreground">
                    <th className="py-2 pr-4">Radio (no isócrona)</th><th className="py-2 pr-4">Competidores</th><th className="py-2">ISM <EstimadoBadge /></th>
                  </tr></thead>
                  <tbody>
                    {(comp?.por_anillo ?? []).map((a, i) => (
                      <tr key={i} className="border-b last:border-0">
                        <td className="py-2 pr-4 font-mono">{fmtDist(a.radio_m)}</td>
                        <td className="py-2 pr-4 font-mono">{a.conteo ?? '—'}</td>
                        <td className="py-2 font-mono">{typeof a.ism === 'number' ? a.ism.toFixed(2) : '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      </Bloque>
    ),
  });

  // ── Negocios ancla ────────────────────────────────────────────────
  bloques.push({
    key: 'anclas',
    node: (
      <Bloque titulo="Negocios ancla">
        <div className="space-y-3">
          {payload.negocios_ancla?.nota && <p className="text-sm text-muted-foreground">{payload.negocios_ancla.nota}</p>}
          {anclas.length > 0 ? (
            <ul className="space-y-1.5">
              {anclas.map((a, i) => (
                <li key={i} className="flex flex-wrap items-center gap-2 rounded-md border px-3 py-2 text-sm">
                  <span aria-hidden>⚓</span>
                  <span className="min-w-0 flex-1 font-medium">{a.nombre ?? 'Negocio ancla'}</span>
                  {(a.etiqueta ?? a.tipo) && <Badge variant="outline">{a.etiqueta ?? a.tipo}</Badge>}
                  <span className="font-mono text-xs text-muted-foreground">a {fmtDist(a.distancia_m)}</span>
                  {typeof a.w === 'number' && <Badge variant="secondary" title="Peso del efecto ancla en Huff">peso ×{(1 + a.w).toFixed(2)}</Badge>}
                </li>
              ))}
            </ul>
          ) : <SinDatos texto="Sin negocios ancla detectados dentro de su radio de efecto." />}
        </div>
      </Bloque>
    ),
  });

  // ── Datos del giro (sector) ───────────────────────────────────────
  if (payload.datos_sector) {
    bloques.push({
      key: 'sector',
      node: (
        <Bloque titulo="Datos del giro">
          <div className="space-y-3">
            <dl className="grid gap-2 text-sm sm:grid-cols-2">
              <div className="flex justify-between border-b py-1"><dt className="text-muted-foreground">Ticket promedio</dt><dd className="font-mono">{mxn(payload.datos_sector.ticket_promedio)}</dd></div>
              <div className="flex justify-between border-b py-1"><dt className="text-muted-foreground">Hora pico</dt><dd className="font-medium">{payload.datos_sector.hora_pico ?? '—'}</dd></div>
              <div className="flex justify-between border-b py-1"><dt className="text-muted-foreground">% de ventas por delivery</dt><dd className="font-mono">{typeof payload.datos_sector.delivery_pct === 'number' ? `${payload.datos_sector.delivery_pct} %` : '—'}</dd></div>
            </dl>
            {(payload.datos_sector.top_productos ?? []).length > 0 && (
              <div>
                <p className="mb-1 text-sm font-semibold">Productos top del giro</p>
                <div className="flex flex-wrap gap-1.5">
                  {payload.datos_sector.top_productos!.map((p, i) => <Badge key={i} variant="secondary">{p}</Badge>)}
                </div>
              </div>
            )}
            {payload.datos_sector.fuente && <p className="text-xs text-muted-foreground">Fuente: {payload.datos_sector.fuente}</p>}
          </div>
        </Bloque>
      ),
    });
  }

  // ── Modelos (ISM / Huff / TAM) ─────────────────────────────────────
  bloques.push({
    key: 'modelos',
    node: (
      <Bloque titulo="Modelos de decisión" extra={<EstimadoBadge />}>
        <div className="space-y-4 text-sm">
          <div>
            <p className="mb-1 font-semibold">ISM <span className="font-mono text-xs text-muted-foreground">{payload.modelos?.ism?.formula}</span></p>
            <RenderGenerico contenido={payload.modelos?.ism?.por_anillo} />
          </div>
          <div>
            <p className="mb-1 font-semibold">Huff <span className="font-mono text-xs text-muted-foreground">{payload.modelos?.huff?.formula}</span></p>
            <p className="text-muted-foreground">Cuota del punto: <strong className="font-mono">{typeof payload.modelos?.huff?.cuota_punto === 'number' ? `${(payload.modelos.huff.cuota_punto * 100).toFixed(1)} %` : '—'}</strong></p>
          </div>
          <div>
            <p className="mb-1 font-semibold">TAM <span className="font-mono text-xs text-muted-foreground">{payload.modelos?.tam?.formula}</span></p>
            {payload.modelos?.tam?.advertencia && <Alert variant="warning" className="mb-2"><AlertDescription>{payload.modelos.tam.advertencia}</AlertDescription></Alert>}
            <p className="text-muted-foreground">
              TAM anual: <strong className="font-mono">{mxn(payload.modelos?.tam?.tam_mxn_anual)}</strong>
              {payload.modelos?.tam?.rango_mxn && payload.modelos.tam.rango_mxn.length === 2 && ` (rango ${mxn(payload.modelos.tam.rango_mxn[0])} – ${mxn(payload.modelos.tam.rango_mxn[1])})`}
            </p>
            {(payload.modelos?.tam?.supuestos ?? []).length > 0 && (
              <ul className="mt-1 list-disc pl-5 text-xs text-muted-foreground">
                {payload.modelos!.tam!.supuestos!.map((s, i) => <li key={i} className="font-mono">{s}</li>)}
              </ul>
            )}
          </div>
        </div>
      </Bloque>
    ),
  });

  // ── Calculadoras (renta + break-even) ─────────────────────────────
  bloques.push({
    key: 'calculadoras',
    node: (
      <div className="grid gap-6 lg:grid-cols-2">
        <Bloque titulo="Calculadora de renta mensual">
          <CalculadoraRenta interactivo={interactivo} />
        </Bloque>
        {payload.punto_equilibrio ? (
          <Bloque titulo="Punto de equilibrio vs. renta">
            <CalculadoraEquilibrio data={payload.punto_equilibrio} interactivo={interactivo} />
          </Bloque>
        ) : (
          <Bloque titulo="Punto de equilibrio vs. renta">
            <SinDatos texto="Este giro no trae plantilla de punto de equilibrio en el catálogo sectorial." />
          </Bloque>
        )}
      </div>
    ),
  });

  // ── Delivery ──────────────────────────────────────────────────────
  if (payload.delivery?.aplica) {
    bloques.push({
      key: 'delivery',
      node: (
        <Bloque titulo="Operación de delivery">
          <div className="space-y-2 text-sm">
            <p>Radio inicial sugerido: <strong className="font-mono">{Array.isArray(payload.delivery.radio_inicial_km) ? `${payload.delivery.radio_inicial_km[0]}–${payload.delivery.radio_inicial_km[1]} km` : `${payload.delivery.radio_inicial_km ?? '—'} km`}</strong></p>
            <p>Tiempo objetivo de entrega: <strong className="font-mono">{Array.isArray(payload.delivery.tiempo_objetivo_min) ? `${payload.delivery.tiempo_objetivo_min[0]}–${payload.delivery.tiempo_objetivo_min[1]} min` : `${payload.delivery.tiempo_objetivo_min ?? '—'} min`}</strong></p>
            {typeof payload.delivery.delivery_pct === 'number' && <p>Participación esperada del delivery en ventas del giro: <strong className="font-mono">{payload.delivery.delivery_pct} %</strong></p>}
            {payload.delivery.nota && <p className="text-muted-foreground">{payload.delivery.nota}</p>}
          </div>
        </Bloque>
      ),
    });
  }

  // ── Fuentes ───────────────────────────────────────────────────────
  bloques.push({
    key: 'fuentes',
    node: (
      <Bloque titulo="Fuentes y datos utilizados">
        <div className="space-y-3">
          {fuentes.length > 0 ? (
            <ul className="space-y-2">
              {fuentes.map((f, i) => (
                <li key={i} className="border-b pb-2 text-sm last:border-0">
                  {typeof f === 'string' ? f : (<><strong>{f.fuente ?? 'Fuente'}</strong>{f.rol && <span className="block text-muted-foreground">{f.rol}</span>}</>)}
                </li>
              ))}
            </ul>
          ) : <SinDatos texto="El payload no trae la lista nominal de fuentes." />}
          <dl className="grid gap-2 text-sm sm:grid-cols-2">
            <div className="flex justify-between border-b py-1"><dt className="text-muted-foreground">Fecha de cálculo</dt><dd className="font-mono text-xs">{payload.fuentes_datos?.fecha_calculo ?? '—'}</dd></div>
            <div className="flex justify-between border-b py-1"><dt className="text-muted-foreground">Versión de modelos</dt><dd className="font-mono text-xs">{payload.fuentes_datos?.model_version ?? '—'}</dd></div>
          </dl>
          {(payload.fuentes_datos?.ediciones ?? []).length > 0 && <RenderGenerico contenido={payload.fuentes_datos!.ediciones} />}
        </div>
      </Bloque>
    ),
  });

  // ── Metodología ───────────────────────────────────────────────────
  bloques.push({
    key: 'metodologia',
    node: (
      <Bloque titulo="Metodología y advertencias">
        <div className="space-y-3">
          {payload.metodologia_advertencias?.nota_general && <Alert variant="info"><AlertDescription>{payload.metodologia_advertencias.nota_general}</AlertDescription></Alert>}
          <RenderGenerico contenido={payload.metodologia_advertencias?.estimado_vs_observado} />
        </div>
      </Bloque>
    ),
  });

  // ── Plan de contacto (Radar §14, si el payload lo trae) ───────────
  if (payload.plan_contacto) {
    bloques.push({
      key: 'plan',
      node: (
        <Bloque titulo="Plan de contacto sugerido">
          <RenderGenerico contenido={payload.plan_contacto} />
        </Bloque>
      ),
    });
  }

  // Orden inmobiliario: entorno y anclas primero; sin bloques operativos.
  let visibles = bloques;
  if (modoInmobiliario) {
    const ocultos = new Set(['delivery', 'calculadoras', 'sector', 'plan']);
    const prioridad = ['entorno', 'anclas', 'movimiento', 'alcance', 'atractores', 'competencia', 'segmentos', 'poblacion', 'hogares', 'perfil', 'modelos', 'fuentes', 'metodologia'];
    visibles = bloques
      .filter((b) => !ocultos.has(b.key))
      .sort((a, b) => prioridad.indexOf(a.key) - prioridad.indexOf(b.key));
  }

  return (
    <div className="space-y-6">
      {/* Cabecera + veredicto */}
      <Card style={{ borderLeft: `6px solid ${verdictColor(decision)}` }}>
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.2em] text-muted-foreground">{cab?.etiqueta ?? 'REPORTE DE UBICACIÓN'}</p>
              <CardTitle className="mt-1 text-2xl">{cab?.titulo ?? `Análisis para ${cab?.giro ?? 'el giro indicado'}`}</CardTitle>
              <CardDescription className="mt-1">
                {cab?.ubicacion ?? 'Ubicación no especificada'}
                {cab?.fecha && ` · ${cab.fecha}`}
                {(cab?.radios_m ?? []).length > 0 && ` · Radios: ${cab!.radios_m!.map((r) => fmtDist(r)).join(' y ')}`}
                {cab?.scian && ` · SCIAN ${cab.scian}`}
                {cab?.empresa && ` · ${cab.empresa}`}
              </CardDescription>
            </div>
            {acciones}
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap items-center gap-3">
            <span className="inline-block h-7 w-7 rounded-full" style={{ backgroundColor: verdictColor(decision) }} aria-hidden />
            <span className="text-3xl font-bold">{decision}</span>
            {ver?.confianza && <Badge variant="outline">Confianza: {ver.confianza}</Badge>}
            {modoInmobiliario && <Badge variant="accent">Modo inmobiliario</Badge>}
          </div>
          {ver?.factores && ver.factores.length > 0 && (
            <div>
              <p className="mb-1 text-sm font-semibold">Factores del veredicto:</p>
              <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
                {ver.factores.map((f, i) => <li key={i}>{f}</li>)}
              </ul>
            </div>
          )}
          {ver?.riesgos && ver.riesgos.length > 0 && (
            <Alert variant="warning"><AlertTitle>Riesgos</AlertTitle><AlertDescription><ul className="list-disc pl-5">{ver.riesgos.map((r, i) => <li key={i}>{r}</li>)}</ul></AlertDescription></Alert>
          )}
          <p className="text-xs text-muted-foreground">🟢 AVANZAR · 🟡 NEGOCIAR · 🔴 EXPLORAR_OTRA_ZONA — semáforo del veredicto (SRS §6.1)</p>
        </CardContent>
      </Card>

      {visibles.map((b) => (
        <React.Fragment key={b.key}>{b.node}</React.Fragment>
      ))}
    </div>
  );
}

/* ================= Página ================= */

const LS_SHARE = (reportId: string) => `geis:share:${reportId}`;
const LS_INV = (reportId: string) => `geis:reporte-inv:${reportId}`;

export default function Reporte() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [giro, setGiro] = React.useState('');
  const [modo, setModo] = React.useState<'coords' | 'direccion'>('coords');
  const [lat, setLat] = React.useState('');
  const [lon, setLon] = React.useState('');
  const [direccion, setDireccion] = React.useState('');
  const [cargando, setCargando] = React.useState(false);
  const [geocodificando, setGeocodificando] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [reporte, setReporte] = React.useState<ReportOutS1 | null>(null);
  const [crudo, setCrudo] = React.useState(false);
  const [geoNota, setGeoNota] = React.useState<string | null>(null);
  const [precargaNota, setPrecargaNota] = React.useState<string | null>(null);
  const [invPrecargada, setInvPrecargada] = React.useState<string | null>(null);
  const [invTipo, setInvTipo] = React.useState<string | null>(null);
  const [shareToken, setShareToken] = React.useState<string | null>(null);
  const [shareExpira, setShareExpira] = React.useState<string | null>(null);
  const [compartiendo, setCompartiendo] = React.useState(false);
  const [copiado, setCopiado] = React.useState(false);

  const payload = reporte?.payload as ReportPayloadFull | undefined;
  const modoInmobiliario = invTipo === 'real_estate';

  // Carga directa de un reporte persistido (?reporte={id}), p. ej. desde Analizar.
  React.useEffect(() => {
    const rid = searchParams.get('reporte') ?? searchParams.get('report');
    if (!rid) return;
    let vivo = true;
    setCargando(true);
    getReport(rid)
      .then((r) => { if (vivo) setReporte(r); })
      .catch((e) => { if (vivo) setError(errorMessage(e)); })
      .finally(() => { if (vivo) setCargando(false); });
    // Modo inmobiliario: el ReportOut no referencia su investigación; se
    // resuelve con el puente que Analizar guarda en localStorage.
    try {
      const invId = localStorage.getItem(LS_INV(rid));
      if (invId) {
        getInvestigation(invId)
          .then((inv) => { if (vivo) { setInvTipo(inv.investigation_type ?? null); setInvPrecargada(inv.investigation_id); } })
          .catch(() => { /* sin investigación asociada accesible: modo normal */ });
      }
    } catch { /* localStorage no disponible */ }
    return () => { vivo = false; };
  }, [searchParams]);

  // Precarga desde una investigación (?id={investigation_id}).
  React.useEffect(() => {
    const id = searchParams.get('id');
    if (!id) return;
    let vivo = true;
    getInvestigation(id)
      .then((inv) => {
        if (!vivo) return;
        setInvPrecargada(inv.investigation_id);
        setInvTipo(inv.investigation_type ?? null);
        const params = (inv.params ?? {}) as Record<string, unknown>;
        const giroPrecargado = (typeof params.giro === 'string' ? params.giro : undefined) ?? inv.vertical ?? '';
        if (giroPrecargado) setGiro(String(giroPrecargado));
        if (inv.center_lat != null) setLat(String(inv.center_lat));
        if (inv.center_lon != null) setLon(String(inv.center_lon));
        if (inv.center_lat != null) setModo('coords');
        setPrecargaNota(`Formulario precargado desde la investigación «${inv.title ?? id}». Solo pulsa «Generar reporte».`);
        toast.success('Investigación precargada', { description: inv.title ?? id });
      })
      .catch((e) => {
        if (!vivo) return;
        toast.error('No se encontró la investigación', { description: errorMessage(e) });
        setPrecargaNota('No se encontró la investigación indicada en la URL; completa el formulario normalmente.');
      });
    return () => { vivo = false; };
  }, [searchParams]);

  // Token de share guardado para este reporte (permite revocarlo después).
  React.useEffect(() => {
    setCopiado(false);
    if (!reporte?.report_id) { setShareToken(null); return; }
    try { setShareToken(localStorage.getItem(LS_SHARE(reporte.report_id))); } catch { setShareToken(null); }
  }, [reporte?.report_id]);

  const generar = async () => {
    setCargando(true);
    setError(null);
    setReporte(null);
    setGeoNota(null);
    try {
      let la = Number(lat);
      let lo = Number(lon);
      if (modo === 'direccion') {
        setGeocodificando(true);
        try {
          const g = await geocode({ address: direccion });
          la = g.lat; lo = g.lon;
          setGeoNota(g.label);
        } finally {
          setGeocodificando(false);
        }
      }
      const res = await createReport({
        investigation_id: invPrecargada ?? undefined,
        title: `Análisis para ${giro}`,
        giro,
        lat: la,
        lon: lo,
        radios: [1000, 2000],
      });
      setReporte(res);
      toast.success('Reporte generado');
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setCargando(false);
    }
  };

  const crearShare = async () => {
    if (!reporte?.report_id) return;
    setCompartiendo(true);
    try {
      const s = await createReportShare(reporte.report_id, 30);
      setShareToken(s.token);
      setShareExpira(s.expira_en);
      try { localStorage.setItem(LS_SHARE(reporte.report_id), s.token); } catch { /* sin persistencia local */ }
      toast.success('Link invitado creado', { description: 'Vigente por 30 días; puedes revocarlo cuando quieras.' });
    } catch (e) {
      toast.error('No se pudo crear el link', { description: errorMessage(e) });
    } finally { setCompartiendo(false); }
  };

  const revocarShare = async () => {
    if (!reporte?.report_id || !shareToken) return;
    setCompartiendo(true);
    try {
      await revokeReportShare(reporte.report_id, shareToken);
      setShareToken(null);
      setShareExpira(null);
      try { localStorage.removeItem(LS_SHARE(reporte.report_id)); } catch { /* sin persistencia local */ }
      toast.success('Link invitado revocado', { description: 'La vista pública ahora responde «enlace no disponible».' });
    } catch (e) {
      toast.error('No se pudo revocar el link', { description: errorMessage(e) });
    } finally { setCompartiendo(false); }
  };

  const copiarShare = async () => {
    if (!shareToken) return;
    const url = `${window.location.origin}/r/${shareToken}`;
    try {
      await navigator.clipboard.writeText(url);
      setCopiado(true);
      toast.success('Link copiado');
    } catch {
      toast.info('Copia el link manualmente', { description: url });
    }
  };

  const linkPublico = shareToken ? `${window.location.origin}/r/${shareToken}` : null;

  const whatsappUrl = React.useMemo(() => {
    if (!payload) return null;
    const lineas = [
      `📍 Reporte de ubicación GEIS — ${payload.cabecera?.giro ?? giro}`,
      `Veredicto: ${payload.veredicto?.decision ?? reporte?.verdict ?? '—'}`,
      `Población (radio mayor): ${fmtNum(payload.clientes_zona?.poblacion_total)} · Competidores: ${fmtNum(payload.competencia?.lista?.length ?? payload.competencia?.por_anillo?.[payload.competencia.por_anillo.length - 1]?.conteo)} · TAM anual: ${mxn(payload.modelos?.tam?.tam_mxn_anual)}`,
    ];
    if (linkPublico) lineas.push(`Ver el reporte: ${linkPublico}`);
    return `https://wa.me/?text=${encodeURIComponent(lineas.join('\n'))}`;
  }, [payload, giro, reporte?.verdict, linkPublico]);

  const acciones = reporte?.report_id ? (
    <div className="flex flex-col items-end gap-2">
      <div className="flex flex-wrap gap-2">
        {whatsappUrl && (
          <a href={whatsappUrl} target="_blank" rel="noreferrer">
            <Button type="button" size="sm" variant="outline">WhatsApp</Button>
          </a>
        )}
        <Button type="button" size="sm" variant="outline" onClick={() => navigate(`/reporte/${reporte.report_id}/imprimir`)}>PDF / Imprimir</Button>
        {!shareToken && (
          <Button type="button" size="sm" onClick={crearShare} disabled={compartiendo}>
            {compartiendo && <Spinner size={14} />} Link invitado
          </Button>
        )}
        <Button type="button" size="sm" variant="ghost" onClick={() => setCrudo((c) => !c)}>{crudo ? 'Ver formateado' : 'Ver JSON'}</Button>
      </div>
      {shareToken && (
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <code className="rounded bg-muted px-2 py-1">{`/r/${shareToken}`}</code>
          <Button type="button" size="sm" variant="outline" onClick={copiarShare}>{copiado ? '✓ Copiado' : 'Copiar link'}</Button>
          <Button type="button" size="sm" variant="destructive" onClick={revocarShare} disabled={compartiendo}>Revocar</Button>
          {shareExpira && <span className="text-muted-foreground">expira {new Date(shareExpira).toLocaleDateString('es-MX')}</span>}
        </div>
      )}
    </div>
  ) : null;

  const valido = modo === 'coords' ? giro.trim() !== '' && lat !== '' && lon !== '' : giro.trim() !== '' && direccion.trim() !== '';

  return (
    <div className="flex h-full flex-col">
      <Topbar titulo="Reporte de ubicación" subtitulo="Informe de decisión completo en una pantalla · la puerta rápida es «Analizar» (2 campos + 1 clic)" />
      <div className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-5xl space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Nuevo análisis</CardTitle>
              <CardDescription>
                Giro + ubicación. Con dirección se geocodifica de verdad (Nominatim/OSM o link de Maps); si no resuelve, verás el error, nunca un punto falso.
                Para el flujo guiado con pin confirmable usa <Link to="/analizar" className="font-medium text-primary hover:underline">Analizar</Link>.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {precargaNota && <Alert variant="info"><AlertDescription>{precargaNota}</AlertDescription></Alert>}
              {modoInmobiliario && <Alert variant="info"><AlertDescription>Modo inmobiliario activo (investigación <code>real_estate</code>): el reporte prioriza entorno, anclas y vialidades, y oculta los bloques operativos del negocio.</AlertDescription></Alert>}
              <Field label="Giro / actividad" htmlFor="giro" required>
                <Input id="giro" placeholder="Ej. Cafetería" value={giro} onChange={(e) => setGiro(e.target.value)} />
              </Field>
              <div className="flex gap-2">
                <Button variant={modo === 'direccion' ? 'default' : 'outline'} size="sm" onClick={() => setModo('direccion')}>Dirección</Button>
                <Button variant={modo === 'coords' ? 'default' : 'outline'} size="sm" onClick={() => setModo('coords')}>Lat / Lon</Button>
              </div>
              {modo === 'coords' ? (
                <div className="grid gap-4 sm:grid-cols-2">
                  <Field label="Latitud" htmlFor="lat" required>
                    <Input id="lat" type="number" step="any" placeholder="19.4326" value={lat} onChange={(e) => setLat(e.target.value)} />
                  </Field>
                  <Field label="Longitud" htmlFor="lon" required>
                    <Input id="lon" type="number" step="any" placeholder="-99.1332" value={lon} onChange={(e) => setLon(e.target.value)} />
                  </Field>
                </div>
              ) : (
                <Field label="Dirección o link de Google Maps" htmlFor="dir" required>
                  <Input id="dir" placeholder="Roma Norte, Cuauhtémoc, CDMX — o pega el link de Maps" value={direccion} onChange={(e) => setDireccion(e.target.value)} />
                </Field>
              )}
              <Button onClick={generar} disabled={cargando || !valido}>
                {(cargando || geocodificando) && <Spinner size={16} />}
                {geocodificando ? 'Geocodificando…' : 'Generar reporte'}
              </Button>
              {geoNota && <p className="text-xs text-muted-foreground">Geocodificado: {geoNota}</p>}
            </CardContent>
          </Card>

          {error && <Alert variant="destructive"><AlertTitle>No se pudo generar el reporte</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>}

          {!reporte && !cargando && !error && (
            <Empty title="Sin reporte" description="Completa el formulario y genera el análisis para ver aquí el reporte completo: mapas, competencia, entorno, alcance, calculadoras y veredicto." icon="📄" />
          )}
          {cargando && !reporte && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground"><Spinner size={16} /> Cargando reporte…</div>
          )}

          {reporte && payload && (
            crudo ? (
              <div className="space-y-4">
                <div className="flex justify-end"><Button variant="ghost" size="sm" onClick={() => setCrudo(false)}>Ver formateado</Button></div>
                <CodeBlock language="json" code={JSON.stringify(reporte, null, 2)} />
              </div>
            ) : (
              <ReporteCuerpo payload={payload} modoInmobiliario={modoInmobiliario} acciones={acciones} />
            )
          )}

          {reporte?.report_id && (
            <p className="font-mono text-xs text-muted-foreground">ID del reporte: {reporte.report_id}</p>
          )}
          <Separator />
        </div>
      </div>
    </div>
  );
}

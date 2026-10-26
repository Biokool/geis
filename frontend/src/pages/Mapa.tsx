import * as React from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { MapContainer, TileLayer, CircleMarker, Circle, Popup, GeoJSON, useMap, ZoomControl } from 'react-leaflet';
import L from 'leaflet';
import '@geoman-io/leaflet-geoman-free';
import { Topbar } from '@/components/layout/Topbar';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/Alert';
import { Skeleton } from '@/components/ui/Skeleton';
import { Empty } from '@/components/ui/Empty';
import { Badge } from '@/components/ui/Badge';
import { Switch } from '@/components/ui/Switch';
import { Label } from '@/components/ui/Label';
import { Button } from '@/components/ui/Button';
import { Spinner } from '@/components/ui/Spinner';
import { get, post, errorMessage, type Lead, type LeadCurado, type Investigation, lineaColor } from '@/lib/api';
import {
  useGeoFiltros, getCuradosGeo, getReporte, postReporte, coordsDeUrlMaps,
  type ReporteParaMapa, type AtractorItem, type GeoParams,
} from '@/lib/apiGeo';
import { NativeSelect } from '@/components/ui/NativeSelect';
import { MapaExpandible } from '@/components/map/MapaExpandible';
import { estratoColor, estratoRadio, areaKm2 } from '@/lib/geo';
import { useGeisStore } from '@/store';
import { toast } from 'sonner';

function GeomanControl({ onPolygon }: { onPolygon: (g: GeoJSON.GeoJSON) => void }) {
  const map = useMap();
  React.useEffect(() => {
    const m = map as unknown as {
      pm: {
        addControls: (o: Record<string, unknown>) => void;
        removeControls: () => void;
        setLang: (l: string) => void;
      };
      on: (ev: string, fn: (e: { layer: L.Layer }) => void) => void;
      off: (ev: string, fn: (e: { layer: L.Layer }) => void) => void;
    };
    try { m.pm.setLang('es'); } catch { /* idioma no disponible */ }
    m.pm.addControls({
      position: 'topright',
      drawMarker: false, drawCircleMarker: false, drawPolyline: false,
      drawRectangle: true, drawPolygon: true, drawCircle: false, drawText: false,
      editMode: true, dragMode: true, cutPolygon: true, removalMode: true,
    });
    const handler = (e: { layer: L.Layer }) => {
      const gj = (e.layer as L.Polygon).toGeoJSON() as unknown as GeoJSON.GeoJSON;
      onPolygon(gj);
    };
    m.on('pm:create', handler);
    return () => { m.off('pm:create', handler); m.pm.removeControls(); };
  }, [map, onPolygon]);
  return null;
}

function MoverMapa({ centro, zoom = 13 }: { centro: [number, number] | null; zoom?: number }) {
  const map = useMap();
  React.useEffect(() => {
    if (centro) map.setView(centro, zoom);
  }, [map, centro, zoom]);
  return null;
}

/** Color de lead por score: ≥70 verde, 40–69 ámbar, <40 gris. */
function scoreColor(score?: number): string {
  const s = score ?? 0;
  if (s >= 70) return '#2F9E44';
  if (s >= 40) return '#E8A13D';
  return '#8a93a6';
}

interface B2bLead {
  denue_id?: string;
  nombre?: string;
  scian_code?: string;
  estrato_texto?: string;
  distancia_m?: number;
  idt?: number;
  score?: number;
  desglose?: Record<string, number>;
}

interface B2bResult {
  total_candidatos?: number;
  leads?: B2bLead[];
  lineage?: Record<string, unknown>;
}

/** Centroide aproximado (promedio del anillo exterior) para alimentar /b2b-prospecting. */
function centroide(g: GeoJSON.Polygon | GeoJSON.MultiPolygon): { lat: number; lon: number } {
  const ring = g.type === 'Polygon' ? g.coordinates[0] : g.coordinates[0][0];
  let sx = 0, sy = 0;
  for (const [lon, lat] of ring) { sx += lon; sy += lat; }
  return { lat: sy / ring.length, lon: sx / ring.length };
}

export default function Mapa() {
  const [leads, setLeads] = React.useState<Lead[]>([]);
  const [curados, setCurados] = React.useState<LeadCurado[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [capaDenue, setCapaDenue] = React.useState(true);
  const [capaHeat, setCapaHeat] = React.useState(true);
  const [capaTemp, setCapaTemp] = React.useState(false);
  const [capaLinea, setCapaLinea] = React.useState(true);
  const [poligono, setPoligono] = React.useState<GeoJSON.GeoJSON | null>(null);
  const [invCentro, setInvCentro] = React.useState<[number, number] | null>(null);
  const [invRadios, setInvRadios] = React.useState<number[]>([]);
  const [capaLeads, setCapaLeads] = React.useState(true);
  const [b2b, setB2b] = React.useState<B2bResult | null>(null);
  const [analizando, setAnalizando] = React.useState(false);
  const setTerritorio = useGeisStore((s) => s.setTerritorio);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  /* ── Sección 2 · preset Radar (?modo=radar) y capas del reporte ─────── */
  const modoRadar = searchParams.get('modo') === 'radar';
  const geo = useGeoFiltros();
  const [invActual, setInvActual] = React.useState<Investigation | null>(null);
  const [reporteMapa, setReporteMapa] = React.useState<ReporteParaMapa | null>(null);
  const [cargandoReporte, setCargandoReporte] = React.useState(false);
  const [capaAtractores, setCapaAtractores] = React.useState(true);
  const [capaIsocronas, setCapaIsocronas] = React.useState(true);

  // Preset Radar: capas de leads y temperatura activas por defecto.
  React.useEffect(() => {
    if (modoRadar) {
      setCapaLeads(true);
      setCapaTemp(true);
    }
  }, [modoRadar]);

  const cargarCuradosGeo = React.useCallback(async (params: GeoParams) => {
    try {
      const r = await getCuradosGeo({ limit: 100, ...params });
      const arr = Array.isArray(r) ? r : (r.items ?? []);
      setCurados(arr.filter((l) => l.lat != null && l.lon != null));
    } catch { /* la capa de leads es opcional: el mapa base sigue funcionando */ }
  }, []);

  // En modo Radar, la capa de leads se filtra con la cascada geográfica.
  React.useEffect(() => {
    if (modoRadar) void cargarCuradosGeo(geo.params);
  }, [modoRadar, geo.params, cargarCuradosGeo]);

  React.useEffect(() => {
    let vivo = true;
    get<{ items?: Lead[]; data?: Lead[] } | Lead[]>('/leads', { limit: 100 })
      .then((r) => {
        if (!vivo) return;
        const arr = Array.isArray(r) ? r : (r.items ?? r.data ?? []);
        setLeads(arr.filter((l) => l.lat !== undefined && l.lon !== undefined));
      })
      .catch((e) => vivo && setError(errorMessage(e)));
    get<{ items?: LeadCurado[] } | LeadCurado[]>('/leads/curados', { limit: 100 })
      .then((r) => {
        if (!vivo) return;
        const arr = Array.isArray(r) ? r : (r.items ?? []);
        setCurados(arr.filter((l) => l.lat !== undefined && l.lon !== undefined));
      })
      .catch(() => { /* los leads curados son opcionales: el mapa base sigue funcionando */ })
      .finally(() => vivo && setLoading(false));
    return () => { vivo = false; };
  }, []);

  React.useEffect(() => {
    const invId = searchParams.get('inv');
    if (!invId) return;
    let vivo = true;
    get<Investigation>(`/investigations/${invId}`)
      .then((inv) => {
        if (!vivo) return;
        setInvActual(inv);
        if (inv.center_lat != null && inv.center_lon != null) {
          setInvCentro([inv.center_lat, inv.center_lon]);
          setInvRadios(inv.radii_m ?? []);
          setTerritorio({ nombre: inv.title ?? `Investigación ${invId.slice(0, 8)}`, tipo: inv.territory_kind ?? 'point_buffers' });
          toast.success('Investigación cargada en el mapa', { description: inv.title ?? invId });
        } else {
          toast.info('La investigación no trae centro geográfico', { description: 'No se puede centrar el mapa.' });
        }
      })
      .catch((e) => { if (vivo) toast.error('No se pudo cargar la investigación', { description: errorMessage(e) }); });
    return () => { vivo = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  /* Reporte de la investigación activa: NO existe un GET «reporte por
     investigación» en la API. Las vías reales son GET /reports/{report_id}
     (si el id viene en ?reporte= o en params de la investigación) o
     POST /reports con investigation_id (el mismo endpoint que usa la
     página Reporte), que genera y devuelve el payload completo. */
  const reporteIdParam = searchParams.get('reporte');
  React.useEffect(() => {
    const deParams = invActual?.params?.report_id ?? invActual?.params?.reporte_id;
    const rid = reporteIdParam ?? (typeof deParams === 'string' ? deParams : null);
    if (!rid) return;
    let vivo = true;
    setCargandoReporte(true);
    getReporte(rid)
      .then((r) => { if (vivo) setReporteMapa(r); })
      .catch((e) => { if (vivo) toast.error('No se pudo cargar el reporte', { description: errorMessage(e) }); })
      .finally(() => { if (vivo) setCargandoReporte(false); });
    return () => { vivo = false; };
  }, [reporteIdParam, invActual]);

  const generarReporteMapa = async () => {
    if (!invActual || invCentro == null) return;
    setCargandoReporte(true);
    try {
      const params = (invActual.params ?? {}) as Record<string, unknown>;
      const r = await postReporte({
        investigation_id: invActual.investigation_id,
        title: invActual.title ?? 'Reporte de ubicación',
        giro: typeof params.giro === 'string' ? params.giro : (invActual.vertical ?? undefined),
        scian: typeof params.scian === 'string' ? params.scian : undefined,
        lat: invCentro[0],
        lon: invCentro[1],
        radios: invRadios.length ? invRadios : [1000, 2000],
      });
      setReporteMapa(r);
      toast.success('Reporte generado', { description: 'Capas de atractores e isócronas actualizadas desde el payload real.' });
    } catch (e) {
      toast.error('No se pudo generar el reporte', { description: errorMessage(e) });
    } finally {
      setCargandoReporte(false);
    }
  };

  const atractores = React.useMemo(
    () => (reporteMapa?.payload?.atractores_trafico?.items ?? [])
      .map((item) => ({ item, coords: coordsDeUrlMaps(item.url_maps) }))
      .filter((x): x is { item: AtractorItem; coords: [number, number] } => x.coords != null),
    [reporteMapa],
  );
  const atractoresSinCoords = (reporteMapa?.payload?.atractores_trafico?.items ?? []).length - atractores.length;
  const isocronas = React.useMemo(
    () => (reporteMapa?.payload?.area_alcance_tiempo?.isocronas ?? []).filter((i) => i.geometria),
    [reporteMapa],
  );
  const categoriasAtractores = React.useMemo(
    () => [...new Set(atractores.map((x) => x.item.categoria_etiqueta ?? x.item.categoria ?? 'Otro'))],
    [atractores],
  );
  const invIdParam = searchParams.get('inv');

  const crearInvestigacionAqui = async (l: Lead) => {
    if (l.lat == null || l.lon == null) { toast.error('Sin coordenadas para crear la investigación'); return; }
    try {
      const nombre = l.razon_social ?? l.nombre ?? 'Establecimiento';
      const creada = await post<Investigation>('/investigations', {
        user_id: 'analista',
        title: nombre,
        investigation_type: 'location_viability',
        territory_kind: 'point_buffers',
        center_lat: l.lat,
        center_lon: l.lon,
        radii_m: [1000, 2000],
        params: { scian: l.scian_code },
      });
      const nuevoId = creada.investigation_id;
      toast.success('Investigación creada', {
        description: nombre,
        action: nuevoId ? { label: 'Ver reporte', onClick: () => navigate(`/reporte?id=${nuevoId}`) } : undefined,
      });
    } catch (e) {
      toast.error('No se pudo crear la investigación', { description: errorMessage(e) });
    }
  };

  const onPolygon = React.useCallback(async (g: GeoJSON.GeoJSON) => {
    setPoligono(g);
    setAnalizando(true);
    setB2b(null);
    const area = areaLocal(g);
    const nombre = `Polígono ${new Date().toLocaleString('es-MX', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}`;
    setTerritorio({ nombre, tipo: 'polygon', geojson: g, area_km2: area });
    try {
      // El backend exige lat/lon (B2BRequest): centroide + radio equivalente al área dibujada.
      if (g.type !== 'Polygon' && g.type !== 'MultiPolygon') throw new Error('Tipo de geometría no soportado');
      const { lat, lon } = centroide(g as GeoJSON.Polygon | GeoJSON.MultiPolygon);
      const radio_m = Math.min(50000, Math.max(500, Math.round(Math.sqrt((area ?? 78.5) / Math.PI) * 1000)));
      const res = await post<B2bResult>('/analysis/b2b-prospecting', { lat, lon, radio_m, top_n: 50 });
      setB2b(res);
      toast.success('Polígono analizado', { description: `${res.total_candidatos ?? 0} candidatos B2B en el área.` });
    } catch (e) {
      toast.error('No se pudo analizar el polígono', { description: errorMessage(e) });
    } finally {
      setAnalizando(false);
    }
  }, [setTerritorio]);

  const centro: [number, number] = leads.length ? [leads[0].lat!, leads[0].lon!] : [25.6866, -100.3161];

  return (
    <div className="flex h-full flex-col">
      <Topbar
        titulo={modoRadar ? 'Mapa Radar' : 'Mapa geoespacial'}
        subtitulo={modoRadar
          ? 'Tus prospectos en el territorio · preset Radar: leads + temperatura + filtros geográficos'
          : 'Geofencing, clústeres y demanda térmica · DENUE + IDT + Radar'}
      />
      {/* El contenedor ampliable incluye el mapa Y el panel de filtros:
          en pantalla completa no se pierde ningún filtro/capa. */}
      <MapaExpandible className="flex min-h-0 flex-1 flex-col md:flex-row" titulo="Mapa">
        <div className="mapa-lienzo relative h-[55vh] min-w-0 flex-1 md:h-auto">
          {loading && (
            <div className="absolute inset-0 z-10 bg-background/60 p-4">
              <Skeleton className="h-full w-full" />
            </div>
          )}
          <MapContainer center={centro} zoom={11} zoomControl={false} className="h-full w-full" style={{ height: '100%' }}>
            <ZoomControl position="topright" />
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            <GeomanControl onPolygon={onPolygon} />
            <MoverMapa centro={invCentro} />
            {invCentro && invRadios.map((r) => (
              <Circle key={r} center={invCentro} radius={r} pathOptions={{ color: '#0E5FD8', weight: 2, fillOpacity: 0.05, dashArray: '6 4' }}>
                <Popup><div className="text-sm"><p className="font-semibold">Radio {r} m</p><p className="text-xs text-muted-foreground">Círculo de radio de la investigación (no es una isócrona).</p></div></Popup>
              </Circle>
            ))}
            {capaDenue && leads.map((l, i) => (
              <CircleMarker
                key={l.denue_id ?? l.id ?? i}
                center={[l.lat!, l.lon!]}
                radius={estratoRadio(l.estrato)}
                pathOptions={{ color: '#fff', weight: 1, fillColor: estratoColor(l.estrato), fillOpacity: 0.9 }}
              >
                <Popup>
                  <div className="text-sm">
                    <p className="font-semibold">{l.razon_social ?? l.nombre ?? 'Establecimiento'}</p>
                    <p className="text-xs text-muted-foreground">Estrato: {l.estrato ?? '—'} · {l.distancia_km !== undefined ? `${l.distancia_km.toFixed(1)} km` : ''}</p>
                    {l.scian_code && <p className="font-mono text-xs">SCIAN {l.scian_code}</p>}
                    {l.scian_desc && <p className="text-xs">{l.scian_desc}</p>}
                    <button type="button" onClick={() => crearInvestigacionAqui(l)} style={{ marginTop: 6, padding: '4px 8px', borderRadius: 6, background: '#0E5FD8', color: '#fff', fontSize: 12, cursor: 'pointer', border: 'none' }}>Crear investigación aquí</button>
                  </div>
                </Popup>
              </CircleMarker>
            ))}
            {capaHeat && leads.map((l, i) => (
              <CircleMarker
                key={`h${l.denue_id ?? l.id ?? i}`}
                center={[l.lat!, l.lon!]}
                radius={Math.max(6, (l.idt ?? 0) / 6)}
                pathOptions={{ color: 'transparent', fillColor: heatColor(l.idt), fillOpacity: 0.28 }}
                interactive={false}
              />
            ))}
            {poligono && <GeoJSON key={JSON.stringify(poligono)} data={poligono} pathOptions={{ color: '#0E5FD8', weight: 2, fillOpacity: 0.08 }} />}
            {/* Módulo Radar: círculos de temperatura y pines por línea recomendada */}
            {capaTemp && curados.map((l) => (
              <CircleMarker
                key={`t${l.lead_id}`}
                center={[l.lat!, l.lon!]}
                radius={Math.max(6, (l.temp_zona ?? 0) * 1.2)}
                pathOptions={{ color: 'transparent', fillColor: tempColor(l.temp_zona), fillOpacity: 0.35 }}
                interactive={false}
              />
            ))}
            {capaLeads && curados.map((l) => (
              <CircleMarker
                key={`lead${l.lead_id}`}
                center={[l.lat!, l.lon!]}
                radius={7}
                pathOptions={{ color: '#fff', weight: 1.5, fillColor: scoreColor(l.score), fillOpacity: 0.95 }}
              >
                <Popup>
                  <div className="text-sm">
                    <p className="font-semibold">{l.nombre}</p>
                    <p className="text-xs">Score: <span className="font-mono font-semibold">{l.score ?? '—'}</span> · Etapa: {l.etapa ?? 'nuevo'}</p>
                    <p className="text-xs text-muted-foreground">{l.giro ?? '—'} · Línea: {lineaNombre(l.linea_recomendada)}</p>
                    {l.temp_zona !== undefined && <p className="text-xs">🌡️ {l.temp_zona} °C en zona</p>}
                    <button type="button" onClick={() => navigate('/leads?lead=' + l.lead_id)} style={{ marginTop: 6, padding: '4px 8px', borderRadius: 6, background: '#0E5FD8', color: '#fff', fontSize: 12, cursor: 'pointer', border: 'none' }}>Ver ficha</button>
                  </div>
                </Popup>
              </CircleMarker>
            ))}
            {capaLinea && curados.map((l) => (
              <CircleMarker
                key={`r${l.lead_id}`}
                center={[l.lat!, l.lon!]}
                radius={3}
                pathOptions={{ color: lineaColor(l.linea_recomendada), weight: 2, fillColor: lineaColor(l.linea_recomendada), fillOpacity: 0.9 }}
                interactive={false}
              />
            ))}
            {/* Sección 1: atractores del reporte (puntos por categoría; la
                posición se extrae de la URL de Maps del propio payload) */}
            {capaAtractores && atractores.map((x, i) => (
              <CircleMarker
                key={`atr${i}`}
                center={x.coords}
                radius={6}
                pathOptions={{ color: '#fff', weight: 1.5, fillColor: colorCategoria(x.item.categoria_etiqueta ?? x.item.categoria ?? 'Otro'), fillOpacity: 0.95 }}
              >
                <Popup>
                  <div className="text-sm">
                    <p className="font-semibold">{x.item.nombre ?? 'Atractor'}</p>
                    <p className="text-xs">{x.item.categoria_etiqueta ?? x.item.categoria ?? '—'}{x.item.distancia_m != null ? ` · ${Math.round(x.item.distancia_m)} m` : ''}</p>
                    {x.item.url_maps && (
                      <a href={x.item.url_maps} target="_blank" rel="noopener noreferrer" style={{ fontSize: 12 }}>Abrir en Maps ↗</a>
                    )}
                  </div>
                </Popup>
              </CircleMarker>
            ))}
            {/* Sección 1: isócronas reales del reporte (GeoJSON de
                area_alcance_tiempo.isocronas[].geometria) */}
            {capaIsocronas && isocronas.map((iso, i) => (
              <GeoJSON
                key={`iso${i}-${iso.minutos ?? 'x'}-${iso.modo ?? ''}`}
                data={{ type: 'Feature', properties: {}, geometry: iso.geometria! } as GeoJSON.Feature}
                pathOptions={{ color: colorIsocrona(i), weight: 2, fillColor: colorIsocrona(i), fillOpacity: 0.12 }}
              >
                <Popup>
                  <div className="text-sm">
                    <p className="font-semibold">Isócrona{iso.minutos != null ? ` · ${iso.minutos} min` : ''}{iso.modo ? ` · ${iso.modo}` : ''}</p>
                    {iso.poblacion != null && <p className="text-xs">Población en el área: {Math.round(iso.poblacion)}</p>}
                    {iso.competidores != null && <p className="text-xs">Competidores del giro: {iso.competidores}</p>}
                  </div>
                </Popup>
              </GeoJSON>
            ))}
          </MapContainer>
          <div className="absolute left-3 top-3 z-[500] space-y-2">
            <Card className="p-3">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Capas</p>
              <div className="space-y-2">
                <div className="flex items-center gap-2"><Switch id="c-denue" checked={capaDenue} onCheckedChange={setCapaDenue} /><Label htmlFor="c-denue" className="text-sm">Establecimientos DENUE ({leads.length})</Label></div>
                <div className="flex items-center gap-2"><Switch id="c-leads" checked={capaLeads} onCheckedChange={setCapaLeads} /><Label htmlFor="c-leads" className="text-sm">Leads ({curados.length})</Label></div>
                <div className="flex items-center gap-2"><Switch id="c-heat" checked={capaHeat} onCheckedChange={setCapaHeat} /><Label htmlFor="c-heat" className="text-sm">Mapa de calor IDT</Label></div>
                <div className="flex items-center gap-2"><Switch id="c-temp" checked={capaTemp} onCheckedChange={setCapaTemp} /><Label htmlFor="c-temp" className="text-sm">Temperatura de zona (Radar)</Label></div>
                <div className="flex items-center gap-2"><Switch id="c-linea" checked={capaLinea} onCheckedChange={setCapaLinea} /><Label htmlFor="c-linea" className="text-sm">Líneas recomendadas (Radar)</Label></div>
                {atractores.length > 0 && (
                  <div className="flex items-center gap-2"><Switch id="c-atr" checked={capaAtractores} onCheckedChange={setCapaAtractores} /><Label htmlFor="c-atr" className="text-sm">Atractores ({atractores.length})</Label></div>
                )}
                {isocronas.length > 0 && (
                  <div className="flex items-center gap-2"><Switch id="c-iso" checked={capaIsocronas} onCheckedChange={setCapaIsocronas} /><Label htmlFor="c-iso" className="text-sm">Isócronas ({isocronas.length})</Label></div>
                )}
              <p className="pt-1 text-xs font-medium">Mostrando {capaDenue ? leads.length : 0} establecimientos · {capaLeads ? curados.length : 0} leads</p>
              {modoRadar && <p className="pt-1"><Badge variant="accent">Preset Radar activo</Badge></p>}
              </div>
              <div className="mt-3 border-t pt-2 text-[11px] text-muted-foreground">
                <p className="font-semibold text-foreground">Leyenda</p>
                <p><span className="mr-1 inline-block h-2.5 w-2.5 rounded-full" style={{ background: '#D64545' }} /> estrato 251+</p>
                <p><span className="mr-1 inline-block h-2.5 w-2.5 rounded-full" style={{ background: '#E8A13D' }} /> estrato 51-100</p>
                <p><span className="mr-1 inline-block h-2.5 w-2.5 rounded-full" style={{ background: '#00B39B' }} /> estrato 11-50</p>
                <p><span className="mr-1 inline-block h-2.5 w-2.5 rounded-full" style={{ background: '#8a93a6' }} /> micro</p>
                <p className="mt-1 font-semibold text-foreground">Score de leads</p>
                <p><span className="mr-1 inline-block h-2.5 w-2.5 rounded-full" style={{ background: '#2F9E44' }} /> score ≥ 70</p>
                <p><span className="mr-1 inline-block h-2.5 w-2.5 rounded-full" style={{ background: '#E8A13D' }} /> score 40–69</p>
                <p><span className="mr-1 inline-block h-2.5 w-2.5 rounded-full" style={{ background: '#8a93a6' }} /> score &lt; 40</p>
                <p><span className="mr-1 inline-block h-2.5 w-2.5 rounded-sm border-2" style={{ borderColor: '#0E5FD8' }} /> polígono / radios de investigación</p>
                <p className="mt-1 font-semibold text-foreground">Línea recomendada</p>
                <p><span className="mr-1 inline-block h-2.5 w-2.5 rounded-full" style={{ background: '#E8590C' }} /> Koolkat · control térmico</p>
                <p><span className="mr-1 inline-block h-2.5 w-2.5 rounded-full" style={{ background: '#E8A13D' }} /> Solar · paneles</p>
                <p><span className="mr-1 inline-block h-2.5 w-2.5 rounded-full" style={{ background: '#0E5FD8' }} /> Evaporativa · bioclimatización</p>
                {categoriasAtractores.length > 0 && (
                  <>
                    <p className="mt-1 font-semibold text-foreground">Atractores por categoría</p>
                    {categoriasAtractores.map((c) => (
                      <p key={c}><span className="mr-1 inline-block h-2.5 w-2.5 rounded-full" style={{ background: colorCategoria(c) }} /> {c}</p>
                    ))}
                  </>
                )}
                {isocronas.length > 0 && <p className="mt-1"><span className="mr-1 inline-block h-2.5 w-2.5 rounded-sm border-2" style={{ borderColor: '#0E5FD8' }} /> isócronas del reporte (5/10/15 min)</p>}
              </div>
            </Card>
          </div>
        </div>
        <aside className="mapa-panel w-full shrink-0 space-y-4 overflow-y-auto border-t bg-card p-4 md:w-80 md:border-l md:border-t-0">
          {modoRadar && (
            <Card>
              <CardHeader>
                <CardTitle>Filtros geográficos · Radar</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <label className="block text-xs font-medium">Entidad
                  <NativeSelect className="mt-1 w-full" value={geo.sel.entidad} onChange={(e) => geo.cambiar('entidad', e.target.value)} aria-label="Entidad (Radar)">
                    <option value="">Todas</option>
                    {geo.opts.entidades.map((v) => <option key={v} value={v}>{v}</option>)}
                  </NativeSelect>
                </label>
                <label className="block text-xs font-medium">Municipio
                  <NativeSelect className="mt-1 w-full" value={geo.sel.municipio} onChange={(e) => geo.cambiar('municipio', e.target.value)} aria-label="Municipio (Radar)">
                    <option value="">Todos</option>
                    {geo.opts.municipios.map((v) => <option key={v} value={v}>{v}</option>)}
                  </NativeSelect>
                </label>
                <label className="block text-xs font-medium">Colonia
                  <NativeSelect className="mt-1 w-full" value={geo.sel.colonia} onChange={(e) => geo.cambiar('colonia', e.target.value)} aria-label="Colonia (Radar)">
                    <option value="">Todas</option>
                    {geo.opts.colonias.map((v) => <option key={v} value={v}>{v}</option>)}
                  </NativeSelect>
                </label>
                <label className="block text-xs font-medium">CP
                  <NativeSelect className="mt-1 w-full" value={geo.sel.cp} onChange={(e) => geo.cambiar('cp', e.target.value)} aria-label="CP (Radar)">
                    <option value="">Todos</option>
                    {geo.opts.cps.map((v) => <option key={v} value={v}>{v}</option>)}
                  </NativeSelect>
                </label>
                <label className="block text-xs font-medium">SCIAN
                  <NativeSelect className="mt-1 w-full" value={geo.sel.scian} onChange={(e) => geo.cambiar('scian', e.target.value)} aria-label="SCIAN (Radar)">
                    <option value="">Todos</option>
                    {geo.opts.scians.map((v) => <option key={v} value={v}>{v}</option>)}
                  </NativeSelect>
                </label>
                {geo.activo && <Button size="sm" variant="ghost" onClick={geo.limpiar}>Limpiar geografía</Button>}
                <p className="text-[11px] text-muted-foreground">
                  Cascada de <code>GET /catalogs/geo-filters</code>; filtra la capa de leads vía <code>GET /leads/curados</code> (AND). Mostrando {curados.length} leads con coordenadas.
                </p>
              </CardContent>
            </Card>
          )}
          <Card>
            <CardHeader><CardTitle>Reporte de la investigación</CardTitle></CardHeader>
            <CardContent className="space-y-2 text-sm">
              {!invIdParam && !reporteIdParam ? (
                <p className="text-muted-foreground">
                  Sin investigación activa: las capas de <strong>Atractores</strong> e <strong>Isócronas</strong> aparecen cuando el mapa se abre con <code>?inv=</code> (desde el Historial) y su reporte trae esos datos. Sin datos, las capas no se muestran — nada inventado.
                </p>
              ) : cargandoReporte ? (
                <div className="flex items-center gap-2 text-muted-foreground"><Spinner size={16} /> Cargando reporte…</div>
              ) : !reporteMapa ? (
                <>
                  <p className="text-muted-foreground">
                    La investigación está cargada pero aún no hay un reporte asociado en esta vista (la API no lista reportes por investigación). Genera el reporte para pintar atractores e isócronas desde su payload real, o abre el mapa con <code>&amp;reporte=&lt;id&gt;</code>.
                  </p>
                  <Button size="sm" onClick={generarReporteMapa} disabled={!invActual || invCentro == null}>
                    Generar reporte de esta investigación
                  </Button>
                </>
              ) : (
                <>
                  <KpiRow label="Atractores pintados" valor={String(atractores.length)} fuente="payload.atractores_trafico.items" />
                  {atractoresSinCoords > 0 && (
                    <p className="text-[11px] text-muted-foreground">{atractoresSinCoords} atractores del payload no traen coordenadas en su URL de Maps y no se pintaron.</p>
                  )}
                  <KpiRow label="Isócronas pintadas" valor={String(isocronas.length)} fuente="payload.area_alcance_tiempo.isocronas" />
                  {atractores.length === 0 && isocronas.length === 0 && (
                    <p className="text-muted-foreground">
                      El reporte no trae atractores ni isócronas (p. ej. Valhalla no respondió y el alcance quedó como radios): las capas no aparecen.
                    </p>
                  )}
                  {reporteMapa.payload?.area_alcance_tiempo?.alcance_tipo && (
                    <p className="text-[11px] text-muted-foreground">Tipo de alcance del reporte: {reporteMapa.payload.area_alcance_tiempo.alcance_tipo}.</p>
                  )}
                </>
              )}
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>Polígono activo</CardTitle></CardHeader>
            <CardContent className="space-y-2 text-sm">
              {error && <Alert variant="destructive"><AlertTitle>Error</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>}
              {!poligono && !analizando && (
                <Empty title="Sin polígono" description="Dibuja un polígono en el mapa (herramientas de la izquierda) para calcular los KPIs del territorio." icon="⬡" />
              )}
              {analizando && <div className="flex items-center gap-2 text-muted-foreground"><Spinner size={16} /> Analizando territorio…</div>}
              {poligono && (
                <>
                  <KpiRow label="Área" valor={fmtNum(areaLocal(poligono), ' km²')} fuente="Calculado localmente (GeoJSON)" />
                  {b2b && (
                    <>
                      <KpiRow label="Candidatos B2B" valor={fmtNum(b2b.total_candidatos)} fuente="DENUE + scoring B2B" />
                      {(b2b.leads ?? []).slice(0, 5).map((l) => (
                        <div key={l.denue_id ?? l.nombre} className="flex items-baseline justify-between border-b py-1.5 text-xs last:border-0">
                          <span className="truncate text-muted-foreground" title={l.nombre}>{l.nombre ?? '—'}</span>
                          <span className="ml-2 shrink-0 font-mono font-semibold">{l.score !== undefined ? l.score.toFixed(0) : '—'}</span>
                        </div>
                      ))}
                      <div className="flex flex-wrap gap-2 pt-2">
                        <Button size="sm" onClick={() => navigate('/leads')}>Ver leads →</Button>
                        <Button size="sm" variant="outline" onClick={() => navigate('/reporte')}>Generar reporte</Button>
                      </div>
                    </>
                  )}
                </>
              )}
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>Establecimientos</CardTitle></CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">{leads.length} pines cargados en el territorio.</p>
              {leads.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {topEstratos(leads).map(([e, n]) => (
                    <Badge key={e} variant="secondary">{e}: {n}</Badge>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </aside>
      </MapaExpandible>
    </div>
  );
}

const PALETA_ATRACTORES = ['#0E5FD8', '#E8590C', '#2F9E44', '#9333EA', '#B98A04', '#0EA5A5', '#D64545', '#64748B'];

/** Color estable por categoría de atractor (hash del nombre). */
function colorCategoria(cat: string): string {
  let h = 0;
  for (const c of cat) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return PALETA_ATRACTORES[h % PALETA_ATRACTORES.length];
}

const COLORES_ISOCRONA = ['#0E5FD8', '#E8590C', '#2F9E44'];

function colorIsocrona(i: number): string {
  return COLORES_ISOCRONA[i % COLORES_ISOCRONA.length];
}

function heatColor(idt?: number): string {
  const v = idt ?? 0;
  if (v >= 75) return '#D64545';
  if (v >= 50) return '#E8590C';
  if (v >= 25) return '#E8A13D';
  return '#00B39B';
}

/** Color del círculo de temperatura por °C (Open-Meteo, módulo Radar). */
function tempColor(temp?: number): string {
  const t = temp ?? 0;
  if (t >= 35) return '#D64545';
  if (t >= 30) return '#E8590C';
  if (t >= 25) return '#E8A13D';
  return '#00B39B';
}

function lineaNombre(linea?: string): string {
  switch ((linea ?? '').toLowerCase()) {
    case 'koolkat': return 'Koolkat';
    case 'solar': return 'Solar';
    case 'evaporativa': return 'Evaporativa';
    default: return linea ?? '—';
  }
}

function areaLocal(g: GeoJSON.GeoJSON): number | undefined {
  try {
    if (g.type === 'Polygon' || g.type === 'MultiPolygon') {
      return areaKm2(g as GeoJSON.Polygon | GeoJSON.MultiPolygon);
    }
  } catch { /* ignorar */ }
  return undefined;
}

function fmtNum(v: unknown, sufijo = ''): string {
  if (typeof v === 'number') return `${v % 1 === 0 ? v : v.toFixed(1)}${sufijo}`;
  return '—';
}

function KpiRow({ label, valor, fuente }: { label: string; valor: string; fuente: string }) {
  return (
    <div className="flex items-baseline justify-between border-b py-1.5 last:border-0" title={`Fuente: ${fuente}`}>
      <span className="text-muted-foreground">{label}</span>
      <span className="font-mono font-semibold">{valor}</span>
    </div>
  );
}

function topEstratos(leads: Lead[]): [string, number][] {
  const m = new Map<string, number>();
  for (const l of leads) {
    const e = l.estrato ?? 'Sin estrato';
    m.set(e, (m.get(e) ?? 0) + 1);
  }
  return [...m.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5);
}

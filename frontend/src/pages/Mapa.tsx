import * as React from 'react';
import { useNavigate } from 'react-router-dom';
import { MapContainer, TileLayer, CircleMarker, Popup, GeoJSON, useMap, ZoomControl } from 'react-leaflet';
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
import { get, post, errorMessage, type Lead, type LeadCurado, lineaColor } from '@/lib/api';
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
  const [b2b, setB2b] = React.useState<B2bResult | null>(null);
  const [analizando, setAnalizando] = React.useState(false);
  const setTerritorio = useGeisStore((s) => s.setTerritorio);
  const navigate = useNavigate();

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
      <Topbar titulo="Mapa geoespacial" subtitulo="Geofencing, clústeres y demanda térmica · DENUE + IDT + Radar" />
      <div className="flex min-h-0 flex-1 flex-col md:flex-row">
        <div className="relative h-[55vh] min-w-0 flex-1 md:h-auto">
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
            {capaLinea && curados.map((l) => (
              <CircleMarker
                key={`r${l.lead_id}`}
                center={[l.lat!, l.lon!]}
                radius={7}
                pathOptions={{ color: '#fff', weight: 1.5, fillColor: lineaColor(l.linea_recomendada), fillOpacity: 0.95 }}
              >
                <Popup>
                  <div className="text-sm">
                    <p className="font-semibold">{l.nombre}</p>
                    <p className="text-xs text-muted-foreground">{l.giro ?? '—'} · Etapa: {l.etapa ?? 'nuevo'}</p>
                    <p className="text-xs">Línea: <strong style={{ color: lineaColor(l.linea_recomendada) }}>{lineaNombre(l.linea_recomendada)}</strong></p>
                    {l.temp_zona !== undefined && <p className="text-xs">🌡️ {l.temp_zona} °C en zona</p>}
                    {l.score !== undefined && <p className="text-xs">Score: <span className="font-mono font-semibold">{l.score}</span></p>}
                  </div>
                </Popup>
              </CircleMarker>
            ))}
          </MapContainer>
          <div className="absolute left-3 top-3 z-[500] space-y-2">
            <Card className="p-3">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Capas</p>
              <div className="space-y-2">
                <div className="flex items-center gap-2"><Switch id="c-denue" checked={capaDenue} onCheckedChange={setCapaDenue} /><Label htmlFor="c-denue" className="text-sm">Establecimientos DENUE</Label></div>
                <div className="flex items-center gap-2"><Switch id="c-heat" checked={capaHeat} onCheckedChange={setCapaHeat} /><Label htmlFor="c-heat" className="text-sm">Mapa de calor IDT</Label></div>
                <div className="flex items-center gap-2"><Switch id="c-temp" checked={capaTemp} onCheckedChange={setCapaTemp} /><Label htmlFor="c-temp" className="text-sm">Temperatura de zona (Radar)</Label></div>
                <div className="flex items-center gap-2"><Switch id="c-linea" checked={capaLinea} onCheckedChange={setCapaLinea} /><Label htmlFor="c-linea" className="text-sm">Líneas recomendadas (Radar)</Label></div>
              </div>
              <div className="mt-3 border-t pt-2 text-[11px] text-muted-foreground">
                <p className="font-semibold text-foreground">Leyenda</p>
                <p><span className="mr-1 inline-block h-2.5 w-2.5 rounded-full" style={{ background: '#D64545' }} /> estrato 251+</p>
                <p><span className="mr-1 inline-block h-2.5 w-2.5 rounded-full" style={{ background: '#E8A13D' }} /> estrato 51-100</p>
                <p><span className="mr-1 inline-block h-2.5 w-2.5 rounded-full" style={{ background: '#00B39B' }} /> estrato 11-50</p>
                <p><span className="mr-1 inline-block h-2.5 w-2.5 rounded-full" style={{ background: '#8a93a6' }} /> micro</p>
                <p className="mt-1 font-semibold text-foreground">Línea recomendada</p>
                <p><span className="mr-1 inline-block h-2.5 w-2.5 rounded-full" style={{ background: '#E8590C' }} /> Koolkat · control térmico</p>
                <p><span className="mr-1 inline-block h-2.5 w-2.5 rounded-full" style={{ background: '#E8A13D' }} /> Solar · paneles</p>
                <p><span className="mr-1 inline-block h-2.5 w-2.5 rounded-full" style={{ background: '#0E5FD8' }} /> Evaporativa · bioclimatización</p>
              </div>
            </Card>
          </div>
        </div>
        <aside className="w-full shrink-0 space-y-4 overflow-y-auto border-t bg-card p-4 md:w-80 md:border-l md:border-t-0">
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
      </div>
    </div>
  );
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

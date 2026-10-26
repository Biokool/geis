import * as React from 'react';
import { useNavigate } from 'react-router-dom';
import { MapContainer, TileLayer, GeoJSON, useMap } from 'react-leaflet';
import L from 'leaflet';
import '@geoman-io/leaflet-geoman-free';
import { Topbar } from '@/components/layout/Topbar';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Field } from '@/components/ui/Field';
import { Spinner } from '@/components/ui/Spinner';
import { Empty } from '@/components/ui/Empty';
import { MapaExpandible } from '@/components/map/MapaExpandible';
import { areaKm2, downloadBlob } from '@/lib/geo';
import { useGeisStore } from '@/store';
import { toast } from 'sonner';

function DrawControl({ onChange }: { onChange: (g: GeoJSON.GeoJSON | null) => void }) {
  const map = useMap();
  React.useEffect(() => {
    const m = map as unknown as {
      pm: { addControls: (o: Record<string, unknown>) => void; removeControls: () => void; setLang: (l: string) => void };
      on: (ev: string, fn: (e: { layer: L.Layer }) => void) => void;
      off: (ev: string) => void;
    };
    try { m.pm.setLang('es'); } catch { /* noop */ }
    m.pm.addControls({
      position: 'topleft', drawMarker: false, drawCircleMarker: false, drawPolyline: false,
      drawRectangle: true, drawPolygon: true, drawCircle: true, drawText: false,
      editMode: true, dragMode: true, cutPolygon: true, removalMode: true,
    });
    const created = (e: { layer: L.Layer }) => onChange((e.layer as L.Polygon).toGeoJSON() as unknown as GeoJSON.GeoJSON);
    const removed = () => onChange(null);
    m.on('pm:create', created);
    m.on('pm:remove', removed);
    return () => { m.off('pm:create'); m.off('pm:remove'); m.pm.removeControls(); };
  }, [map, onChange]);
  return null;
}

export default function Geofencing() {
  const navigate = useNavigate();
  const [geo, setGeo] = React.useState<GeoJSON.GeoJSON | null>(null);
  const [nombre, setNombre] = React.useState('');
  const [activando, setActivando] = React.useState(false);
  const setTerritorio = useGeisStore((s) => s.setTerritorio);

  const area = React.useMemo(() => {
    if (!geo) return null;
    try {
      if (geo.type === 'Polygon' || geo.type === 'MultiPolygon') {
        return areaKm2(geo as GeoJSON.Polygon | GeoJSON.MultiPolygon);
      }
    } catch { /* noop */ }
    return null;
  }, [geo]);

  /**
   * El backend aún no persiste territorios (sin POST /territories/from-polygon):
   * el polígono se activa como territorio de la sesión y viaja al Mapa/KPIs/Reporte.
   */
  const activar = () => {
    if (!geo) return;
    setActivando(true);
    try {
      setTerritorio({
        nombre: nombre || `Territorio ${new Date().toLocaleDateString('es-MX')}`,
        tipo: 'polygon',
        geojson: geo,
        area_km2: area ?? undefined,
      });
      toast.success('Territorio activado', { description: 'Disponible en esta sesión para Mapa, KPIs y Reporte.' });
      navigate('/mapa');
    } finally {
      setActivando(false);
    }
  };

  const exportar = () => {
    if (!geo) return;
    downloadBlob(JSON.stringify({ type: 'FeatureCollection', features: [{ type: 'Feature', properties: { nombre }, geometry: geo }] }, null, 2), `${nombre || 'territorio'}.geojson`, 'application/geo+json');
  };

  return (
    <div className="flex h-full flex-col">
      <Topbar titulo="Constructor de polígonos" subtitulo="Geofencing manual: dibuja, mide y activa territorios" />
      <MapaExpandible className="flex min-h-0 flex-1 flex-col md:flex-row" titulo="Constructor de polígonos">
        <div className="mapa-lienzo h-[55vh] min-w-0 flex-1 md:h-auto">
          <MapContainer center={[23.6345, -102.5528]} zoom={5} className="h-full w-full" style={{ height: '100%' }}>
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            <DrawControl onChange={setGeo} />
            {geo && <GeoJSON key={JSON.stringify(geo)} data={geo} pathOptions={{ color: '#00B39B', weight: 2, fillOpacity: 0.1 }} />}
          </MapContainer>
        </div>
        <aside className="mapa-panel w-full shrink-0 space-y-4 overflow-y-auto border-t bg-card p-4 md:w-80 md:border-l md:border-t-0">
          <Card>
            <CardHeader>
              <CardTitle>Territorio</CardTitle>
              <CardDescription>Métricas en vivo del polígono dibujado</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              {!geo ? (
                <Empty title="Sin geometría" description="Dibuja un polígono, rectángulo o círculo con las herramientas del mapa." icon="⬡" />
              ) : (
                <>
                  <div className="flex justify-between border-b py-1.5">
                    <span className="text-muted-foreground">Tipo</span>
                    <span className="font-medium">{geo.type}</span>
                  </div>
                  <div className="flex justify-between border-b py-1.5">
                    <span className="text-muted-foreground">Área</span>
                    <span className="font-mono font-semibold">{area !== null ? `${area.toFixed(2)} km²` : '—'}</span>
                  </div>
                  <Alert variant="warning">
                    <AlertTitle>Población ≠ compradores</AlertTitle>
                    <AlertDescription>
                      La población y los establecimientos contenidos se calculan al analizar el territorio contra
                      DENUE y Censo vigentes: son cifras observadas, no una estimación de clientes.
                    </AlertDescription>
                  </Alert>
                  <Field label="Nombre del territorio" htmlFor="tnombre">
                    <Input id="tnombre" placeholder="Corredor Apodaca" value={nombre} onChange={(e) => setNombre(e.target.value)} />
                  </Field>
                  <div className="flex flex-wrap gap-2">
                    <Button onClick={activar} disabled={activando}>
                      {activando && <Spinner size={16} />}
                      Activar territorio
                    </Button>
                    <Button variant="outline" onClick={exportar}>GeoJSON</Button>
                  </div>
                  <p className="text-[11px] text-muted-foreground">
                    El territorio se activa en esta sesión (el backend aún no lo persiste).
                  </p>
                </>
              )}
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>Opciones</CardTitle></CardHeader>
            <CardContent className="space-y-2 text-sm text-muted-foreground">
              <p>• Dibujo libre con Geoman (polígono, rectángulo, círculo)</p>
              <p>• Importar GeoJSON/KML y buffers por isócrona: fase 2 (aún sin endpoint).</p>
            </CardContent>
          </Card>
        </aside>
      </MapaExpandible>
    </div>
  );
}

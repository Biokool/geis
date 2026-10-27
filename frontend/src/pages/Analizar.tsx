import * as React from 'react';
import { useNavigate } from 'react-router-dom';
import { MapContainer, TileLayer, Marker, useMap } from 'react-leaflet';
import L from 'leaflet';
import { Topbar } from '@/components/layout/Topbar';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Field } from '@/components/ui/Field';
import { Spinner } from '@/components/ui/Spinner';
import { Badge } from '@/components/ui/Badge';
import { MapaExpandible } from '@/components/map/MapaExpandible';
import {
  geocode, createInvestigation, createReport, deriveCompanyConfig,
  errorMessage, GIROS_CATALOGO, listGirosCatalog, listScianCatalog,
  type GeocodeResult, type GiroFicha, type ScianCatalogItem,
} from '@/lib/api';
import { toast } from 'sonner';

function sinAcentos(s: string): string {
  return s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim();
}

function CentrarMapa({ centro }: { centro: [number, number] }) {
  const map = useMap();
  React.useEffect(() => { map.setView(centro, Math.max(map.getZoom(), 15)); }, [map, centro]);
  return null;
}

const iconoPin = L.divIcon({
  className: 'geis-pin-analizar',
  html: '<span style="display:flex;align-items:center;justify-content:center;width:30px;height:30px;border-radius:9999px 9999px 9999px 4px;background:#0E5FD8;color:#fff;font-size:16px;border:2px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,.45);transform:rotate(-45deg)"><span style="transform:rotate(45deg)">●</span></span>',
  iconSize: [30, 30],
  iconAnchor: [15, 28],
});

interface Punto extends GeocodeResult { confirmado: boolean }

/** Deja solo el código de 6 dígitos (las fichas pueden traer "531112 — …"). */
const codigoScian = (valor: string) => (valor.match(/\d{6}/) ?? [''])[0];

export default function Analizar() {
  const navigate = useNavigate();
  const [giro, setGiro] = React.useState('');
  const [scian, setScian] = React.useState('');
  const [scianNota, setScianNota] = React.useState<string | null>(null);
  const [mostrarSugerencias, setMostrarSugerencias] = React.useState(false);
  const [girosExtra, setGirosExtra] = React.useState<GiroFicha[]>([]);
  const [catalogoGiros, setCatalogoGiros] = React.useState<GiroFicha[]>([]);
  const [catalogoScian, setCatalogoScian] = React.useState<ScianCatalogItem[]>([]);
  const [catalogoCargado, setCatalogoCargado] = React.useState(false);
  const [mostrarScian, setMostrarScian] = React.useState(false);
  const [direccion, setDireccion] = React.useState('');
  const [punto, setPunto] = React.useState<Punto | null>(null);
  const [ubicando, setUbicando] = React.useState(false);
  const [reEtiquetando, setReEtiquetando] = React.useState(false);
  const [analizando, setAnalizando] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [mostrarSupuestos, setMostrarSupuestos] = React.useState(false);
  const [gasto, setGasto] = React.useState('');
  const [fNse, setFNse] = React.useState('');
  const [fPen, setFPen] = React.useState('');
  const markerRef = React.useRef<L.Marker | null>(null);

  // Giros del perfil de empresa activo (palabras clave del ICP), si existe.
  React.useEffect(() => {
    let vivo = true;
    deriveCompanyConfig()
      .then((cfg) => {
        if (!vivo) return;
        const extras: GiroFicha[] = (cfg.icp_keywords ?? [])
          .filter((k) => k && !GIROS_CATALOGO.some((g) => sinAcentos(g.nombre) === sinAcentos(k)))
          .map((k) => ({ nombre: k, scian: cfg.scian_targets?.slice(0, 1) ?? [], alias: [k] }));
        setGirosExtra(extras);
      })
      .catch(() => { /* sin perfil activo: solo catálogo local */ });
    return () => { vivo = false; };
  }, []);

  // Catálogo real del backend (giros con alias + clases SCIAN) para el autocompletado.
  React.useEffect(() => {
    let vivo = true;
    Promise.all([listGirosCatalog(), listScianCatalog()])
      .then(([giros, scian]) => {
        if (!vivo) return;
        const vistos = new Set(GIROS_CATALOGO.map((g) => sinAcentos(g.nombre)));
        const fichas: GiroFicha[] = [];
        for (const g of giros.items) {
          const clave = sinAcentos(g.giro);
          if (vistos.has(clave)) continue;
          vistos.add(clave);
          fichas.push({
            nombre: g.giro,
            scian: [g.scian_code],
            alias: [g.giro, g.description ?? ''].filter(Boolean),
          });
        }
        for (const s of scian.items) {
          const nombre = s.description ?? s.scian_code;
          const clave = sinAcentos(nombre);
          if (vistos.has(clave)) continue;
          vistos.add(clave);
          fichas.push({ nombre, scian: [s.scian_code], alias: [nombre, s.scian_code] });
        }
        setCatalogoGiros(fichas);
        setCatalogoScian(scian.items);
      })
      .catch(() => { /* catálogo caído: quedan los 15 giros locales */ })
      .finally(() => { if (vivo) setCatalogoCargado(true); });
    return () => { vivo = false; };
  }, []);

  const todosGiros = React.useMemo(() => {
    const vistos = new Set<string>();
    const lista: GiroFicha[] = [];
    for (const f of [...GIROS_CATALOGO, ...girosExtra, ...catalogoGiros]) {
      const clave = sinAcentos(f.nombre);
      if (vistos.has(clave)) continue;
      vistos.add(clave);
      lista.push(f);
    }
    return lista;
  }, [girosExtra, catalogoGiros]);

  const sugerencias = React.useMemo(() => {
    const q = sinAcentos(giro);
    const base = q
      ? todosGiros.filter((g) => sinAcentos(g.nombre).includes(q) || g.alias.some((a) => sinAcentos(a).includes(q)))
      : todosGiros;
    const orden = q
      ? [...base].sort((a, b) => {
          const ea = sinAcentos(a.nombre);
          const eb = sinAcentos(b.nombre);
          return Number(!ea.startsWith(q)) - Number(!eb.startsWith(q)) || ea.localeCompare(eb);
        })
      : base;
    return orden.slice(0, 60);
  }, [giro, todosGiros]);

  const scianSugerencias = React.useMemo(() => {
    const q = scian.trim();
    if (!q) return catalogoScian.slice(0, 40);
    const t = sinAcentos(q);
    return catalogoScian
      .filter((s) => s.scian_code.includes(q) || sinAcentos(s.description ?? '').includes(t))
      .slice(0, 40);
  }, [scian, catalogoScian]);

  const elegirScian = (s: ScianCatalogItem) => {
    setScian(s.scian_code);
    setMostrarScian(false);
    setScianNota(
      s.description
        ? `SCIAN ${s.scian_code} — ${s.description}. Editable.`
        : `SCIAN ${s.scian_code}. Editable.`,
    );
  };

  const elegirGiro = (f: GiroFicha) => {
    setGiro(f.nombre);
    setMostrarSugerencias(false);
    if (f.scian.length > 0) {
      setScian(codigoScian(f.scian[0]));
      setScianNota(
        f.scian.length > 1
          ? `Ficha con varias clases SCIAN (${f.scian.join(', ')}); se usa la primera. Puedes corregirla antes de analizar.`
          : 'SCIAN de la ficha del catálogo sectorial. Puedes corregirlo antes de analizar.',
      );
    } else {
      setScian('');
      setScianNota('Este giro no trae SCIAN de catálogo: se resuelve automáticamente en el backend al analizar.');
    }
  };

  const alEscribirGiro = (v: string) => {
    setGiro(v);
    setMostrarSugerencias(true);
    const q = sinAcentos(v);
    const exacta = todosGiros.find((g) => sinAcentos(g.nombre) === q || g.alias.some((a) => sinAcentos(a) === q));
    if (exacta && exacta.scian.length > 0) {
      setScian(codigoScian(exacta.scian[0]));
      setScianNota('SCIAN de la ficha del catálogo sectorial. Editable.');
    } else if (v.trim()) {
      setScianNota('Sin ficha exacta en el catálogo: el SCIAN se resuelve automáticamente en el backend al analizar (puedes forzarlo escribiéndolo aquí).');
    }
  };

  const ubicar = async () => {
    if (!direccion.trim()) return;
    setUbicando(true);
    setError(null);
    try {
      const g = await geocode({ address: direccion.trim() });
      setPunto({ ...g, confirmado: true });
      toast.success('Ubicación resuelta', { description: g.label });
    } catch (e) {
      setPunto(null);
      setError(errorMessage(e));
    } finally { setUbicando(false); }
  };

  const alArrastrarPin = async () => {
    const m = markerRef.current;
    if (!m) return;
    const { lat, lng } = m.getLatLng();
    setPunto((p) => (p ? { ...p, lat, lon: lng, confirmado: true } : p));
    // Reverse con el mismo endpoint para refrescar colonia/municipio/entidad.
    setReEtiquetando(true);
    try {
      const g = await geocode({ lat, lon: lng });
      setPunto({ ...g, confirmado: true });
    } catch {
      toast.warning('Pin movido, pero no se pudo re-etiquetar', { description: 'Se conservan las coordenadas nuevas; la etiqueta textual es la anterior.' });
      setPunto((p) => (p ? { ...p, lat, lon: lng } : p));
    } finally { setReEtiquetando(false); }
  };

  const analizar = async () => {
    if (!punto || !giro.trim()) return;
    setAnalizando(true);
    setError(null);
    try {
      let invId: string | undefined;
      try {
        const inv = await createInvestigation({
          title: `Análisis · ${giro.trim()} — ${punto.label}`,
          investigation_type: 'location_viability',
          territory_kind: 'point_buffers',
          center_lat: punto.lat,
          center_lon: punto.lon,
          radii_m: [1000, 2000],
          params: { giro: giro.trim(), ...(scian.trim() ? { scian: scian.trim() } : {}) },
        });
        invId = inv.investigation_id;
      } catch (e) {
        toast.warning('No se pudo crear la investigación; el reporte se genera sin asociar', { description: errorMessage(e) });
      }
      const overrides: Record<string, number> = {};
      if (gasto !== '' && Number(gasto) > 0) overrides.gasto_promedio_mensual = Number(gasto);
      if (fNse !== '' && Number(fNse) > 0) overrides.f_nse = Number(fNse);
      if (fPen !== '' && Number(fPen) > 0) overrides.f_pen = Number(fPen);
      const rep = await createReport({
        investigation_id: invId,
        title: `Análisis para ${giro.trim()}`,
        giro: giro.trim(),
        scian: scian.trim() || undefined,
        lat: punto.lat,
        lon: punto.lon,
        radios: [1000, 2000],
        ...overrides,
      });
      if (invId && rep.report_id) {
        // Puente reporte→investigación (el ReportOut no la referencia):
        // lo usa Reporte.tsx para saber si aplica el modo inmobiliario.
        try { localStorage.setItem(`geis:reporte-inv:${rep.report_id}`, invId); } catch { /* sin persistencia local */ }
      }
      toast.success('Reporte listo');
      navigate(`/reporte?reporte=${rep.report_id}`);
    } catch (e) {
      setError(errorMessage(e));
    } finally { setAnalizando(false); }
  };

  const listo = giro.trim() !== '' && punto !== null;

  return (
    <div className="flex h-full flex-col">
      <Topbar titulo="Analizar una ubicación" subtitulo="El flujo Sabueso: 2 campos + 1 clic → reporte completo en una pantalla" />
      <div className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-3xl space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>¿Qué negocio y dónde?</CardTitle>
              <CardDescription>
                Escribe el giro, pega la dirección o un link de Google Maps, confirma el pin y pulsa «Analizar».
                La geocodificación es real (Nominatim/OSM y parser de links): si la dirección no resuelve, lo verás aquí — nunca se analiza un punto falso.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              {/* Campo 1: giro con autocompletado */}
              <div className="relative">
                <Field label="1 · Giro del negocio" htmlFor="an-giro" required>
                  <Input
                    id="an-giro"
                    placeholder="Ej. gasolinera, abarrotes, gimnasio…"
                    value={giro}
                    autoComplete="off"
                    onChange={(e) => alEscribirGiro(e.target.value)}
                    onFocus={() => setMostrarSugerencias(true)}
                    onBlur={() => window.setTimeout(() => setMostrarSugerencias(false), 150)}
                  />
                </Field>
                {mostrarSugerencias && sugerencias.length > 0 && (
                  <ul className="absolute z-20 mt-1 max-h-56 w-full overflow-y-auto rounded-md border bg-card shadow-lg">
                    {sugerencias.map((f) => (
                      <li key={`${f.nombre}-${f.scian[0] ?? 'auto'}`}>
                        <button type="button" className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm hover:bg-muted/60" onMouseDown={(e) => e.preventDefault()} onClick={() => elegirGiro(f)}>
                          <span className="font-medium">{f.nombre}</span>
                          <span className="font-mono text-xs text-muted-foreground">{f.scian.length ? `SCIAN ${f.scian.join(', ')}` : 'SCIAN automático'}</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
                <div className="mt-2 grid gap-2 sm:grid-cols-[1fr_auto] sm:items-end">
                  <div className="relative">
                    <Field label="SCIAN (editable)" htmlFor="an-scian">
                      <Input
                        id="an-scian"
                        placeholder={catalogoCargado ? 'Código o giro (ej. 491110 o gasolinera)' : 'Se resuelve automáticamente'}
                        value={scian}
                        autoComplete="off"
                        onChange={(e) => { setScian(e.target.value); setMostrarScian(true); setScianNota('SCIAN capturado manualmente: se enviará tal cual al análisis.'); }}
                        onFocus={() => setMostrarScian(true)}
                        onBlur={() => window.setTimeout(() => setMostrarScian(false), 150)}
                        className="font-mono"
                      />
                    </Field>
                    {mostrarScian && scianSugerencias.length > 0 && (
                      <ul className="absolute z-20 mt-1 max-h-64 w-full overflow-y-auto rounded-md border bg-card shadow-lg">
                        {scianSugerencias.map((s) => (
                          <li key={s.scian_code}>
                            <button type="button" className="flex w-full items-center gap-3 px-3 py-2 text-left text-sm hover:bg-muted/60" onMouseDown={(e) => e.preventDefault()} onClick={() => elegirScian(s)}>
                              <span className="shrink-0 font-mono text-xs text-muted-foreground">{s.scian_code}</span>
                              <span className="truncate">{s.description ?? 'Sin descripción'}</span>
                            </button>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                  <span className="pb-1 text-xs text-muted-foreground">Si lo dejas vacío, lo resuelve el backend.</span>
                </div>
                {scianNota && <p className="mt-1 text-xs text-muted-foreground">{scianNota}</p>}
                {catalogoCargado && (
                  <p className="mt-1 text-xs text-muted-foreground">
                    Catálogo cargado: {catalogoGiros.length} giros y {catalogoScian.length} clases SCIAN. Escribe en cualquiera de los dos campos para filtrar.
                  </p>
                )}
              </div>

              {/* Campo 2: dirección / link */}
              <div>
                <Field label="2 · Dirección o link de Google Maps" htmlFor="an-dir" required>
                  <Input
                    id="an-dir"
                    placeholder="Av. Álvaro Obregón 120, Roma Norte, CDMX — o pega el link de Maps"
                    value={direccion}
                    onChange={(e) => setDireccion(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); void ubicar(); } }}
                  />
                </Field>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <Button type="button" onClick={ubicar} disabled={ubicando || !direccion.trim()}>
                    {ubicando && <Spinner size={16} />} Ubicar
                  </Button>
                  {punto && (
                    <Badge variant="outline">
                      Fuente: {punto.fuente === 'link_maps' ? 'link de Maps' : punto.fuente === 'coordenadas' ? 'coordenadas' : punto.fuente === 'nominatim' ? 'Nominatim/OSM' : punto.fuente}
                    </Badge>
                  )}
                </div>
              </div>

              {error && (
                <Alert variant="destructive">
                  <AlertTitle>No se pudo completar el paso</AlertTitle>
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}

              {/* Confirmación visual: minimapa con pin arrastrable */}
              {punto && (
                <div className="space-y-2">
                  <MapaExpandible className="h-64 w-full overflow-hidden rounded-lg border" titulo="Ubicación confirmada">
                    <MapContainer center={[punto.lat, punto.lon]} zoom={15} className="h-full w-full" style={{ height: '100%' }}>
                      <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
                      <CentrarMapa centro={[punto.lat, punto.lon]} />
                      <Marker
                        position={[punto.lat, punto.lon]}
                        icon={iconoPin}
                        draggable
                        ref={markerRef}
                        eventHandlers={{ dragend: () => { void alArrastrarPin(); } }}
                      />
                    </MapContainer>
                  </MapaExpandible>
                  <p className="text-sm">
                    📍 <strong>{punto.label}</strong>
                    {punto.direccion_formateada && punto.direccion_formateada !== punto.label && <span className="block text-xs text-muted-foreground">{punto.direccion_formateada}</span>}
                    <span className="block font-mono text-xs text-muted-foreground">{punto.lat.toFixed(5)}, {punto.lon.toFixed(5)}{punto.cp ? ` · CP ${punto.cp}` : ''}</span>
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Arrastra el pin si el punto no es exacto: al soltarlo se vuelve a geocodificar la etiqueta (colonia, municipio, entidad) con esas coordenadas.
                    {reEtiquetando && ' Re-etiquetando…'}
                  </p>
                </div>
              )}

              {/* Supuestos TAM opcionales */}
              <div>
                <Button type="button" variant="ghost" size="sm" onClick={() => setMostrarSupuestos((s) => !s)}>
                  {mostrarSupuestos ? '▾' : '▸'} Supuestos del TAM (opcionales — si no, manda la ficha del giro)
                </Button>
                {mostrarSupuestos && (
                  <div className="mt-2 grid gap-3 sm:grid-cols-3">
                    <Field label="Gasto promedio mensual (MXN)" htmlFor="an-gasto">
                      <Input id="an-gasto" type="number" min="0" step="any" value={gasto} onChange={(e) => setGasto(e.target.value)} />
                    </Field>
                    <Field label="Factor NSE" htmlFor="an-fnse">
                      <Input id="an-fnse" type="number" min="0" step="0.01" value={fNse} onChange={(e) => setFNse(e.target.value)} />
                    </Field>
                    <Field label="Factor penetración (0–1)" htmlFor="an-fpen">
                      <Input id="an-fpen" type="number" min="0" max="1" step="0.01" value={fPen} onChange={(e) => setFPen(e.target.value)} />
                    </Field>
                  </div>
                )}
              </div>

              <Button onClick={analizar} disabled={!listo || analizando} className="w-full sm:w-auto" size="lg">
                {analizando && <Spinner size={16} />}
                {analizando ? 'Analizando…' : 'Analizar'}
              </Button>
              {!listo && <p className="text-xs text-muted-foreground">Completa el giro y confirma el punto en el minimapa para habilitar el análisis.</p>}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

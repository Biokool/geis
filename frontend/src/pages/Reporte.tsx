import * as React from 'react';
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
import { EstimadoBadge } from '@/components/ui/Estimado';
import { post, get, errorMessage } from '@/lib/api';
import { verdictColor } from '@/lib/geo';
import { toast } from 'sonner';

/** Respuesta real del backend: POST /api/v1/reports (SRS §6.5, app/reports/builder.py). */
interface ReportPayload {
  cabecera?: { etiqueta?: string; titulo?: string; giro?: string; scian?: string; ubicacion?: string; lat?: number; lon?: number; fecha?: string; radios_m?: number[] };
  veredicto?: { decision?: string; confianza?: string; factores?: string[]; riesgos?: string[] };
  perfil_cliente?: { editorial?: string };
  clientes_zona?: { nota?: string; segmentos?: unknown[]; poblacion_total?: number; poblacion_objetivo?: number };
  hogares_familias?: Record<string, unknown>;
  atractores_trafico?: { nota?: string; items?: unknown[] };
  competencia?: { por_anillo?: { radio_m?: number; conteo?: number; ism?: number; ism_banda?: string }[]; lista?: unknown[] };
  mapas?: { capas?: string[]; centro?: { lat?: number; lon?: number } };
  entorno_comercial?: { total_negocios?: number; categorias?: unknown[] };
  poblacion_viviendas?: { advertencia?: string; detalle?: unknown; viviendas?: unknown };
  movimiento_acceso?: { nse_etiqueta?: string; nse_nota?: string; vialidades?: unknown[]; movilidad?: unknown };
  area_alcance_tiempo?: { isocronas?: unknown[]; como_usarla?: string };
  modelos?: {
    ism?: { formula?: string; por_anillo?: { radio_m?: number; D?: number; O?: number; ISM?: number; banda?: string }[] };
    huff?: { formula?: string; cuota_punto?: number; rango_cuota?: unknown; alpha?: number; lambda?: number };
    tam?: { formula?: string; tam_mxn_anual?: number; rango_mxn?: number[]; advertencia?: string; supuestos?: string[] };
  };
  fuentes_datos?: { ediciones?: unknown[]; fecha_calculo?: string; model_version?: string };
  metodologia_advertencias?: { estimado_vs_observado?: string[]; nota_general?: string };
}

interface ReportOut {
  report_id?: string;
  title?: string;
  verdict?: string | null;
  payload?: ReportPayload;
  created_at?: string;
  lineage?: Record<string, unknown>;
}

const mxn = (v?: number | null) =>
  typeof v === 'number'
    ? new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN', maximumFractionDigits: 0 }).format(v)
    : '—';

export default function Reporte() {
  const [giro, setGiro] = React.useState('');
  const [modo, setModo] = React.useState<'coords' | 'direccion'>('coords');
  const [lat, setLat] = React.useState('');
  const [lon, setLon] = React.useState('');
  const [direccion, setDireccion] = React.useState('');
  const [cargando, setCargando] = React.useState(false);
  const [geocodificando, setGeocodificando] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [reporte, setReporte] = React.useState<ReportOut | null>(null);
  const [crudo, setCrudo] = React.useState(false);
  const [tempZona, setTempZona] = React.useState<number | null>(null);
  const [geoNota, setGeoNota] = React.useState<string | null>(null);

  const generar = async () => {
    setCargando(true);
    setError(null);
    setReporte(null);
    setTempZona(null);
    setGeoNota(null);
    try {
      let la = Number(lat);
      let lo = Number(lon);
      if (modo === 'direccion') {
        setGeocodificando(true);
        try {
          const g = await post<{ lat: number; lon: number; label?: string; nota?: string }>('/territories/geocode', { address: direccion });
          la = g.lat; lo = g.lon;
          setGeoNota(g.label ?? `${la}, ${lo}`);
          if (g.nota) toast.warning('Geocodificación aproximada', { description: g.nota });
        } finally {
          setGeocodificando(false);
        }
      }
      const res = await post<ReportOut>('/reports', {
        title: `Reporte · ${giro}`,
        giro,
        lat: la,
        lon: lo,
        radios: [1000, 2000],
      });
      setReporte(res);
      try {
        const w = await get<{ temperature_c?: number }>('/geo/weather', { lat: String(la), lon: String(lo) });
        if (typeof w.temperature_c === 'number') setTempZona(w.temperature_c);
      } catch { /* clima opcional: el plan de contacto funciona sin él */ }
      toast.success('Reporte generado');
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setCargando(false);
    }
  };

  const payload = reporte?.payload;
  const ver = payload?.veredicto;
  const decision = ver?.decision ?? reporte?.verdict ?? 'Sin veredicto';
  const plan = reporte ? planContacto(giro, tempZona, new Date()) : null;
  const valido = modo === 'coords' ? giro.trim() !== '' && lat !== '' && lon !== '' : giro.trim() !== '' && direccion.trim() !== '';

  return (
    <div className="flex h-full flex-col">
      <Topbar titulo="Reporte de ubicación" subtitulo="Informe de decisión · 13 secciones + veredicto explícito + plan de contacto (14)" />
      <div className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-4xl space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Nuevo análisis</CardTitle>
              <CardDescription>
                Giro + ubicación. Si usas dirección, se geocodifica primero (<code>POST /territories/geocode</code>).
                El análisis usa DENUE y Censo vigentes.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Field label="Giro / actividad" htmlFor="giro" required>
                <Input id="giro" placeholder="Ej. Cafetería" value={giro} onChange={(e) => setGiro(e.target.value)} />
              </Field>
              <div className="flex gap-2">
                <Button variant={modo === 'coords' ? 'default' : 'outline'} size="sm" onClick={() => setModo('coords')}>Lat / Lon</Button>
                <Button variant={modo === 'direccion' ? 'default' : 'outline'} size="sm" onClick={() => setModo('direccion')}>Dirección</Button>
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
                <Field label="Dirección" htmlFor="dir" required>
                  <Input id="dir" placeholder="Roma Norte, Cuauhtémoc, CDMX" value={direccion} onChange={(e) => setDireccion(e.target.value)} />
                </Field>
              )}
              <Button onClick={generar} disabled={cargando || !valido}>
                {(cargando || geocodificando) && <Spinner size={16} />}
                {geocodificando ? 'Geocodificando…' : 'Generar reporte'}
              </Button>
            </CardContent>
          </Card>

          {error && <Alert variant="destructive"><AlertTitle>No se pudo generar el reporte</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>}

          {!reporte && !cargando && !error && (
            <Empty title="Sin reporte" description="Completa el formulario y genera el análisis para ver aquí las 13 secciones, el veredicto y el plan de contacto sugerido (14)." icon="📄" />
          )}

          {reporte && payload && (
            <div className="space-y-6">
              <Card style={{ borderLeft: `6px solid ${verdictColor(decision)}` }}>
                <CardHeader>
                  <div className="flex items-center justify-between gap-2">
                    <CardTitle>Veredicto</CardTitle>
                    <Button variant="ghost" size="sm" onClick={() => setCrudo((c) => !c)}>
                      {crudo ? 'Ver formateado' : 'Ver JSON crudo'}
                    </Button>
                  </div>
                  {payload.cabecera && (
                    <CardDescription>
                      {payload.cabecera.giro ?? giro} · {payload.cabecera.ubicacion ?? ''}
                      {geoNota && ` · geocodificado: ${geoNota}`}
                    </CardDescription>
                  )}
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex flex-wrap items-center gap-3">
                    <span className="inline-block h-6 w-6 rounded-full" style={{ backgroundColor: verdictColor(decision) }} aria-hidden />
                    <span className="text-2xl font-bold">{decision}</span>
                    {ver?.confianza && <Badge variant="outline">Confianza: {ver.confianza}</Badge>}
                  </div>
                  {ver?.factores && ver.factores.length > 0 && (
                    <div>
                      <p className="mb-1 text-sm font-semibold">Factores:</p>
                      <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
                        {ver.factores.map((f, i) => <li key={i}>{f}</li>)}
                      </ul>
                    </div>
                  )}
                  {ver?.riesgos && ver.riesgos.length > 0 && (
                    <Alert variant="warning"><AlertTitle>Riesgos</AlertTitle><AlertDescription><ul className="list-disc pl-5">{ver.riesgos.map((r, i) => <li key={i}>{r}</li>)}</ul></AlertDescription></Alert>
                  )}
                  <p className="text-xs text-muted-foreground">
                    🟢 AVANZAR · 🟡 NEGOCIAR · 🔴 EXPLORAR_OTRA_ZONA — semáforo del veredicto (SRS §6.1)
                  </p>
                </CardContent>
              </Card>

              {crudo ? (
                <CodeBlock language="json" code={JSON.stringify(reporte, null, 2)} />
              ) : (
                <Card>
                  <CardHeader><CardTitle>Secciones del informe</CardTitle></CardHeader>
                  <CardContent>
                    <Accordion type="multiple" className="w-full">
                      <Sec n={1} titulo="Perfil del cliente">
                        <p className="whitespace-pre-line text-sm leading-relaxed">{payload.perfil_cliente?.editorial ?? 'Sin contenido.'}</p>
                      </Sec>
                      <Sec n={2} titulo="Clientes y resultado de la zona">
                        {payload.clientes_zona?.nota && (
                          <Alert variant="info" className="mb-3"><AlertDescription>{payload.clientes_zona.nota}</AlertDescription></Alert>
                        )}
                        <dl className="grid gap-2 text-sm sm:grid-cols-2">
                          <Dato k="Población total" v={fmt(payload.clientes_zona?.poblacion_total)} />
                          <Dato k="Población objetivo" v={fmt(payload.clientes_zona?.poblacion_objetivo)} />
                        </dl>
                        <RenderContenido contenido={payload.clientes_zona?.segmentos} />
                      </Sec>
                      <Sec n={3} titulo="Hogares y familias">
                        <RenderContenido contenido={payload.hogares_familias} />
                      </Sec>
                      <Sec n={4} titulo="Atractores de tráfico">
                        {payload.atractores_trafico?.nota && (
                          <Alert variant="info" className="mb-3"><AlertDescription>{payload.atractores_trafico.nota}</AlertDescription></Alert>
                        )}
                        <RenderContenido contenido={payload.atractores_trafico?.items} />
                      </Sec>
                      <Sec n={5} titulo="Competencia en la zona">
                        {payload.competencia?.por_anillo && payload.competencia.por_anillo.length > 0 ? (
                          <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                              <thead><tr className="border-b text-left text-xs uppercase tracking-wider text-muted-foreground">
                                <th className="py-2 pr-4">Radio</th><th className="py-2 pr-4">Competidores</th><th className="py-2 pr-4">ISM <EstimadoBadge /></th><th className="py-2">Banda</th>
                              </tr></thead>
                              <tbody>
                                {payload.competencia.por_anillo.map((a, i) => (
                                  <tr key={i} className="border-b last:border-0">
                                    <td className="py-2 pr-4 font-mono">{a.radio_m ?? '—'} m</td>
                                    <td className="py-2 pr-4 font-mono">{a.conteo ?? '—'}</td>
                                    <td className="py-2 pr-4 font-mono">{a.ism !== undefined ? a.ism.toFixed(2) : '—'}</td>
                                    <td className="py-2">{a.ism_banda ?? '—'}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        ) : <p className="text-sm text-muted-foreground">Sin datos por anillo.</p>}
                        <RenderContenido contenido={payload.competencia?.lista} />
                      </Sec>
                      <Sec n={6} titulo="Mapas">
                        <p className="mb-2 text-sm text-muted-foreground">Capas descritas por el informe:</p>
                        <ul className="list-disc space-y-1 pl-5 text-sm">
                          {(payload.mapas?.capas ?? []).map((c, i) => <li key={i} className="font-mono text-xs">{c}</li>)}
                        </ul>
                        {payload.mapas?.centro && (
                          <p className="mt-2 font-mono text-xs text-muted-foreground">
                            Centro: {payload.mapas.centro.lat}, {payload.mapas.centro.lon}
                          </p>
                        )}
                      </Sec>
                      <Sec n={7} titulo="Entorno comercial">
                        {payload.entorno_comercial?.total_negocios !== undefined && (
                          <p className="mb-2 text-sm">Negocios totales: <strong className="font-mono">{payload.entorno_comercial.total_negocios}</strong></p>
                        )}
                        <RenderContenido contenido={payload.entorno_comercial?.categorias} />
                      </Sec>
                      <Sec n={8} titulo="Población y viviendas">
                        {payload.poblacion_viviendas?.advertencia && (
                          <Alert variant="warning" className="mb-3"><AlertDescription>{payload.poblacion_viviendas.advertencia}</AlertDescription></Alert>
                        )}
                        <RenderContenido contenido={payload.poblacion_viviendas?.detalle ?? payload.poblacion_viviendas?.viviendas} />
                      </Sec>
                      <Sec n={9} titulo="Movimiento y acceso" extra={<EstimadoBadge />}>
                        {payload.movimiento_acceso?.nse_etiqueta && (
                          <p className="mb-2 text-sm">NSE: <strong>{payload.movimiento_acceso.nse_etiqueta}</strong></p>
                        )}
                        {payload.movimiento_acceso?.nse_nota && (
                          <Alert variant="info" className="mb-3"><AlertDescription>{payload.movimiento_acceso.nse_nota}</AlertDescription></Alert>
                        )}
                        <RenderContenido contenido={payload.movimiento_acceso?.vialidades} />
                        <RenderContenido contenido={payload.movimiento_acceso?.movilidad} />
                      </Sec>
                      <Sec n={10} titulo="Área de alcance por tiempo">
                        {payload.area_alcance_tiempo?.como_usarla && (
                          <p className="mb-2 text-sm text-muted-foreground">{payload.area_alcance_tiempo.como_usarla}</p>
                        )}
                        <RenderContenido contenido={payload.area_alcance_tiempo?.isocronas} />
                      </Sec>
                      <Sec n={11} titulo="Modelos" extra={<EstimadoBadge />}>
                        <div className="space-y-4 text-sm">
                          <div>
                            <p className="mb-1 font-semibold">ISM <span className="font-mono text-xs text-muted-foreground">{payload.modelos?.ism?.formula}</span></p>
                            <RenderContenido contenido={payload.modelos?.ism?.por_anillo} />
                          </div>
                          <div>
                            <p className="mb-1 font-semibold">Huff <span className="font-mono text-xs text-muted-foreground">{payload.modelos?.huff?.formula}</span></p>
                            <p className="text-muted-foreground">Cuota del punto: <strong className="font-mono">{payload.modelos?.huff?.cuota_punto !== undefined ? (payload.modelos.huff.cuota_punto * 100).toFixed(1) + ' %' : '—'}</strong></p>
                          </div>
                          <div>
                            <p className="mb-1 font-semibold">TAM <span className="font-mono text-xs text-muted-foreground">{payload.modelos?.tam?.formula}</span></p>
                            {payload.modelos?.tam?.advertencia && (
                              <Alert variant="warning" className="mb-2"><AlertDescription>{payload.modelos.tam.advertencia}</AlertDescription></Alert>
                            )}
                            <p className="text-muted-foreground">
                              TAM anual: <strong className="font-mono">{mxn(payload.modelos?.tam?.tam_mxn_anual)}</strong>
                              {payload.modelos?.tam?.rango_mxn && payload.modelos.tam.rango_mxn.length === 2 &&
                                ` (rango ${mxn(payload.modelos.tam.rango_mxn[0])} – ${mxn(payload.modelos.tam.rango_mxn[1])})`}
                            </p>
                            {payload.modelos?.tam?.supuestos && payload.modelos.tam.supuestos.length > 0 && (
                              <ul className="mt-1 list-disc pl-5 text-xs text-muted-foreground">
                                {payload.modelos.tam.supuestos.map((s, i) => <li key={i} className="font-mono">{s}</li>)}
                              </ul>
                            )}
                          </div>
                        </div>
                      </Sec>
                      <Sec n={12} titulo="Fuentes y datos">
                        <dl className="grid gap-2 text-sm sm:grid-cols-2">
                          <Dato k="Fecha de cálculo" v={payload.fuentes_datos?.fecha_calculo} />
                          <Dato k="Versión de modelos" v={payload.fuentes_datos?.model_version} />
                        </dl>
                        <RenderContenido contenido={payload.fuentes_datos?.ediciones} />
                      </Sec>
                      <Sec n={13} titulo="Metodología y advertencias">
                        {payload.metodologia_advertencias?.nota_general && (
                          <Alert variant="info" className="mb-3"><AlertDescription>{payload.metodologia_advertencias.nota_general}</AlertDescription></Alert>
                        )}
                        <RenderContenido contenido={payload.metodologia_advertencias?.estimado_vs_observado} />
                      </Sec>
                      {/* Sección 14 · Módulo Radar: plan de contacto sugerido */}
                      {plan && (
                        <AccordionItem value="s14">
                          <AccordionTrigger>
                            <span><span className="mr-2 font-mono text-muted-foreground">14.</span>Plan de contacto sugerido <Badge variant="accent" className="ml-2">Radar</Badge></span>
                          </AccordionTrigger>
                          <AccordionContent>
                            <div className="space-y-4 text-sm">
                              <div className="flex items-center gap-3">
                                <span className="text-muted-foreground">Línea recomendada:</span>
                                <span className="inline-block h-3 w-3 rounded-full" style={{ backgroundColor: plan.color }} aria-hidden />
                                <strong>{plan.lineaNombre}</strong>
                              </div>
                              <p className="text-xs text-muted-foreground">Por qué: {plan.motivoLinea}</p>
                              <div>
                                <p className="mb-1 font-semibold">Argumentos para el giro «{giro}»</p>
                                <ul className="list-disc space-y-1 pl-5 text-muted-foreground">
                                  {plan.argumentos.map((a, i) => <li key={i}>{a}</li>)}
                                </ul>
                              </div>
                              <div>
                                <p className="mb-1 font-semibold">Mejor momento para contactar</p>
                                <p className="text-muted-foreground">
                                  {plan.tempC !== null ? `🌡️ ${plan.tempC.toFixed(1)} °C ahora en la zona (Open-Meteo). ` : 'Sin dato de temperatura en vivo. '}
                                  {plan.momento}
                                </p>
                              </div>
                              <p className="text-[11px] text-muted-foreground">
                                Regla de línea por mes (biokool): feb–jun → Koolkat (temporada de calor); oct–feb + giro gasolinera/estacionamiento/comercial → Solar; resto → Evaporativa.
                              </p>
                            </div>
                          </AccordionContent>
                        </AccordionItem>
                      )}
                    </Accordion>
                  </CardContent>
                </Card>
              )}

              {reporte.lineage && (
                <Card>
                  <CardHeader><CardTitle>Linaje de datos</CardTitle></CardHeader>
                  <CardContent>
                    <dl className="grid gap-2 text-sm sm:grid-cols-2">
                      {Object.entries(reporte.lineage).map(([k, v]) => (
                        <div key={k} className="flex justify-between gap-4 border-b py-1">
                          <dt className="text-muted-foreground">{k}</dt>
                          <dd className="font-mono text-xs">{typeof v === 'object' ? JSON.stringify(v) : String(v)}</dd>
                        </div>
                      ))}
                    </dl>
                    {reporte.report_id && (
                      <p className="mt-3 font-mono text-xs text-muted-foreground">ID del reporte: {reporte.report_id}</p>
                    )}
                  </CardContent>
                </Card>
              )}
              <Separator />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Sec({ n, titulo, extra, children }: { n: number; titulo: string; extra?: React.ReactNode; children: React.ReactNode }) {
  return (
    <AccordionItem value={`s${n}`}>
      <AccordionTrigger>
        <span>
          <span className="mr-2 font-mono text-muted-foreground">{n}.</span>{titulo}
          {extra && <span className="ml-2">{extra}</span>}
        </span>
      </AccordionTrigger>
      <AccordionContent>{children}</AccordionContent>
    </AccordionItem>
  );
}

function Dato({ k, v }: { k: string; v?: string | number | null }) {
  return (
    <div className="flex justify-between gap-4 border-b py-1">
      <dt className="text-muted-foreground">{k}</dt>
      <dd className="font-mono text-xs">{v ?? '—'}</dd>
    </div>
  );
}

function fmt(v: unknown): string {
  if (typeof v === 'number') return v.toLocaleString('es-MX');
  return '—';
}

function RenderContenido({ contenido }: { contenido: unknown }) {
  if (contenido === null || contenido === undefined) return null;
  if (typeof contenido === 'string') return <p className="whitespace-pre-line text-sm leading-relaxed">{contenido}</p>;
  if (Array.isArray(contenido)) {
    if (contenido.length === 0) return <p className="text-sm text-muted-foreground">Sin datos.</p>;
    return (
      <ul className="list-disc space-y-1 pl-5 text-sm">
        {contenido.map((it, i) => (
          <li key={i}>{typeof it === 'string' ? it : JSON.stringify(it)}</li>
        ))}
      </ul>
    );
  }
  if (typeof contenido === 'object') {
    const entries = Object.entries(contenido as Record<string, unknown>).filter(([, v]) => v !== null && v !== undefined);
    if (entries.length === 0) return <p className="text-sm text-muted-foreground">Sin datos.</p>;
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

/** snake_case → etiqueta legible. */
function etiqueta(k: string): string {
  return k.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase());
}

/* ---------- Sección 14 · Módulo Radar: plan de contacto sugerido ---------- */

interface PlanContacto {
  linea: 'koolkat' | 'solar' | 'evaporativa';
  lineaNombre: string;
  color: string;
  motivoLinea: string;
  argumentos: string[];
  momento: string;
  tempC: number | null;
}

const LINEA_META: Record<PlanContacto['linea'], { nombre: string; color: string }> = {
  koolkat: { nombre: 'Koolkat · control térmico', color: '#E8590C' },
  solar: { nombre: 'Solar · paneles fotovoltaicos', color: '#E8A13D' },
  evaporativa: { nombre: 'Evaporativa · bioclimatización', color: '#0E5FD8' },
};

function planContacto(giro: string, tempC: number | null, fecha: Date): PlanContacto {
  const mes = fecha.getMonth(); // 0=ene … 11=dic
  const g = giro.toLowerCase();
  const esCalor = mes >= 1 && mes <= 5;                       // feb–jun
  const esInvierno = mes >= 9 || mes <= 1;                     // oct–feb
  // Pistas de giro solar: idénticas al backend (GIROS_SOLAR en scoring_unificado.py).
  // "plaza comercial" está subsumida por "comercial"; no agregar "plaza" ni
  // "retail" sueltos o la línea diverge del servidor.
  const giroSolar = /gasolin|estacionamiento|comercial/.test(g);

  let linea: PlanContacto['linea'];
  let motivoLinea: string;
  if (esCalor) {
    linea = 'koolkat';
    motivoLinea = 'Estamos en temporada de calor (feb–jun): el control térmico de naves y locales es la necesidad dominante.';
  } else if (esInvierno && giroSolar) {
    linea = 'solar';
    motivoLinea = 'Temporada de invierno + giro al aire libre: los paneles solares recortan el recibo de luz justo cuando el consumo de climatización cambia.';
  } else {
    linea = 'evaporativa';
    motivoLinea = 'Fuera de la temporada pico de calor: la bioclimatización evaporativa vende confort con bajo consumo energético todo el año.';
  }

  const esIndustrial = /industr|nave|log[ií]st|manufact|f[aá]brica|taller|almac/.test(g);
  const esHospitalidad = /hotel|restaur|oficina|escuela|cl[ií]nica|hospital/.test(g);

  const argumentos: string[] = [];
  if (linea === 'koolkat') {
    argumentos.push('El calor baja la productividad del personal y pone en riesgo mercancía sensible a temperatura.');
    argumentos.push('Koolkat climatiza grandes volúmenes con una fracción del costo del aire acondicionado tradicional.');
    if (esIndustrial) argumentos.push(`En un giro como «${giro}», el control térmico de la nave protege tanto a la plantilla como al inventario.`);
  } else if (linea === 'solar') {
    argumentos.push('Los espacios al aire libre consumen mucha energía en iluminación y bombeo: el sol que los calienta puede pagar su recibo.');
    argumentos.push('Paneles solares = gasto operativo predecible por 25 años y deducción fiscal del activo.');
    if (giroSolar) argumentos.push(`Para «${giro}», la marquesina solar además da sombra a clientes y vehículos: doble beneficio visible.`);
  } else {
    argumentos.push('La bioclimatización evaporativa renueva el aire (salud) en vez de recircularlo, con consumos muy inferiores al minisplit.');
    argumentos.push('Ideal para espacios semi-abiertos donde el aire acondicionado no funciona.');
    if (esHospitalidad) argumentos.push(`En «${giro}», el confort térmico de clientes se nota en reseñas y permanencia.`);
    if (esIndustrial) argumentos.push(`En «${giro}», baja la sensación térmica de la nave sin cerrar puertas ni detener la operación.`);
  }
  argumentos.push('Oferta de arranque: diagnóstico térmico gratuito de la zona con el mapa de temperatura del módulo Radar.');

  let momento: string;
  if (tempC === null) {
    momento = 'Consulta el pronóstico y agenda la visita en el día más caluroso de la semana: el calor hace la mitad del pitch.';
  } else if (tempC >= 32) {
    momento = 'Contacto inmediato: hay ola de calor en la zona. Llama hoy y visita entre 12:00 y 16:00 para que sientan el problema.';
  } else if (tempC >= 30) {
    momento = 'Ventana caliente: agenda la visita en el pico de calor del día (12:00–16:00); el contraste térmico vende solo.';
  } else if (tempC >= 25) {
    momento = 'Calor moderado: visita a mediodía y enfoca el argumento en productividad del personal, no solo en confort.';
  } else {
    momento = 'El calor no aprieta hoy: el pitch debe ir por ahorro de energía y ROI, no por urgencia térmica. Agenda seguimiento en temporada de calor.';
  }

  return {
    linea,
    lineaNombre: LINEA_META[linea].nombre,
    color: LINEA_META[linea].color,
    motivoLinea,
    argumentos,
    momento,
    tempC,
  };
}

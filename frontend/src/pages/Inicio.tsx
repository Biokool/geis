import * as React from 'react';
import { useNavigate } from 'react-router-dom';
import { Topbar } from '@/components/layout/Topbar';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/Alert';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Skeleton } from '@/components/ui/Skeleton';
import { Empty } from '@/components/ui/Empty';
import { Progress } from '@/components/ui/Progress';
import { Chart } from '@/components/ui/Chart';
import {
  get, errorMessage, getCompanyProfile, getLeadsCount, ApiError,
  type SystemHealth, type CompanyProfile, type Lead, type LeadCurado, type PipelineRun, type Investigation,
  ETAPAS_RADAR, lineaColor,
} from '@/lib/api';
import { useGeisStore } from '@/store';

const FLUJOS = [
  {
    icono: '🗺️',
    titulo: 'Analizar territorio',
    descripcion: 'Dibuja un polígono, mide demanda y competencia, y genera el informe de decisión con veredicto.',
    pasos: [
      { to: '/mapa', label: 'Mapa', detalle: 'geofencing + capas DENUE/IDT' },
      { to: '/kpis', label: 'KPIs', detalle: 'métricas del territorio activo' },
      { to: '/reporte', label: 'Reporte', detalle: '13 secciones + plan de contacto' },
    ],
  },
  {
    icono: '🎯',
    titulo: 'Captar y contactar',
    descripcion: 'Lanza el scrapeo y el scoring, mueve los leads por el pipeline y expórtalos a tu CRM.',
    pasos: [
      { to: '/operacion', label: 'Operación', detalle: 'pipelines 01→05 + ETL' },
      { to: '/leads', label: 'Leads', detalle: 'matriz DENUE + curados Radar' },
      { to: '/exportacion', label: 'Exportación', detalle: 'territorio, leads y CRM' },
    ],
  },
  {
    icono: '🖥️',
    titulo: 'Gobernar el sistema',
    descripcion: 'Diagnostica servicios, conmuta providers anti-cautiverio y guarda territorios reutilizables.',
    pasos: [
      { to: '/sistema', label: 'Sistema', detalle: 'semáforo + providers + LinkedIn' },
      { to: '/historial', label: 'Historial', detalle: 'investigaciones y linaje' },
      { to: '/geofencing', label: 'Geofencing', detalle: 'constructor de polígonos' },
    ],
  },
];

function punto(estado?: string): string {
  const e = String(estado ?? '').toLowerCase();
  if (['ok', 'up', 'healthy', 'true'].includes(e)) return '#2F9E44';
  if (['degraded', 'warn', 'warning'].includes(e)) return '#E8A13D';
  return '#8a93a6';
}

function KpiStat({ titulo, valor, nota }: { titulo: string; valor: string; nota?: string }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardDescription className="text-xs font-semibold uppercase tracking-wider">{titulo}</CardDescription>
        <p className="font-mono text-3xl font-bold">{valor}</p>
      </CardHeader>
      {nota && <CardContent><p className="text-[11px] text-muted-foreground">{nota}</p></CardContent>}
    </Card>
  );
}

export default function Inicio() {
  const navigate = useNavigate();
  const territorio = useGeisStore((s) => s.territorio);
  const [health, setHealth] = React.useState<SystemHealth | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [perfil, setPerfil] = React.useState<CompanyProfile | null>(null);
  const [sinPerfil, setSinPerfil] = React.useState(false);
  const [cargandoPerfil, setCargandoPerfil] = React.useState(true);

  const [leadsTotalReal, setLeadsTotalReal] = React.useState<number | null>(null);
  const [invCount, setInvCount] = React.useState(0);
  const [hasEstablecimientos, setHasEstablecimientos] = React.useState(false);
  const [curados, setCurados] = React.useState<LeadCurado[]>([]);
  const [denue, setDenue] = React.useState<Lead[]>([]);
  const [runs, setRuns] = React.useState<PipelineRun[]>([]);
  const [dashLoading, setDashLoading] = React.useState(true);
  const [dashError, setDashError] = React.useState<string | null>(null);

  const cargar = React.useCallback(() => {
    setLoading(true);
    setError(null);
    get<SystemHealth>('/system/health')
      .then(setHealth)
      .catch((e) => setError(errorMessage(e)))
      .finally(() => setLoading(false));
  }, []);

  const cargarDashboard = React.useCallback(() => {
    setDashLoading(true);
    setDashError(null);
    (async () => {
      // Total real desde /leads/count (ya no se pagina para contar)
      try {
        const c = await getLeadsCount();
        setLeadsTotalReal(c.total);
      } catch { setLeadsTotalReal(null); }
      // Una sola página para los charts
      const r = await get<{ items?: LeadCurado[]; next_cursor?: string | null } | LeadCurado[]>('/leads/curados', { limit: 100 });
      const items = Array.isArray(r) ? r : (r.items ?? []);
      setCurados(items);
      const dl = await get<{ items?: Lead[]; data?: Lead[] } | Lead[]>('/leads', { limit: 100 });
      const denueArr = Array.isArray(dl) ? dl : (dl.items ?? dl.data ?? []);
      setDenue(denueArr);
      setHasEstablecimientos(denueArr.length > 0);
      // Investigaciones (para checklist)
      try {
        const inv = await get<{ items?: Investigation[]; data?: Investigation[] } | Investigation[]>('/investigations', { limit: 1 });
        const arrInv = Array.isArray(inv) ? inv : (inv.items ?? inv.data ?? []);
        // limit 1 solo dice si hay al menos 1; para conteo breve pedimos sin limit si vino 1
        setInvCount(arrInv.length);
      } catch { setInvCount(0); }
      const rs = await get<{ items?: PipelineRun[] } | PipelineRun[]>('/pipelines/runs', { limit: 200 });
      setRuns(Array.isArray(rs) ? rs : (rs.items ?? []));
    })()
      .catch((e) => setDashError(errorMessage(e)))
      .finally(() => setDashLoading(false));
  }, []);

  React.useEffect(() => { cargar(); cargarDashboard(); }, [cargar, cargarDashboard]);

  React.useEffect(() => {
    getCompanyProfile()
      .then((p) => { setPerfil(p); setSinPerfil(false); })
      .catch((e) => {
        // 404 = aún no hay perfil: se muestra el banner de configuración.
        // Otro error (módulo aún no desplegado): no se bloquea el Inicio.
        if (e instanceof ApiError && e.status === 404) setSinPerfil(true);
      })
      .finally(() => setCargandoPerfil(false));
  }, []);

  const dash = React.useMemo(() => {
    const porEtapa = (e: string) => curados.filter((l) => (l.etapa ?? 'nuevo') === e).length;
    const scores = curados.map((l) => l.score ?? 0).filter((v) => v > 0);
    const scoreProm = scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : 0;
    return {
      total: leadsTotalReal ?? curados.length,
      totalCargados: curados.length,
      nuevos: porEtapa('nuevo'),
      enPipeline: porEtapa('contactado') + porEtapa('reunion') + porEtapa('propuesta'),
      ganados: porEtapa('ganado'),
      perdidos: porEtapa('perdido'),
      scoreProm,
      enriquecidos: curados.filter((l) => l.enriquecido_apollo === true).length,
      enCrm: curados.filter((l) => l.crm_synced_at != null).length,
      denue: denue.length,
      funnel: ETAPAS_RADAR.filter((e) => e.id !== 'perdido').map((e) => ({ name: e.label, value: porEtapa(e.id) })),
      dona: ['koolkat', 'solar', 'evaporativa'].map((linea) => ({
        name: { koolkat: 'Koolkat', solar: 'Solar', evaporativa: 'Evaporativa' }[linea],
        value: curados.filter((l) => (l.linea_recomendada ?? '').toLowerCase() === linea).length,
        itemStyle: { color: lineaColor(linea) },
      })),
      runsOk: runs.filter((r) => r.estado === 'ok').length,
      runsError: runs.filter((r) => r.estado === 'error').length,
      ultima: runs[0],
    };
  }, [curados, denue, runs, leadsTotalReal]);

  const pasos = [
    {
      id: 'perfil',
      titulo: 'Perfil de empresa activo',
      completo: !!perfil,
      detalle: perfil ? perfil.nombre : sinPerfil ? 'Sin perfil configurado' : 'Cargando…',
      cta: 'Configurar',
      to: '/configuracion',
    },
    {
      id: 'datos',
      titulo: 'Datos cargados',
      completo: (leadsTotalReal ?? 0) > 0 || hasEstablecimientos,
      detalle: (leadsTotalReal ?? 0) > 0 ? `${leadsTotalReal} leads Radar` : hasEstablecimientos ? `${denue.length} establecimientos` : 'Sin datos todavía',
      cta: 'Ir al mapa',
      to: '/mapa',
    },
    {
      id: 'investigacion',
      titulo: 'Primera investigación',
      completo: invCount > 0,
      detalle: invCount > 0 ? 'Al menos 1 investigación creada' : 'Aún no hay investigaciones',
      cta: 'Crear en el mapa',
      to: '/mapa',
    },
    {
      id: 'leads',
      titulo: 'Leads en lista',
      completo: (leadsTotalReal ?? 0) > 0,
      detalle: (leadsTotalReal ?? 0) > 0 ? `${leadsTotalReal} leads` : 'Sin leads curados',
      cta: 'Ver leads',
      to: '/leads',
    },
    {
      id: 'pipeline',
      titulo: 'Primera corrida del pipeline',
      completo: runs.length > 0,
      detalle: runs.length > 0 ? `${runs.length} corridas registradas` : 'Sin corridas',
      cta: 'Ir a Operación',
      to: '/operacion',
    },
  ];
  const completos = pasos.filter((s) => s.completo).length;
  const siguientePaso = pasos.find((s) => !s.completo);

  return (
    <div className="flex h-full flex-col">
      <Topbar titulo="Inicio" subtitulo="Dashboard general · GEIS × Radar · inteligencia geomarketing + ejecución comercial" />
      <div className="flex-1 space-y-6 overflow-y-auto p-6">
        <div className="mx-auto max-w-5xl space-y-6">
          {/* Primeros pasos — checklist de estado real */}
          <Card>
            <CardHeader>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <CardTitle>Primeros pasos</CardTitle>
                  <CardDescription>Estado real del sistema · {completos} de 5 pasos completos</CardDescription>
                </div>
                {siguientePaso ? (
                  <Button onClick={() => navigate(siguientePaso.to)}>Siguiente paso: {siguientePaso.titulo} →</Button>
                ) : (
                  <Badge variant="success">Sistema operando</Badge>
                )}
              </div>
              <Progress value={(completos / 5) * 100} className="mt-3" />
              <p className="text-xs text-muted-foreground">{completos} de 5</p>
            </CardHeader>
            <CardContent className="space-y-3">
              {cargandoPerfil && <Skeleton className="h-10" />}
              {pasos.map((paso, i) => (
                <div key={paso.id} className="flex flex-wrap items-center gap-3 border-b py-2 last:border-0">
                  <span aria-hidden className="text-lg">{paso.completo ? '✓' : '○'}</span>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium">{i + 1}. {paso.titulo}</p>
                    <p className="text-xs text-muted-foreground">{paso.detalle}</p>
                  </div>
                  {paso.completo ? (
                    <Badge variant="secondary">Completo</Badge>
                  ) : (
                    <Button size="sm" variant="outline" onClick={() => navigate(paso.to)}>{paso.cta}</Button>
                  )}
                </div>
              ))}
              {completos === 5 && (
                <div className="flex flex-wrap items-center gap-2 pt-2">
                  <span className="text-sm font-medium">Sistema operando — accesos rápidos:</span>
                  <Button size="sm" onClick={() => navigate('/mapa')}>Mapa</Button>
                  <Button size="sm" variant="outline" onClick={() => navigate('/leads')}>Leads</Button>
                  <Button size="sm" variant="outline" onClick={() => navigate('/operacion')}>Operación</Button>
                </div>
              )}
              {perfil && (
                <p className="pt-1 text-xs text-muted-foreground">
                  Empresa activa: <strong>{perfil.nombre}</strong>
                  {perfil.vertical_id ? ` · vertical: ${perfil.vertical_id}` : ''} · v{perfil.version}{' '}
                  <button type="button" className="text-primary hover:underline" onClick={() => navigate('/configuracion')}>Editar configuración →</button>
                </p>
              )}
            </CardContent>
          </Card>

          {/* Acceso destacado · Sección 1: puerta única de análisis (2 campos + 1 clic) */}
          <Card className="border-2 border-primary/50 bg-primary/5">
            <CardContent className="flex flex-wrap items-center gap-4 py-5">
              <span aria-hidden className="text-3xl">📍</span>
              <div className="min-w-0 flex-1">
                <p className="text-lg font-semibold">Analizar una ubicación</p>
                <p className="text-sm text-muted-foreground">
                  Giro + dirección o link de Google Maps → reporte completo en una pantalla: competencia, entorno, alcance, calculadoras y veredicto. Sin pasar por el mapa.
                </p>
              </div>
              <Button size="lg" onClick={() => navigate('/analizar')}>Analizar una ubicación →</Button>
            </CardContent>
          </Card>

          {/* Cómo funciona */}
          <section>
            <h2 className="mb-3 text-lg font-semibold tracking-tight">Cómo funciona</h2>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {[
                { n: 1, titulo: 'Configura', desc: 'Define tu empresa, giro y líneas para que el scoring use tus criterios.', to: '/configuracion' },
                { n: 2, titulo: 'Investiga', desc: 'Dibuja un territorio en el mapa y mide demanda, competencia y potencial.', to: '/mapa' },
                { n: 3, titulo: 'Actúa', desc: 'Trabaja la lista de leads: etapa, notas, señales y contacto directo.', to: '/leads' },
                { n: 4, titulo: 'Opera', desc: 'Lanza pipelines, revisa corridas y exporta resultados a tu CRM.', to: '/operacion' },
              ].map((s) => (
                <button key={s.n} type="button" onClick={() => navigate(s.to)} className="rounded-xl border bg-card p-4 text-left shadow transition-colors hover:bg-muted/50">
                  <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Paso {s.n}</p>
                  <p className="mt-1 font-semibold">{s.titulo} →</p>
                  <p className="mt-1 text-sm text-muted-foreground">{s.desc}</p>
                </button>
              ))}
            </div>
          </section>

          {/* KPIs generales */}
          <section>
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-lg font-semibold tracking-tight">KPIs generales</h2>
              <Button variant="ghost" size="sm" onClick={() => { cargar(); cargarDashboard(); }}>Actualizar</Button>
            </div>
            {dashError ? (
              <Alert variant="destructive">
                <AlertTitle>No se pudieron cargar los KPIs</AlertTitle>
                <AlertDescription>
                  <p className="mb-2">{dashError}</p>
                  <Button variant="outline" size="sm" onClick={cargarDashboard}>Reintentar</Button>
                </AlertDescription>
              </Alert>
            ) : dashLoading ? (
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                {[0, 1, 2, 3, 4, 5, 6, 7].map((i) => <Skeleton key={i} className="h-32" />)}
              </div>
            ) : (
              <>
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                  <KpiStat titulo="Leads Radar" valor={String(dash.total)} nota="Total real · prod.leads (GET /leads/count)" />
                  <KpiStat titulo="Nuevos" valor={String(dash.nuevos)} nota="etapa «nuevo» · sin primer contacto" />
                  <KpiStat titulo="En pipeline" valor={String(dash.enPipeline)} nota="contactado + reunión + propuesta" />
                  <KpiStat titulo="Ganados" valor={String(dash.ganados)} nota={`perdidos: ${dash.perdidos}`} />
                  <KpiStat titulo="Score promedio" valor={`${dash.scoreProm.toFixed(0)}/100`} nota="scoring conductual Radar" />
                  <KpiStat titulo="Enriquecidos" valor={String(dash.enriquecidos)} nota="Apollo · enriquecimiento de cuentas" />
                  <KpiStat titulo="En CRM" valor={String(dash.enCrm)} nota="sincronizados con HubSpot" />
                  <KpiStat titulo="Plantas DENUE" valor={String(dash.denue)} nota="matriz de territorio (mapa)" />
                </div>
                <div className="mt-4 grid gap-4 lg:grid-cols-2">
                  <Card>
                    <CardHeader>
                      <CardTitle>Funnel comercial</CardTitle>
                      <CardDescription>Leads Radar por etapa{(leadsTotalReal ?? 0) > curados.length ? " · sobre los primeros 100 leads" : ""}</CardDescription>
                    </CardHeader>
                    <CardContent>
                      {dash.totalCargados > 0 ? (
                        <Chart
                          height={280}
                          option={{
                            tooltip: { trigger: 'item', formatter: '{b}: {c}' },
                            series: [{
                              type: 'funnel',
                              left: '10%', width: '80%',
                              label: { formatter: '{b}: {c}' },
                              data: dash.funnel,
                            }],
                          }}
                        />
                      ) : (
                        <Empty
                          title="Sin leads Radar"
                          description="Ejecuta el pipeline 01 (scraper) desde Operación para poblar el funnel."
                          icon="🎯"
                          action={{ label: 'Ir a Operación', onClick: () => navigate('/operacion') }}
                        />
                      )}
                    </CardContent>
                  </Card>
                  <Card>
                    <CardHeader>
                      <CardTitle>Línea recomendada</CardTitle>
                      <CardDescription>Distribución de los leads Radar{(leadsTotalReal ?? 0) > curados.length ? " · sobre los primeros 100 leads" : ""}</CardDescription>
                    </CardHeader>
                    <CardContent>
                      {dash.totalCargados > 0 ? (
                        <Chart
                          height={280}
                          option={{
                            tooltip: { trigger: 'item' },
                            legend: { bottom: 0 },
                            series: [{ type: 'pie', radius: ['45%', '70%'], data: dash.dona, label: { formatter: '{b}: {c}' } }],
                          }}
                        />
                      ) : (
                        <Empty
                          title="Sin datos"
                          description="Aún no hay leads con línea recomendada."
                          icon="🧭"
                          action={{ label: 'Ir a Operación', onClick: () => navigate('/operacion') }}
                        />
                      )}
                    </CardContent>
                  </Card>
                </div>
              </>
            )}
          </section>

          {/* Estado, territorio y operación */}
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle>Estado del sistema</CardTitle>
                  <Button variant="ghost" size="sm" onClick={cargar}>Actualizar</Button>
                </div>
              </CardHeader>
              <CardContent>
                {loading ? (
                  <div className="space-y-2"><Skeleton className="h-6" /><Skeleton className="h-6" /><Skeleton className="h-6" /></div>
                ) : error ? (
                  <Alert variant="destructive">
                    <AlertTitle>No se pudo consultar el estado</AlertTitle>
                    <AlertDescription>
                      <p className="mb-2">{error}</p>
                      <Button variant="outline" size="sm" onClick={cargar}>Reintentar</Button>
                    </AlertDescription>
                  </Alert>
                ) : health ? (
                  <ul className="space-y-2">
                    {([
                      ['PostgreSQL + PostGIS', health.postgres],
                      ['n8n (orquestador)', health.n8n],
                      ['Scraper', health.scraper],
                    ] as [string, unknown][]).map(([nombre, estado]) => (
                      <li key={nombre} className="flex items-center gap-3 text-sm">
                        <span className="inline-block h-3 w-3 rounded-full" style={{ backgroundColor: punto(typeof estado === 'string' ? estado : undefined) }} aria-hidden />
                        <span className="flex-1 font-medium">{nombre}</span>
                        <Badge variant="outline">{String(estado ?? '—')}</Badge>
                      </li>
                    ))}
                    <li className="pt-1">
                      <Button variant="link" className="h-auto p-0" onClick={() => navigate('/sistema')}>
                        Ver diagnóstico completo →
                      </Button>
                    </li>
                  </ul>
                ) : null}
              </CardContent>
            </Card>

            <Card>
              <CardHeader><CardTitle>Territorio activo</CardTitle></CardHeader>
              <CardContent>
                {territorio ? (
                  <div className="space-y-2 text-sm">
                    <p className="text-base font-semibold">⬡ {territorio.nombre}</p>
                    <p className="text-muted-foreground">
                      Tipo: {territorio.tipo ?? '—'}
                      {territorio.area_km2 !== undefined && ` · ${territorio.area_km2.toFixed(2)} km²`}
                    </p>
                    <div className="flex gap-2 pt-1">
                      <Button size="sm" onClick={() => navigate('/kpis')}>Ver KPIs</Button>
                      <Button size="sm" variant="outline" onClick={() => navigate('/mapa')}>Ir al mapa</Button>
                    </div>
                  </div>
                ) : (
                  <Empty
                    title="Sin territorio activo"
                    description="Dibuja un polígono en el Mapa o guárdalo en Geofencing para activar los KPIs y el reporte."
                    icon="⬡"
                    action={{ label: 'Ir al mapa', onClick: () => navigate('/mapa') }}
                  />
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Última operación</CardTitle>
                <CardDescription>Corridas de pipelines (n8n)</CardDescription>
              </CardHeader>
              <CardContent>
                {runs.length === 0 ? (
                  <Empty
                    title="Sin corridas"
                    description="Ejecuta un pipeline desde Operación."
                    icon="⚙️"
                    action={{ label: 'Ir a Operación', onClick: () => navigate('/operacion') }}
                  />
                ) : (
                  <div className="space-y-2 text-sm">
                    {dash.ultima && (
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-mono text-xs">{dash.ultima.pipeline}</span>
                        <Badge variant={dash.ultima.estado === 'ok' ? 'success' : dash.ultima.estado === 'error' ? 'destructive' : 'secondary'}>
                          {dash.ultima.estado}
                        </Badge>
                      </div>
                    )}
                    <p className="text-muted-foreground">
                      {dash.ultima?.started_at ? new Date(dash.ultima.started_at).toLocaleString() : '—'}
                    </p>
                    <div className="flex gap-4">
                      <span className="text-muted-foreground">✔ OK: <strong>{dash.runsOk}</strong></span>
                      <span className="text-muted-foreground">✖ Errores: <strong>{dash.runsError}</strong></span>
                    </div>
                    <Button variant="link" className="h-auto p-0" onClick={() => navigate('/operacion')}>
                      Ver todas las corridas →
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          <div>
            <h2 className="mb-3 text-lg font-semibold tracking-tight">Los 3 flujos principales</h2>
            <div className="grid gap-4 md:grid-cols-3">
              {FLUJOS.map((f) => (
                <Card key={f.titulo} className="flex flex-col">
                  <CardHeader>
                    <CardTitle><span aria-hidden className="mr-2">{f.icono}</span>{f.titulo}</CardTitle>
                    <CardDescription>{f.descripcion}</CardDescription>
                  </CardHeader>
                  <CardContent className="flex flex-1 flex-col gap-2">
                    {f.pasos.map((p, i) => (
                      <Button
                        key={p.to}
                        variant={i === 0 ? 'default' : 'outline'}
                        className="justify-between"
                        onClick={() => navigate(p.to)}
                      >
                        <span>{i + 1}. {p.label}</span>
                        <span className="text-xs opacity-70">{p.detalle}</span>
                      </Button>
                    ))}
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Qué es este ecosistema</CardTitle>
              <CardDescription>
                GEIS es la capa de inteligencia (territorio, demanda, competencia, veredictos) y el
                módulo Radar la capa de ejecución (scrapeo de leads, scoring conductual, señales y CRM).
                Todo aterriza en Postgres; la nube es opcional y conmutable por la capa anti-cautiverio.
              </CardDescription>
            </CardHeader>
          </Card>
        </div>
      </div>
    </div>
  );
}

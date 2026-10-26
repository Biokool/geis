import * as React from 'react';
import { useNavigate } from 'react-router-dom';
import { Topbar } from '@/components/layout/Topbar';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/Alert';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Skeleton } from '@/components/ui/Skeleton';
import { Separator } from '@/components/ui/Separator';
import { Empty } from '@/components/ui/Empty';
import { Input } from '@/components/ui/Input';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '@/components/ui/Dialog';
import {
  get, ApiError, errorMessage, getAiStatus,
  type SystemHealth, type Provider, type PipelineRun, type AiStatus,
} from '@/lib/api';
import {
  getRuns, runsComoArray, detalleRunTexto,
  getProviders, providersComoArray, putProvider, getLeadsCountGeo,
  getLinkedInStatus, getLinkedInAuth, postLinkedInDisconnect, linkedinExpirado,
  type LinkedInStatusReal,
} from '@/lib/apiGeo';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

/** Catálogo de providers del dashboard original (server.js PROVIDERS + regla R11). */
const CATALOGO: Record<string, { etiqueta: string; descripcion: string; modos: string[]; backends: string[] }> = {
  scraper: { etiqueta: 'Scraper', descripcion: 'Extracción de Google Maps. Nube: Apify.', modos: ['local', 'cloud'], backends: ['local', 'apify'] },
  enrichment: { etiqueta: 'Enriquecimiento', descripcion: 'Datos de contacto y empleados. Nube: Apollo.', modos: ['local', 'cloud'], backends: ['local', 'apollo'] },
  crm: { etiqueta: 'CRM espejo', descripcion: 'Espejo de leads. Nube: HubSpot o Twenty.', modos: ['local', 'cloud'], backends: ['local', 'hubspot', 'twenty'] },
  email: { etiqueta: 'Email', descripcion: 'Fase 2: SMTP con dominios dedicados (nunca el corporativo).', modos: ['disabled', 'cloud'], backends: ['local', 'smtp'] },
  weather: { etiqueta: 'Clima', descripcion: 'Temperatura por zona. Open-Meteo, sin llave.', modos: ['cloud'], backends: ['open-meteo'] },
  linkedin: { etiqueta: 'LinkedIn', descripcion: 'Señales cálidas de tu página de empresa.', modos: ['disabled', 'cloud'], backends: ['linkedin'] },
};

const MODO_LABEL: Record<string, string> = { local: 'Local', cloud: 'Nube', disabled: 'Apagado' };

const ETAPAS_PIPELINE: { id: string; label: string }[] = [
  { id: 'radar-01', label: '01 · Radar scrape' },
  { id: 'radar-02', label: '02 · Dedup + score' },
  { id: 'radar-03', label: '03 · Caza señales' },
  { id: 'radar-04', label: '04 · CRM espejo' },
  { id: 'radar-05', label: '05 · LinkedIn' },
];

function puntoColor(estado: 'ok' | 'warn' | 'error' | 'na'): string {
  if (estado === 'ok') return '#2F9E44';
  if (estado === 'warn') return '#E8A13D';
  if (estado === 'error') return '#D64545';
  return '#8a93a6';
}

function estadoDe(healthVal?: string): 'ok' | 'warn' | 'error' | 'na' {
  const e = String(healthVal ?? '').toLowerCase();
  if (e === 'ok') return 'ok';
  if (e === 'error') return 'error';
  if (e === '') return 'na';
  return 'warn';
}

function runBadge(estado?: string) {
  if (estado === 'ok') return <Badge variant="success">OK</Badge>;
  if (estado === 'error') return <Badge variant="destructive">Error</Badge>;
  if (estado === 'running') return <Badge variant="warning">Corriendo</Badge>;
  return <Badge variant="secondary">{estado ?? '—'}</Badge>;
}

interface Confirmacion {
  titulo: string;
  descripcion: string;
  accion: () => Promise<void>;
  etiqueta: string;
}

export default function Sistema() {
  const navigate = useNavigate();
  const [health, setHealth] = React.useState<SystemHealth | null>(null);
  const [providers, setProviders] = React.useState<Provider[]>([]);
  const [linkedin, setLinkedin] = React.useState<LinkedInStatusReal | null>(null);
  const [sinClientId, setSinClientId] = React.useState<boolean | null>(null);
  const [authUrl, setAuthUrl] = React.useState<string | null>(null);
  const [runs, setRuns] = React.useState<PipelineRun[]>([]);
  const [cobertura, setCobertura] = React.useState<Record<string, number> | null>(null);
  const [aiStatus, setAiStatus] = React.useState<AiStatus | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [guardando, setGuardando] = React.useState<string | null>(null);
  const [orgId, setOrgId] = React.useState('');
  const [confirmacion, setConfirmacion] = React.useState<Confirmacion | null>(null);
  const [soloProblemas, setSoloProblemas] = React.useState(false);

  const cargar = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [h, p, li, r, cob, ai] = await Promise.allSettled([
        get<SystemHealth>('/system/health'),
        getProviders(),
        getLinkedInStatus(),
        getRuns(30),
        Promise.all(['koolkat', 'solar', 'evaporativa'].map((linea) => getLeadsCountGeo({ linea }))),
        getAiStatus(),
      ]);
      if (h.status === 'fulfilled') setHealth(h.value);
      else setError(errorMessage(h.reason));
      if (p.status === 'fulfilled') {
        const arr = providersComoArray(p.value);
        setProviders(arr);
        const liProv = arr.find((x) => x.name === 'linkedin');
        const cfg = (liProv?.config ?? {}) as Record<string, unknown>;
        if (typeof cfg.org_id === 'string') setOrgId(cfg.org_id);
        else if (cfg.org_id != null) setOrgId(String(cfg.org_id));
      }
      if (li.status === 'fulfilled') setLinkedin(li.value);
      if (r.status === 'fulfilled') setRuns(runsComoArray(r.value));
      if (cob.status === 'fulfilled') {
        const m: Record<string, number> = {};
        ['koolkat', 'solar', 'evaporativa'].forEach((linea, i) => { m[linea] = cob.value[i]?.total ?? 0; });
        setCobertura(m);
      }
      if (ai.status === 'fulfilled') setAiStatus(ai.value);
      // Sonda de configuración de LinkedIn: /auth responde 501 si falta
      // LINKEDIN_CLIENT_ID o LINKEDIN_REDIRECT_URI en el entorno.
      try {
        const a = await getLinkedInAuth();
        setAuthUrl(a.auth_url ?? a.url ?? null);
        setSinClientId(false);
      } catch (e) {
        if (e instanceof ApiError && e.status === 501) {
          setSinClientId(true);
          setAuthUrl(null);
        } else {
          setSinClientId(null);
        }
      }
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => { cargar(); }, [cargar]);

  const aplicarProvider = async (name: string, body: { mode?: string; provider?: string; config?: Record<string, unknown> }) => {
    setGuardando(name);
    try {
      const actualizado = await putProvider(name, body);
      setProviders((prev) => prev.map((p) => (p.name === name ? { ...p, ...actualizado } : p)));
      toast.success(`Provider «${name}» actualizado`);
    } catch (e) {
      toast.error('No se pudo actualizar el provider', { description: errorMessage(e) });
    } finally {
      setGuardando(null);
    }
  };

  const cambiarModo = (p: Provider, mode: string) => {
    if (p.mode === mode) return;
    const cat = CATALOGO[p.name];
    const backends = cat?.backends ?? [p.provider];
    if (mode === 'cloud') {
      const backend = backends.find((b) => b !== 'local');
      if (!backend) {
        toast.error('Sin backend de nube conocido', { description: `«${p.name}» no tiene backend de nube en el catálogo.` });
        return;
      }
      setConfirmacion({
        titulo: `Pasar «${p.name}» a la nube`,
        descripcion: `El modo pasará a «cloud» con el backend «${backend}». Asegúrate de tener la API key correspondiente en el .env del servidor antes de continuar: si la nube falla, el pipeline sigue en local o salta la rama, pero gastarás llamadas contra una key inválida.`,
        etiqueta: 'Pasar a nube',
        accion: () => aplicarProvider(p.name, { mode: 'cloud', provider: backend }),
      });
      return;
    }
    if (mode === 'local') {
      void aplicarProvider(p.name, { mode: 'local', provider: 'local' });
      return;
    }
    void aplicarProvider(p.name, { mode });
  };

  const cambiarBackend = (p: Provider, backend: string) => {
    if (p.provider === backend) return;
    if (backend === 'local') {
      void aplicarProvider(p.name, { provider: 'local', mode: 'local' });
      return;
    }
    const cat = CATALOGO[p.name];
    if (cat?.modos.includes('cloud') && p.mode !== 'cloud') {
      setConfirmacion({
        titulo: `Usar el backend «${backend}»`,
        descripcion: `«${backend}» es un backend de nube: el provider «${p.name}» pasará a modo «cloud». Asegúrate de tener la API key en el .env del servidor.`,
        etiqueta: 'Usar backend de nube',
        accion: () => aplicarProvider(p.name, { provider: backend, mode: 'cloud' }),
      });
      return;
    }
    void aplicarProvider(p.name, { provider: backend });
  };

  const guardarOrgId = async () => {
    const p = providers.find((x) => x.name === 'linkedin');
    // El PUT de este backend REEMPLAZA config (no fusiona como el original):
    // se envía la config completa fusionada en el cliente.
    const config = { ...((p?.config ?? {}) as Record<string, unknown>), org_id: orgId.trim() };
    await aplicarProvider('linkedin', { config });
  };

  const conectarLinkedIn = () => {
    if (authUrl) {
      window.open(authUrl, '_blank', 'noopener');
      toast.info('Autoriza la app en LinkedIn y regresa aquí.');
    } else {
      toast.error('Sin URL de autorización', { description: 'Revisa la configuración de LinkedIn en el servidor.' });
    }
  };

  const pedirDesconectar = () => {
    setConfirmacion({
      titulo: 'Desconectar LinkedIn',
      descripcion: 'Se removerá el token del proceso actual. Si LINKEDIN_ACCESS_TOKEN está en el .env o el vault, elimínalo ahí para una desconexión permanente. La etapa 05 dejará de generar señales cálidas.',
      etiqueta: 'Desconectar',
      accion: async () => {
        try {
          const r = await postLinkedInDisconnect();
          setLinkedin({ connected: false, nota: r.nota });
          toast.success('LinkedIn desconectado', { description: r.nota });
        } catch (e) {
          toast.error('No se pudo desconectar', { description: errorMessage(e) });
        }
      },
    });
  };

  const liConectado = linkedin?.conectado ?? linkedin?.connected ?? false;
  const liExpirado = linkedinExpirado(linkedin);
  const coberturaOk = cobertura != null && Object.values(cobertura).every((n) => n > 0);
  const scraperProvider = providers.find((p) => p.name === 'scraper');
  const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;

  /* ── Estado vigente por etapa (no confundir con errores históricos) ──
     `runs` viene ordenado del más reciente al más antiguo: el primer run
     de cada pipeline es su estado actual. Los errores viejos se muestran
     como «histórico» (no pintan la fila de rojo) si después hubo un OK. */
  const ultimoDe = React.useMemo(() => {
    const mapa = new Map<string, PipelineRun>();
    for (const r of runs) if (!mapa.has(r.pipeline)) mapa.set(r.pipeline, r);
    return mapa;
  }, [runs]);

  const resumenEtapas = ETAPAS_PIPELINE.map((e) => ({
    ...e,
    run: ultimoDe.get(e.id),
  }));
  const erroresVigentes = resumenEtapas.filter((e) => e.run?.estado === 'error');
  const erroresHistoricos = runs.filter(
    (r) => r.estado === 'error' && ultimoDe.get(r.pipeline)?.run_id !== r.run_id,
  );
  const todaviaRunning = resumenEtapas.filter((e) => e.run?.estado === 'running');

  const filasDiag: { nombre: string; estado: 'ok' | 'warn' | 'error' | 'na'; mensaje: string; accion?: React.ReactNode }[] = [
    {
      nombre: 'Base de datos',
      estado: estadoDe(health?.postgres as string | undefined),
      mensaje: health?.postgres === 'ok' ? 'Postgres + PostGIS responde.' : 'Sin respuesta de Postgres.',
    },
    {
      nombre: 'Proveedores',
      estado: providers.length > 0 ? 'ok' : 'warn',
      mensaje: providers.length > 0 ? `${providers.length} providers registrados en la tabla.` : 'La tabla de providers está vacía (¿corrió la auto-migración?).',
    },
    {
      nombre: 'Cobertura de líneas',
      estado: cobertura == null ? 'na' : coberturaOk ? 'ok' : 'warn',
      mensaje: cobertura == null
        ? 'Sin conteos disponibles.'
        : coberturaOk
          ? `Koolkat ${cobertura.koolkat} · Solar ${cobertura.solar} · Evaporativa ${cobertura.evaporativa}.`
          : `Líneas en 0: ${Object.entries(cobertura).filter(([, n]) => n === 0).map(([k]) => k).join(', ')}. Corre la 01/02 o revisa la regla de línea por mes.`,
      accion: cobertura != null && !coberturaOk
        ? <Button size="sm" variant="outline" onClick={() => navigate('/operacion')}>Ir a Operación</Button>
        : undefined,
    },
    {
      nombre: 'n8n (automatización)',
      estado: estadoDe(health?.n8n as string | undefined),
      mensaje: health?.n8n === 'ok' ? 'n8n responde en /healthz.' : 'n8n no responde (los workflows no correrán).',
    },
    {
      nombre: 'Scraper',
      estado: estadoDe(health?.scraper as string | undefined),
      mensaje: health?.scraper === 'ok'
        ? `Scraper responde. Backend activo: ${scraperProvider?.provider ?? 'sin provider registrado'}.`
        : 'El microservicio scraper no responde.',
    },
  ];

  const liStats = (linkedin?.stats ?? []) as Record<string, unknown>[];
  const liWarm = (linkedin?.warmSignals ?? []) as Record<string, unknown>[];
  const ultimoStat = liStats[0];

  return (
    <div className="flex h-full flex-col">
      <Topbar titulo="Sistema" subtitulo="Salud, conexiones y ajustes. Si algo falla, se ve aquí" />
      <div className="flex-1 space-y-6 overflow-y-auto p-6">
        {error && <Alert variant="destructive"><AlertTitle>Error al cargar el estado</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>}

        {loading ? (
          <div className="space-y-4"><Skeleton className="h-56" /><Skeleton className="h-56" /></div>
        ) : (
          <>
            {/* ── 1 · Diagnóstico (§4.5.1) ─────────────────────────── */}
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle>Diagnóstico</CardTitle>
                  <Button variant="outline" size="sm" onClick={() => cargar()}>Revisar de nuevo</Button>
                </div>
                <CardDescription>Semáforo desde <code>GET /system/health</code> y los conteos reales de leads.</CardDescription>
              </CardHeader>
              <CardContent>
                <ul className="space-y-3">
                  {filasDiag.map((f) => (
                    <li key={f.nombre} className="flex flex-wrap items-center gap-3">
                      <span className="inline-block h-3.5 w-3.5 rounded-full" style={{ backgroundColor: puntoColor(f.estado) }} aria-hidden />
                      <span className="min-w-[10rem] text-sm font-medium">{f.nombre}</span>
                      <span className="flex-1 text-xs text-muted-foreground">{f.mensaje}</span>
                      {f.accion}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>

            {/* ── 1b · Estado vigente por etapa ────────────────────── */}
            <Card>
              <CardHeader>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <CardTitle>Estado vigente por etapa</CardTitle>
                    <CardDescription>
                      Solo cuenta la <strong>última</strong> corrida de cada etapa. Un error antiguo ya corregido
                      aparece como histórico y no significa que el sistema esté caído.
                    </CardDescription>
                  </div>
                  <Button variant="outline" size="sm" onClick={() => navigate('/operacion')}>Ir a Operación</Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
                  {resumenEtapas.map((e) => (
                    <div key={e.id} className="rounded-lg border p-3">
                      <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">{e.label}</p>
                      <div className="mt-1">{runBadge(e.run?.estado)}</div>
                      <p className="mt-1 text-[11px] text-muted-foreground">
                        {e.run?.started_at ? new Date(e.run.started_at).toLocaleString('es-MX') : 'Sin corridas'}
                      </p>
                    </div>
                  ))}
                </div>
                {erroresVigentes.length > 0 ? (
                  <Alert variant="destructive">
                    <AlertTitle>Hay {erroresVigentes.length} etapa(s) con error vigente</AlertTitle>
                    <AlertDescription>
                      {erroresVigentes.map((e) => `${e.label}: ${detalleRunTexto(e.run?.detalle)}`).join(' · ')}
                    </AlertDescription>
                  </Alert>
                ) : (
                  <Alert variant="success">
                    <AlertTitle>Sin errores vigentes en las etapas del Radar</AlertTitle>
                    <AlertDescription>
                      {todaviaRunning.length > 0
                        ? `En ejecución: ${todaviaRunning.map((e) => e.label).join(', ')}.`
                        : 'La última corrida de cada etapa terminó correctamente.'}
                      {erroresHistoricos.length > 0 && ` Hay ${erroresHistoricos.length} error(es) histórico(s) de corridas anteriores (ya reemplazados por una corrida posterior).`}
                    </AlertDescription>
                  </Alert>
                )}
              </CardContent>
            </Card>

            {/* ── 2 · Proveedores (§4.5.2) ─────────────────────────── */}
            <Card>
              <CardHeader>
                <CardTitle>Proveedores</CardTitle>
                <CardDescription>
                  Cada capacidad corre en local $0; cambia a nube solo con la capa gratuita. Pasar a cloud pide confirmación. Los cambios usan <code>PUT /providers/&#123;name&#125;</code>.
                </CardDescription>
              </CardHeader>
              <CardContent>
                {providers.length === 0 ? (
                  <Empty title="Sin providers" description="El backend no devolvió la tabla de providers." icon="🔌" />
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b text-left text-xs uppercase tracking-wider text-muted-foreground">
                          <th className="py-2 pr-4">Capacidad</th>
                          <th className="py-2 pr-4">Modo</th>
                          <th className="py-2">Backend</th>
                        </tr>
                      </thead>
                      <tbody>
                        {providers.map((p) => {
                          const cat = CATALOGO[p.name];
                          const modos = cat?.modos ?? ['local', 'cloud', 'disabled'];
                          const backends = cat?.backends ?? [p.provider];
                          return (
                            <tr key={p.name} className="border-b last:border-0 align-top">
                              <td className="py-3 pr-4">
                                <p className="font-medium">{cat?.etiqueta ?? p.name} <span className="font-mono text-[11px] text-muted-foreground">({p.name} · {p.kind})</span></p>
                                <p className="max-w-md text-[11px] text-muted-foreground">{cat?.descripcion ?? ''}</p>
                                {p.name === 'linkedin' && (
                                  <div className="mt-2 flex max-w-md items-center gap-2">
                                    <Input
                                      value={orgId}
                                      onChange={(e) => setOrgId(e.target.value)}
                                      placeholder="org_id numérico de tu página"
                                      aria-label="org_id de LinkedIn"
                                      className="h-8 text-xs"
                                    />
                                    <Button size="sm" className="h-8 shrink-0" onClick={guardarOrgId} disabled={guardando === 'linkedin'}>
                                      Guardar
                                    </Button>
                                  </div>
                                )}
                              </td>
                              <td className="py-3 pr-4">
                                <div className="flex gap-1" role="group" aria-label={`Modo de ${p.name}`}>
                                  {modos.map((m) => (
                                    <Button
                                      key={m}
                                      size="sm"
                                      variant={p.mode === m ? 'default' : 'outline'}
                                      className={cn('h-7 px-2 text-xs', m === 'disabled' && p.mode !== 'disabled' && 'text-muted-foreground')}
                                      disabled={guardando === p.name}
                                      onClick={() => cambiarModo(p, m)}
                                    >
                                      {MODO_LABEL[m] ?? m}
                                    </Button>
                                  ))}
                                </div>
                              </td>
                              <td className="py-3">
                                {backends.length > 1 ? (
                                  <select
                                    value={p.provider}
                                    disabled={guardando === p.name}
                                    onChange={(e) => cambiarBackend(p, e.target.value)}
                                    aria-label={`Backend de ${p.name}`}
                                    className="h-8 rounded-md border border-input bg-background px-2 text-xs"
                                  >
                                    {backends.map((b) => <option key={b} value={b}>{b}</option>)}
                                    {!backends.includes(p.provider) && <option value={p.provider}>{p.provider}</option>}
                                  </select>
                                ) : (
                                  <span className="font-mono text-xs text-muted-foreground">{p.provider}</span>
                                )}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* ── 3 · LinkedIn (§4.5.3) ────────────────────────────── */}
            <Card>
              <CardHeader>
                <CardTitle>LinkedIn · página de empresa</CardTitle>
                <CardDescription>Desde <code>GET /integrations/linkedin/status</code> (sin secretos: el token vive en el entorno).</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {sinClientId ? (
                  <Alert variant="destructive">
                    <AlertTitle>Falta LINKEDIN_CLIENT_ID</AlertTitle>
                    <AlertDescription>
                      Crea una app en developer.linkedin.com (productos: Share on LinkedIn + Sign In with LinkedIn using OpenID Connect, y solicita Community Management API), define LINKEDIN_CLIENT_ID, LINKEDIN_CLIENT_SECRET y LINKEDIN_REDIRECT_URI en el .env del servidor y reinicia el backend.
                    </AlertDescription>
                  </Alert>
                ) : !liConectado ? (
                  <>
                    <p className="text-sm">LinkedIn no está conectado: la etapa 05 no puede leer las señales de tu página.</p>
                    <Alert variant="info">
                      <AlertDescription>
                        Nota honesta: la API de LinkedIn <strong>no permite buscar prospectos ni extraer contactos</strong>; aquí solo se monitorean las señales de tu propia página (seguidores y engagement).
                      </AlertDescription>
                    </Alert>
                    {linkedin?.nota && <p className="text-xs text-muted-foreground">{linkedin.nota}</p>}
                    <div className="flex gap-2">
                      <Button size="sm" onClick={conectarLinkedIn} disabled={!authUrl}>Conectar LinkedIn</Button>
                      <Button size="sm" variant="outline" onClick={() => cargar()}>Ya autoricé, actualizar</Button>
                    </div>
                  </>
                ) : (
                  <>
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="success">Conectado</Badge>
                      {liExpirado
                        ? <Badge variant="warning">Token expirado — reconecta</Badge>
                        : <Badge variant="outline">Token presente en el entorno</Badge>}
                    </div>
                    {linkedin?.nota && <p className="text-xs text-muted-foreground">{linkedin.nota}</p>}
                    {ultimoStat ? (
                      <div className="grid grid-cols-3 gap-3 text-center">
                        <div><p className="font-mono text-2xl font-bold">{String(ultimoStat.followers ?? '—')}</p><p className="text-[11px] text-muted-foreground">Seguidores</p></div>
                        <div><p className="font-mono text-2xl font-bold">{String(ultimoStat.posts_count ?? '—')}</p><p className="text-[11px] text-muted-foreground">Posts evaluados</p></div>
                        <div><p className="font-mono text-2xl font-bold">{String(ultimoStat.engagement_total ?? '—')}</p><p className="text-[11px] text-muted-foreground">Engagement</p></div>
                      </div>
                    ) : (
                      <p className="text-xs text-muted-foreground">
                        Este backend confirma la conexión por variable de entorno y no devuelve la serie de stats en <code>/status</code>; las métricas diarias las genera la etapa 05.
                      </p>
                    )}
                    <Separator />
                    <div>
                      <p className="mb-1 text-sm font-semibold">Señales cálidas pendientes</p>
                      {liWarm.length > 0 ? (
                        <ul className="space-y-1 text-xs">
                          {liWarm.map((s, i) => (
                            <li key={i} className="border-b py-1 last:border-0">
                              <span className="font-medium">{String(s.titulo ?? 'Señal')}</span>
                              {s.detalle != null && <span className="text-muted-foreground"> — {String(s.detalle)}</span>}
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="text-xs text-muted-foreground">Sin señales cálidas pendientes reportadas por la API. La etapa 05 las genera cada lunes.</p>
                      )}
                    </div>
                    <Button variant="destructive" size="sm" onClick={pedirDesconectar}>Desconectar</Button>
                  </>
                )}
              </CardContent>
            </Card>

            {/* ── 4 · Bitácora (§4.5.4) ────────────────────────────── */}
            <Card>
              <CardHeader>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <CardTitle>Bitácora de ejecuciones</CardTitle>
                    <CardDescription>
                      Historial completo. Solo la última corrida de cada etapa define el estado actual;
                      los errores anteriores se marcan como «histórico».
                    </CardDescription>
                  </div>
                  <Button
                    variant={soloProblemas ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setSoloProblemas((v) => !v)}
                  >
                    {soloProblemas ? 'Ver todo el historial' : 'Solo problemas vigentes'}
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                {runs.length === 0 ? (
                  <Empty title="Sin ejecuciones aún" description="Ve a Operación y corre la etapa 01 para registrar la primera corrida." icon="📜"
                    action={{ label: 'Ir a Operación', onClick: () => navigate('/operacion') }} />
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b text-left text-xs uppercase tracking-wider text-muted-foreground">
                          <th className="py-2 pr-4">#</th>
                          <th className="py-2 pr-4">Etapa</th>
                          <th className="py-2 pr-4">Estado</th>
                          <th className="py-2 pr-4">Inicio</th>
                          <th className="py-2 pr-4">Fin</th>
                          <th className="py-2">Detalle</th>
                        </tr>
                      </thead>
                      <tbody>
                        {runs.slice(0, 30).map((r) => (
                          <tr key={r.run_id} className={cn('border-b last:border-0', r.estado === 'error' && 'bg-destructive/5')}>
                            <td className="py-2 pr-4 font-mono text-xs">{r.run_id}</td>
                            <td className="py-2 pr-4 font-mono text-xs">{r.pipeline}</td>
                            <td className="py-2 pr-4">{runBadge(r.estado)}</td>
                            <td className="py-2 pr-4 font-mono text-xs">{r.started_at ? new Date(r.started_at).toLocaleString('es-MX') : '—'}</td>
                            <td className="py-2 pr-4 font-mono text-xs">{r.finished_at ? new Date(r.finished_at).toLocaleString('es-MX') : '—'}</td>
                            <td className={cn('py-2 text-xs', r.estado === 'error' ? 'font-medium text-destructive' : 'text-muted-foreground')}>{detalleRunTexto(r.detalle)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
                <p className="mt-3 text-[11px] text-muted-foreground">
                  Nota: la API actual (<code>GET /pipelines/runs</code>) devuelve solo las corridas locales registradas en <code>prod.runs</code>; no expone las ejecuciones internas de n8n (en el dashboard original eso requería <code>N8N_API_KEY</code> y solo afectaba la lectura).
                </p>
              </CardContent>
            </Card>

            {/* ── 5 · Configuración técnica (§4.5.5) ───────────────── */}
            <Card>
              <CardHeader>
                <CardTitle>Configuración técnica</CardTitle>
                <CardDescription>Solo se muestra si las cosas existen (✓/✗), nunca sus valores. Las llaves viven en el .env del servidor.</CardDescription>
              </CardHeader>
              <CardContent>
                <dl className="space-y-2 text-sm">
                  <div className="flex flex-wrap justify-between gap-2 border-b py-1.5">
                    <dt className="text-muted-foreground">Versión</dt>
                    <dd className="text-xs">No expuesta por la API actual (el dashboard original la servía en <code>/api/config</code>).</dd>
                  </div>
                  <div className="flex flex-wrap justify-between gap-2 border-b py-1.5">
                    <dt className="text-muted-foreground">Zona horaria (este navegador)</dt>
                    <dd className="font-mono text-xs">{tz}</dd>
                  </div>
                  <div className="flex flex-wrap justify-between gap-2 border-b py-1.5">
                    <dt className="text-muted-foreground">n8n</dt>
                    <dd className="text-xs">{health?.n8n === 'ok' ? '✓ responde' : '✗ sin respuesta'} · su URL interna y su API key no las expone la API</dd>
                  </div>
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b py-1.5">
                    <dt className="text-muted-foreground">Webhooks radar-01…05</dt>
                    <dd className="flex flex-wrap gap-1">
                      {['radar-01', 'radar-02', 'radar-03', 'radar-04', 'radar-05'].map((w) => (
                        <Badge key={w} variant="outline" className="font-mono text-[10px]">{w}: n/d</Badge>
                      ))}
                    </dd>
                  </div>
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b py-1.5">
                    <dt className="text-muted-foreground">Keys de nube (Radar)</dt>
                    <dd className="text-xs">apify / apollo / hubspot / linkedin: presencia no expuesta por la API — se verifica en el .env</dd>
                  </div>
                  <div className="flex flex-wrap items-center justify-between gap-2 py-1.5">
                    <dt className="text-muted-foreground">Keys de IA interna (<code>GET /ai/status</code>)</dt>
                    <dd className="flex flex-wrap gap-1">
                      {(aiStatus?.providers ?? []).length === 0
                        ? <span className="text-xs">Sin datos de /ai/status.</span>
                        : aiStatus!.providers.map((p) => (
                          <Badge key={p.name} variant={p.configured ? 'success' : 'outline'} className="font-mono text-[10px]">
                            {p.configured ? '✓' : '✗'} {p.name}
                          </Badge>
                        ))}
                    </dd>
                  </div>
                </dl>
              </CardContent>
            </Card>
          </>
        )}
      </div>

      <Dialog open={!!confirmacion} onOpenChange={(o) => { if (!o) setConfirmacion(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{confirmacion?.titulo}</DialogTitle>
            <DialogDescription>{confirmacion?.descripcion}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmacion(null)}>Cancelar</Button>
            <Button
              onClick={() => { const c = confirmacion; setConfirmacion(null); if (c) void c.accion(); }}
            >
              {confirmacion?.etiqueta ?? 'Confirmar'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

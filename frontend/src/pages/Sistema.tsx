import * as React from 'react';
import { Topbar } from '@/components/layout/Topbar';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/Alert';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Skeleton } from '@/components/ui/Skeleton';
import { Separator } from '@/components/ui/Separator';
import { Empty } from '@/components/ui/Empty';
import { get, put, post, errorMessage, type SystemHealth, type Provider, type LinkedInStatus, type PipelineRun } from '@/lib/api';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

/** Convierte un estado de servicio a color de semáforo. */
function semaforo(estado?: string): { color: string; etiqueta: string } {
  const e = String(estado ?? '').toLowerCase();
  if (['ok', 'up', 'healthy', 'conectado', 'activo', 'true', 'local', 'cloud'].includes(e))
    return { color: '#2F9E44', etiqueta: 'Operativo' };
  if (['degraded', 'warn', 'warning', 'lento', 'parcial'].includes(e))
    return { color: '#E8A13D', etiqueta: 'Degradado' };
  if (['disabled', 'false', 'apagado'].includes(e))
    return { color: '#8a93a6', etiqueta: 'Apagado' };
  if (e === '' || e === 'null' || e === 'undefined')
    return { color: '#8a93a6', etiqueta: 'Desconocido' };
  return { color: '#D64545', etiqueta: 'Fuera de servicio' };
}

/** El health devuelve los providers como dict {mode, enabled}: extrae un estado legible. */
function estadoProvider(v: unknown): string | undefined {
  if (typeof v === 'string' || typeof v === 'boolean') return String(v);
  if (v && typeof v === 'object') {
    const o = v as Record<string, unknown>;
    if (typeof o.status === 'string') return o.status;
    if (typeof o.mode === 'string') return o.enabled === false ? 'disabled' : o.mode;
    if (typeof o.enabled === 'boolean') return o.enabled ? 'true' : 'false';
  }
  return undefined;
}

const MODOS = [
  { id: 'local', label: 'Local' },
  { id: 'cloud', label: 'Nube' },
  { id: 'disabled', label: 'Apagado' },
] as const;

const PROVIDER_INFO: Record<string, string> = {
  scraper: 'Extracción de establecimientos (Playwright local / Apify nube).',
  enrichment: 'Enriquecimiento de datos de contacto (Apollo en la nube).',
  crm: 'Sincronización de leads al CRM (HubSpot / Twenty).',
  email: 'Envío de correos de contacto (apagado en fase 1; nunca el dominio corporativo).',
  weather: 'Temperatura por zona (Open-Meteo, sin clave).',
  linkedin: 'Estadísticas de la página de empresa de LinkedIn.',
  geocoding: 'Geocodificación de direcciones.',
  routing: 'Cálculo de rutas y tiempos de traslado.',
};

function runBadge(estado?: string) {
  if (estado === 'ok') return <Badge variant="success">OK</Badge>;
  if (estado === 'error') return <Badge variant="destructive">Error</Badge>;
  if (estado === 'running') return <Badge variant="warning">Corriendo</Badge>;
  return <Badge variant="secondary">{estado ?? '—'}</Badge>;
}

export default function Sistema() {
  const [health, setHealth] = React.useState<SystemHealth | null>(null);
  const [providers, setProviders] = React.useState<Provider[]>([]);
  const [linkedin, setLinkedin] = React.useState<LinkedInStatus | null>(null);
  const [runs, setRuns] = React.useState<PipelineRun[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [guardando, setGuardando] = React.useState<string | null>(null);

  const cargar = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [h, p, li, r] = await Promise.all([
        get<SystemHealth>('/system/health'),
        get<{ items?: Provider[] } | Provider[]>('/providers'),
        get<LinkedInStatus>('/integrations/linkedin/status').catch(() => null),
        get<{ items?: PipelineRun[] } | PipelineRun[]>('/pipelines/runs', { limit: 10 }).catch(() => null),
      ]);
      setHealth(h);
      setProviders(Array.isArray(p) ? p : (p.items ?? []));
      setLinkedin(li);
      setRuns(r ? (Array.isArray(r) ? r : (r.items ?? [])) : []);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => { cargar(); }, [cargar]);

  const cambiarModo = async (name: string, mode: string) => {
    setGuardando(name);
    try {
      await put(`/providers/${name}`, { mode });
      setProviders((prev) => prev.map((p) => (p.name === name ? { ...p, mode } : p)));
      toast.success(`Provider «${name}» → ${mode}`);
    } catch (e) {
      toast.error('No se pudo cambiar el modo', { description: errorMessage(e) });
    } finally {
      setGuardando(null);
    }
  };

  const conectarLinkedIn = async () => {
    try {
      const r = await get<{ auth_url?: string; url?: string }>('/integrations/linkedin/auth');
      const url = r.auth_url ?? r.url;
      if (url) {
        window.open(url, '_blank', 'noopener');
        toast.info('Autoriza la app en LinkedIn y regresa aquí.');
      } else {
        toast.error('El backend no devolvió una URL de autorización.');
      }
    } catch (e) {
      toast.error('No se pudo iniciar la conexión', { description: errorMessage(e) });
    }
  };

  const desconectarLinkedIn = async () => {
    try {
      await post('/integrations/linkedin/disconnect');
      setLinkedin({ conectado: false });
      toast.success('LinkedIn desconectado');
    } catch (e) {
      toast.error('No se pudo desconectar', { description: errorMessage(e) });
    }
  };

  const servicios: [string, unknown][] = health
    ? [
        ['PostgreSQL + PostGIS', health.postgres],
        ['n8n (orquestador)', health.n8n],
        ['Scraper (:5000)', health.scraper],
        ...Object.entries(health.providers ?? {}),
      ]
    : [];

  const liConectado = linkedin?.conectado ?? linkedin?.connected ?? false;

  return (
    <div className="flex h-full flex-col">
      <Topbar titulo="Sistema" subtitulo="Diagnóstico, providers anti-cautiverio e integraciones" />
      <div className="flex-1 space-y-6 overflow-y-auto p-6">
        {error && <Alert variant="destructive"><AlertTitle>Error al cargar el estado</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>}

        {loading ? (
          <div className="grid gap-4 lg:grid-cols-2"><Skeleton className="h-64" /><Skeleton className="h-64" /></div>
        ) : (
          <>
            <div className="grid gap-4 lg:grid-cols-2">
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle>Semáforo de servicios</CardTitle>
                    <Button variant="outline" size="sm" onClick={() => cargar()}>Recargar</Button>
                  </div>
                  <CardDescription>Estado reportado por <code>GET /system/health</code>.</CardDescription>
                </CardHeader>
                <CardContent>
                  {servicios.length === 0 ? (
                    <Empty title="Sin datos" description="El backend no devolvió el estado de los servicios." icon="🖥️" />
                  ) : (
                    <ul className="space-y-3">
                      {servicios.map(([nombre, estado]) => {
                        const s = semaforo(estadoProvider(estado));
                        return (
                          <li key={nombre} className="flex items-center gap-3">
                            <span className="inline-block h-3.5 w-3.5 rounded-full" style={{ backgroundColor: s.color }} aria-hidden />
                            <span className="flex-1 text-sm font-medium">{nombre}</span>
                            <Badge variant="outline">{s.etiqueta}</Badge>
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>LinkedIn</CardTitle>
                  <CardDescription>Integración de la página de empresa (pipeline radar-05).</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex items-center gap-3">
                    <span className="inline-block h-3.5 w-3.5 rounded-full" style={{ backgroundColor: liConectado ? '#2F9E44' : '#8a93a6' }} aria-hidden />
                    <span className="text-sm font-medium">{liConectado ? 'Conectado' : 'No conectado'}</span>
                  </div>
                  {linkedin && Object.entries(linkedin).filter(([k]) => !['conectado', 'connected'].includes(k)).length > 0 && (
                    <dl className="space-y-1 text-xs">
                      {Object.entries(linkedin)
                        .filter(([k]) => !['conectado', 'connected'].includes(k))
                        .map(([k, v]) => (
                          <div key={k} className="flex justify-between gap-4">
                            <dt className="text-muted-foreground">{k}</dt>
                            <dd className="font-mono">{typeof v === 'object' ? JSON.stringify(v) : String(v)}</dd>
                          </div>
                        ))}
                    </dl>
                  )}
                  <Separator />
                  <div className="flex gap-2">
                    {liConectado ? (
                      <Button variant="destructive" size="sm" onClick={desconectarLinkedIn}>Desconectar</Button>
                    ) : (
                      <Button size="sm" onClick={conectarLinkedIn}>Conectar LinkedIn</Button>
                    )}
                  </div>
                  <p className="text-[11px] text-muted-foreground">
                    Requiere la app de LinkedIn con permisos de Community Management. Los tokens viven en el vault/.env, nunca en el frontend.
                  </p>
                </CardContent>
              </Card>
            </div>

            <Card>
              <CardHeader>
                <CardTitle>Providers · capa anti-cautiverio</CardTitle>
                <CardDescription>
                  Cada capacidad tiene backend local y opción en la nube. Si la nube falla, el sistema usa el modo local o salta la rama: los datos siempre aterrizan primero en Postgres.
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
                          <th className="py-2 pr-4">Provider</th>
                          <th className="py-2 pr-4">Tipo</th>
                          <th className="py-2 pr-4">Backend</th>
                          <th className="py-2">Modo</th>
                        </tr>
                      </thead>
                      <tbody>
                        {providers.map((p) => (
                          <tr key={p.name} className="border-b last:border-0">
                            <td className="py-2 pr-4">
                              <p className="font-mono text-xs font-semibold">{p.name}</p>
                              <p className="max-w-md text-[11px] text-muted-foreground">{PROVIDER_INFO[p.name] ?? ''}</p>
                            </td>
                            <td className="py-2 pr-4 text-xs text-muted-foreground">{p.kind}</td>
                            <td className="py-2 pr-4 text-xs text-muted-foreground">{p.provider}</td>
                            <td className="py-2">
                              <div className="flex gap-1" role="group" aria-label={`Modo de ${p.name}`}>
                                {MODOS.map((m) => (
                                  <Button
                                    key={m.id}
                                    size="sm"
                                    variant={p.mode === m.id ? 'default' : 'outline'}
                                    className={cn('h-7 px-2 text-xs', m.id === 'disabled' && p.mode !== 'disabled' && 'text-muted-foreground')}
                                    disabled={guardando === p.name}
                                    onClick={() => cambiarModo(p.name, m.id)}
                                  >
                                    {m.label}
                                  </Button>
                                ))}
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader><CardTitle>Bitácora reciente</CardTitle></CardHeader>
              <CardContent>
                {runs.length === 0 ? (
                  <p className="text-sm text-muted-foreground">Sin corridas recientes.</p>
                ) : (
                  <ul className="space-y-2">
                    {runs.slice(0, 8).map((r) => (
                      <li key={r.run_id} className="flex items-center gap-3 text-sm">
                        <span className="font-mono text-xs">{r.pipeline}</span>
                        {runBadge(r.estado)}
                        <span className="ml-auto font-mono text-xs text-muted-foreground">
                          {r.started_at ? new Date(r.started_at).toLocaleString('es-MX') : ''}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          </>
        )}
      </div>
    </div>
  );
}

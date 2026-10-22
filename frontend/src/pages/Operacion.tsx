import * as React from 'react';
import { Topbar } from '@/components/layout/Topbar';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/Alert';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Spinner } from '@/components/ui/Spinner';
import { Skeleton } from '@/components/ui/Skeleton';
import { Separator } from '@/components/ui/Separator';
import { post, get, ApiError, errorMessage, type PipelineRun } from '@/lib/api';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

interface Paso {
  id: string;
  titulo: string;
  descripcion: string;
  grupo: 'radar' | 'etl';
}

const PASOS: Paso[] = [
  { id: 'radar-01', titulo: '01 · Scrapeo', descripcion: 'Busca en Google Maps, normaliza y guarda en el staging crudo.', grupo: 'radar' },
  { id: 'radar-02', titulo: '02 · Deduplicado + score', descripcion: 'Dedup por nombre+dirección, temperatura Open-Meteo, score y línea recomendada.', grupo: 'radar' },
  { id: 'radar-03', titulo: '03 · Señales', descripcion: 'Procesa señales manuales del SDR y cálidas de LinkedIn (+score).', grupo: 'radar' },
  { id: 'radar-04', titulo: '04 · CRM', descripcion: 'Espeja los leads al CRM en la nube (o termina si el CRM es local).', grupo: 'radar' },
  { id: 'radar-05', titulo: '05 · LinkedIn', descripcion: 'Lee las métricas de la página de empresa y detecta picos de engagement.', grupo: 'radar' },
  { id: 'etl-denue', titulo: 'ETL · DENUE', descripcion: 'Carga y actualiza el padrón de establecimientos (edición INEGI vigente).', grupo: 'etl' },
  { id: 'etl-censo', titulo: 'ETL · Censo', descripcion: 'Carga y actualiza población y viviendas por AGEB (Censo vigente).', grupo: 'etl' },
];

function runBadge(estado?: string) {
  if (estado === 'ok') return <Badge variant="success">OK</Badge>;
  if (estado === 'error') return <Badge variant="destructive">Error</Badge>;
  if (estado === 'running') return <Badge variant="warning">Corriendo</Badge>;
  return <Badge variant="secondary">Sin corridas</Badge>;
}

function detalleTexto(detalle: unknown): string {
  if (detalle === null || detalle === undefined) return '—';
  if (typeof detalle === 'string') return detalle;
  if (typeof detalle === 'object' && detalle !== null && 'message' in detalle) {
    return String((detalle as Record<string, unknown>).message);
  }
  return JSON.stringify(detalle);
}

export default function Operacion() {
  const [runs, setRuns] = React.useState<PipelineRun[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [corriendo, setCorriendo] = React.useState<string | null>(null);
  const [bloqueo, setBloqueo] = React.useState<{ paso: string; motivo: string } | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  const cargar = React.useCallback(async () => {
    try {
      const r = await get<{ items?: PipelineRun[] } | PipelineRun[]>('/pipelines/runs', { limit: 100 });
      const arr = Array.isArray(r) ? r : (r.items ?? []);
      setRuns(arr);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => { cargar(); }, [cargar]);

  const ultimoRun = React.useCallback(
    (pipeline: string) => runs.find((r) => r.pipeline === pipeline),
    [runs],
  );

  const ejecutar = async (paso: Paso) => {
    setCorriendo(paso.id);
    setBloqueo(null);
    try {
      await post(`/pipelines/run/${paso.id}`);
      toast.success(`Pipeline ${paso.id} lanzado`, { description: 'La corrida quedó registrada en la bitácora.' });
      await cargar();
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        setBloqueo({ paso: paso.id, motivo: e.message });
        toast.warning('Pipeline bloqueado por orden', { description: e.message });
      } else {
        toast.error('No se pudo lanzar el pipeline', { description: errorMessage(e) });
      }
    } finally {
      setCorriendo(null);
    }
  };

  return (
    <div className="flex h-full flex-col">
      <Topbar titulo="Operación" subtitulo="Orquestación de pipelines · Radar 01→05 + ETL · con bloqueo por orden" />
      <div className="flex-1 space-y-6 overflow-y-auto p-6">
        {error && <Alert variant="destructive"><AlertTitle>Error al cargar la bitácora</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>}
        {bloqueo && (
          <Alert variant="warning">
            <AlertTitle>⛔ {bloqueo.paso} bloqueado</AlertTitle>
            <AlertDescription>{bloqueo.motivo}</AlertDescription>
          </Alert>
        )}

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Pipeline de ejecución</CardTitle>
                <CardDescription>
                  Pulsa ▶ para lanzar un paso. Los pasos del módulo Radar corren en orden 01→05: si el paso anterior no terminó OK, la API devuelve 409 con el motivo.
                </CardDescription>
              </div>
              <Button variant="outline" size="sm" onClick={() => cargar()}>Recargar</Button>
            </div>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="flex gap-3 overflow-x-auto"><Skeleton className="h-36 w-52 shrink-0" /><Skeleton className="h-36 w-52 shrink-0" /><Skeleton className="h-36 w-52 shrink-0" /></div>
            ) : (
              <div className="flex items-stretch gap-0 overflow-x-auto pb-2">
                {PASOS.map((p, i) => {
                  const run = ultimoRun(p.id);
                  const enCurso = corriendo === p.id;
                  return (
                    <React.Fragment key={p.id}>
                      <div className="w-56 shrink-0 rounded-lg border bg-card p-4 shadow-sm">
                        <div className="mb-2 flex items-center justify-between">
                          <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{p.titulo}</span>
                          {runBadge(run?.estado)}
                        </div>
                        <p className="mb-3 min-h-[3.5rem] text-xs leading-snug text-muted-foreground">{p.descripcion}</p>
                        <Button
                          size="sm"
                          className="w-full"
                          variant={p.grupo === 'radar' ? 'default' : 'secondary'}
                          disabled={enCurso}
                          onClick={() => ejecutar(p)}
                          title={`Lanzar ${p.id}`}
                        >
                          {enCurso ? <Spinner size={14} /> : '▶'} Lanzar
                        </Button>
                        {bloqueo?.paso === p.id && (
                          <p className="mt-2 text-[11px] text-warning">⛔ {bloqueo.motivo}</p>
                        )}
                        {run && (
                          <p className="mt-2 font-mono text-[11px] text-muted-foreground" title={detalleTexto(run.detalle)}>
                            {run.started_at ? new Date(run.started_at).toLocaleString('es-MX', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : ''}
                          </p>
                        )}
                      </div>
                      {i < PASOS.length - 1 && (
                        <div className="flex shrink-0 items-center px-1" aria-hidden>
                          <span className={cn('text-xl', p.grupo === 'etl' ? 'text-muted-foreground/40' : 'text-primary')}>→</span>
                        </div>
                      )}
                    </React.Fragment>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Bitácora de corridas</CardTitle>
            <CardDescription>Últimas ejecuciones de todos los pipelines (Radar + ETL).</CardDescription>
          </CardHeader>
          <CardContent>
            {runs.length === 0 ? (
              <p className="text-sm text-muted-foreground">Aún no hay corridas registradas.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-xs uppercase tracking-wider text-muted-foreground">
                      <th className="py-2 pr-4">Pipeline</th>
                      <th className="py-2 pr-4">Estado</th>
                      <th className="py-2 pr-4">Inicio</th>
                      <th className="py-2 pr-4">Fin</th>
                      <th className="py-2">Detalle</th>
                    </tr>
                  </thead>
                  <tbody>
                    {runs.slice(0, 50).map((r) => (
                      <tr key={r.run_id} className="border-b last:border-0">
                        <td className="py-2 pr-4 font-mono text-xs">{r.pipeline}</td>
                        <td className="py-2 pr-4">{runBadge(r.estado)}</td>
                        <td className="py-2 pr-4 font-mono text-xs">{r.started_at ? new Date(r.started_at).toLocaleString('es-MX') : '—'}</td>
                        <td className="py-2 pr-4 font-mono text-xs">{r.finished_at ? new Date(r.finished_at).toLocaleString('es-MX') : '—'}</td>
                        <td className="py-2 text-xs text-muted-foreground">{detalleTexto(r.detalle)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <Separator className="my-4" />
            <p className="text-xs text-muted-foreground">
              El bloqueo por orden lo aplica el backend (lee <code>prod.runs</code>): un paso no puede lanzarse si el anterior no terminó en <code>ok</code>.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

import * as React from 'react';
import { useNavigate } from 'react-router-dom';
import { Topbar } from '@/components/layout/Topbar';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/Alert';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Spinner } from '@/components/ui/Spinner';
import { Skeleton } from '@/components/ui/Skeleton';
import { Separator } from '@/components/ui/Separator';
import { Input } from '@/components/ui/Input';
import { Field } from '@/components/ui/Field';
import { NativeSelect } from '@/components/ui/NativeSelect';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '@/components/ui/Dialog';
import {
  post, get, geocode, ApiError, errorMessage,
  type PipelineRun, type Provider, type LeadCurado,
} from '@/lib/api';
import {
  getRuns, runsComoArray, detalleRunTexto, getWorkflows, getProviders, providersComoArray,
  postEnrichGeo, getLinkedInStatus, linkedinExpirado, getLinkedInAuth, getWeather,
  useGeoFiltros,
  type WorkflowOut, type LinkedInStatusReal, type WeatherOut,
} from '@/lib/apiGeo';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

interface Paso {
  id: string;
  titulo: string;
  descripcion: string;
  grupo: 'radar' | 'etl';
  cron: string;
  predecesor?: string;
}

/** Entidades federativas (selector del territorio del Radar). */
const ENTIDADES_MX = [
  'Aguascalientes', 'Baja California', 'Baja California Sur', 'Campeche',
  'Chiapas', 'Chihuahua', 'Ciudad de México', 'Coahuila', 'Colima',
  'Durango', 'Estado de México', 'Guanajuato', 'Guerrero', 'Hidalgo',
  'Jalisco', 'Michoacán', 'Morelos', 'Nayarit', 'Nuevo León', 'Oaxaca',
  'Puebla', 'Querétaro', 'Quintana Roo', 'San Luis Potosí', 'Sinaloa',
  'Sonora', 'Tabasco', 'Tamaulipas', 'Tlaxcala', 'Veracruz', 'Yucatán',
  'Zacatecas',
];

const LS_RADAR_TARGET = 'geis:radar:target';

interface RadarTarget {
  entidad: string;
  municipio: string;
  colonia: string;
  cp: string;
  giros: string;
}

const TARGET_VACIO: RadarTarget = { entidad: '', municipio: '', colonia: '', cp: '', giros: '' };

function leerTargetRadar(): RadarTarget {
  try {
    const crudo = localStorage.getItem(LS_RADAR_TARGET);
    if (!crudo) return TARGET_VACIO;
    const datos = JSON.parse(crudo) as Partial<RadarTarget>;
    return {
      entidad: String(datos.entidad ?? ''),
      municipio: String(datos.municipio ?? ''),
      colonia: String(datos.colonia ?? ''),
      cp: String(datos.cp ?? ''),
      giros: String(datos.giros ?? ''),
    };
  } catch {
    return TARGET_VACIO;
  }
}

function textoUbicacion(t: Pick<RadarTarget, 'entidad' | 'municipio' | 'colonia' | 'cp'>): string {
  return [t.colonia, t.municipio, t.entidad].filter(Boolean).join(', ')
    + (t.cp ? `${t.colonia || t.municipio || t.entidad ? ' · ' : ''}CP ${t.cp}` : '');
}

/** Catálogo de etapas del original (inventario §4.2) con su cron de n8n. */
const PASOS: Paso[] = [
  { id: 'radar-01', titulo: '01 · Radar scrape', descripcion: 'Busca en Google Maps los giros elegidos en el Territorio del Radar (o los corredores por defecto), normaliza y guarda en el staging crudo.', grupo: 'radar', cron: '0 6 * * 1 · lunes 6:00' },
  { id: 'radar-02', titulo: '02 · Dedup + score', descripcion: 'Dedup por nombre+dirección, temperatura Open-Meteo, score, línea recomendada y enriquecimiento Apollo opcional.', grupo: 'radar', cron: 'manual / tras 01', predecesor: 'radar-01' },
  { id: 'radar-03', titulo: '03 · Caza señales', descripcion: 'Procesa señales manuales del SDR y cálidas de LinkedIn (+25 score por señal).', grupo: 'radar', cron: '0 7 * * * · diario 7:00', predecesor: 'radar-02' },
  { id: 'radar-04', titulo: '04 · Sync CRM espejo', descripcion: 'Espeja los leads al CRM en la nube (HubSpot/Twenty); si el CRM es local, termina sin hacer nada.', grupo: 'radar', cron: 'manual (apagado en v1)', predecesor: 'radar-02' },
  { id: 'radar-05', titulo: '05 · Señales LinkedIn', descripcion: 'Lee las métricas de la página de empresa y detecta picos de engagement (señales cálidas).', grupo: 'radar', cron: '0 8 * * 1 · lunes 8:00' },
  { id: 'etl-denue', titulo: 'ETL · DENUE', descripcion: 'Carga y actualiza el padrón de establecimientos (edición INEGI vigente).', grupo: 'etl', cron: 'manual' },
  { id: 'etl-censo', titulo: 'ETL · Censo', descripcion: 'Carga y actualiza población y viviendas por AGEB (Censo vigente).', grupo: 'etl', cron: 'manual' },
];

function runBadge(estado?: string) {
  if (estado === 'ok') return <Badge variant="success">OK</Badge>;
  if (estado === 'error') return <Badge variant="destructive">Error</Badge>;
  if (estado === 'running') return <Badge variant="warning">Corriendo</Badge>;
  return <Badge variant="secondary">Sin corridas</Badge>;
}

function textoUltima(run?: PipelineRun): string {
  if (!run) return 'Sin ejecutar aún';
  const fecha = run.started_at
    ? new Date(run.started_at).toLocaleString('es-MX', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
    : '';
  if (run.estado === 'ok') return `Última: OK · ${fecha}`;
  if (run.estado === 'running') return 'En ejecución…';
  if (run.estado === 'error') return 'Última: error';
  return `Última: ${run.estado} · ${fecha}`;
}

/** Motivo de bloqueo client-side, espejo de la regla R10 del backend. */
function motivoBloqueo(paso: Paso, ultimoDe: (p: string) => PipelineRun | undefined): string | null {
  if (!paso.predecesor) return null;
  const pred = ultimoDe(paso.predecesor);
  if (pred?.estado === 'ok') return null;
  const base = `${paso.id} requiere que ${paso.predecesor} haya terminado con estado 'ok'`;
  if (!pred) return `${base}: ${paso.predecesor} nunca se ha ejecutado, ejecútala primero`;
  if (pred.estado === 'running') {
    const desde = pred.started_at ? ` desde ${new Date(pred.started_at).toLocaleString('es-MX')}` : '';
    return `${base}: ${paso.predecesor} sigue en ejecución${desde}; si se atoró, revísala en n8n → Executions`;
  }
  if (pred.estado === 'error') {
    return `${base}: ${paso.predecesor} terminó en error. Último detalle: ${detalleRunTexto(pred.detalle)}`;
  }
  return base;
}

export default function Operacion() {
  const navigate = useNavigate();
  const [runs, setRuns] = React.useState<PipelineRun[]>([]);
  const [workflows, setWorkflows] = React.useState<WorkflowOut[]>([]);
  const [providers, setProviders] = React.useState<Provider[]>([]);
  const [linkedin, setLinkedin] = React.useState<LinkedInStatusReal | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [corriendo, setCorriendo] = React.useState<string | null>(null);
  const [bloqueo, setBloqueo] = React.useState<{ paso: string; motivo: string } | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [confirmar, setConfirmar] = React.useState<Paso | null>(null);
  const [enriqueciendo, setEnriqueciendo] = React.useState(false);
  const [enrichMsg, setEnrichMsg] = React.useState<string | null>(null);
  const [climaLead, setClimaLead] = React.useState<LeadCurado | null>(null);
  const [clima, setClima] = React.useState<WeatherOut | null>(null);
  const [climaCargando, setClimaCargando] = React.useState(false);

  /* ── Territorio objetivo del Radar (estado/municipio/zona) ─────────── */
  const [targetInicial] = React.useState<RadarTarget>(leerTargetRadar);
  const geo = useGeoFiltros({
    entidad: targetInicial.entidad,
    municipio: targetInicial.municipio,
    colonia: targetInicial.colonia,
    cp: targetInicial.cp,
  });
  const [girosTxt, setGirosTxt] = React.useState(targetInicial.giros);
  const [validandoUbicacion, setValidandoUbicacion] = React.useState(false);
  const [ubicacionValidada, setUbicacionValidada] = React.useState<string | null>(null);

  const target: RadarTarget = React.useMemo(() => ({
    entidad: geo.sel.entidad,
    municipio: geo.sel.municipio,
    colonia: geo.sel.colonia,
    cp: geo.sel.cp,
    giros: girosTxt,
  }), [geo.sel, girosTxt]);

  // Persistencia local: al volver a Operación el territorio sigue elegido.
  React.useEffect(() => {
    try { localStorage.setItem(LS_RADAR_TARGET, JSON.stringify(target)); } catch { /* sin storage */ }
  }, [target]);

  const entidades = React.useMemo(() => {
    const set = new Set<string>([...ENTIDADES_MX, ...geo.opts.entidades]);
    return [...set].sort((a, b) => a.localeCompare(b, 'es'));
  }, [geo.opts.entidades]);

  const giros = React.useMemo(
    () => girosTxt.split(',').map((g) => g.trim()).filter(Boolean),
    [girosTxt],
  );
  const resumenUbicacion = textoUbicacion(target) || 'Corredores por defecto del workflow (Toluca y Querétaro)';
  const targetDefinido = Boolean(target.entidad || target.municipio || target.colonia || target.cp);

  const validarUbicacion = async () => {
    const texto = [target.colonia, target.municipio, target.entidad].filter(Boolean).join(', ');
    if (!texto) {
      toast.info('Elige al menos entidad, municipio o zona para validar.');
      return;
    }
    setValidandoUbicacion(true);
    setUbicacionValidada(null);
    try {
      const g = await geocode({ address: texto });
      setUbicacionValidada(g.label);
      // Completa lo que el geocodificador sí resolvió (sin pisar lo escrito).
      if (!geo.sel.entidad && g.entidad) geo.cambiar('entidad', g.entidad);
      if (!geo.sel.municipio && g.municipio) geo.cambiar('municipio', g.municipio);
      if (!geo.sel.colonia && g.colonia) geo.cambiar('colonia', g.colonia);
      if (!geo.sel.cp && g.cp) geo.cambiar('cp', g.cp);
      toast.success('Territorio localizado', { description: g.label });
    } catch (e) {
      toast.error('No se pudo validar el territorio', { description: errorMessage(e) });
    } finally {
      setValidandoUbicacion(false);
    }
  };

  const cargar = React.useCallback(async () => {
    try {
      const [rRuns, rWf, rProv, rLi, rCur] = await Promise.allSettled([
        getRuns(100),
        getWorkflows(),
        getProviders(),
        getLinkedInStatus(),
        get<{ items?: LeadCurado[] } | LeadCurado[]>('/leads/curados', { limit: 100 }),
      ]);
      if (rRuns.status === 'fulfilled') setRuns(runsComoArray(rRuns.value));
      else setError(errorMessage(rRuns.reason));
      if (rWf.status === 'fulfilled') {
        const w = rWf.value;
        setWorkflows(Array.isArray(w) ? w : (w.items ?? []));
      }
      if (rProv.status === 'fulfilled') setProviders(providersComoArray(rProv.value));
      if (rLi.status === 'fulfilled') setLinkedin(rLi.value);
      if (rCur.status === 'fulfilled') {
        const r = rCur.value;
        const arr = Array.isArray(r) ? r : (r.items ?? []);
        const conCoords = arr.filter((l) => l.lat != null && l.lon != null);
        conCoords.sort((a, b) => (b.score ?? 0) - (a.score ?? 0));
        setClimaLead(conCoords[0] ?? null);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => { cargar(); }, [cargar]);

  // Polling suave (inventario #94): cada 25 s si algo corre y la pestaña es visible.
  const hayRunning = runs.some((r) => r.estado === 'running');
  React.useEffect(() => {
    if (!hayRunning) return;
    const t = setInterval(() => { if (!document.hidden) cargar(); }, 25000);
    return () => clearInterval(t);
  }, [hayRunning, cargar]);

  const ultimoRun = React.useCallback(
    (pipeline: string) => runs.find((r) => r.pipeline === pipeline),
    [runs],
  );

  const workflowDe = (paso: Paso): WorkflowOut | undefined =>
    workflows.find((w) => w.id.includes(paso.id) || paso.id.includes(w.id) || w.id.startsWith(paso.id.slice(-2)));

  const ejecutar = async (paso: Paso) => {
    setCorriendo(paso.id);
    setBloqueo(null);
    try {
      // Las etapas Radar disparan el webhook real de n8n; radar-01 viaja
      // con el estado/municipio/zona y los giros elegidos. Las ETL solo
      // registran la corrida local (no tienen webhook).
      const cuerpo = paso.grupo === 'radar'
        ? {
            disparar: true,
            ...(paso.id === 'radar-01'
              ? {
                  target: {
                    entidad: target.entidad,
                    municipio: target.municipio,
                    colonia: target.colonia,
                    cp: target.cp,
                  },
                  giros,
                }
              : {}),
          }
        : undefined;
      await post(`/pipelines/run/${paso.id}`, cuerpo);
      toast.success(`Pipeline ${paso.id} lanzado`, {
        description: paso.grupo === 'radar'
          ? `El workflow de n8n quedó disparado · ${paso.id === 'radar-01' ? resumenUbicacion : 'revisa la bitácora para ver el avance'}`
          : 'La corrida quedó registrada en la bitácora.',
      });
      if (paso.id === 'radar-01' && !targetDefinido) {
        toast.info('Sin territorio elegido: se usan los corredores por defecto del workflow.');
      }
      await cargar();
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        // El backend devuelve detail={motivo, predecesor, ultimo_estado}
        const body = e.body as { detail?: { motivo?: string } } | null;
        const motivo = body?.detail?.motivo ?? e.message;
        setBloqueo({ paso: paso.id, motivo });
        toast.warning('Pipeline bloqueado por orden', { description: motivo });
      } else {
        toast.error('No se pudo lanzar el pipeline', { description: errorMessage(e) });
      }
    } finally {
      setCorriendo(null);
    }
  };

  const enriquecerGeo = async () => {
    setEnriqueciendo(true); setEnrichMsg(null);
    try {
      const r = await postEnrichGeo(500);
      const msg = `${r.actualizados} leads actualizados · ${r.pendientes} pendientes (con geometría: ${r.detalle.con_geometria} · solo CP: ${r.detalle.solo_cp} · sin datos: ${r.detalle.sin_datos}).`;
      setEnrichMsg(msg);
      toast.success('Geografía enriquecida', { description: msg });
    } catch (e) {
      toast.error('No se pudo enriquecer la geografía', { description: errorMessage(e) });
    } finally {
      setEnriqueciendo(false);
    }
  };

  const consultarClima = async () => {
    if (!climaLead || climaLead.lat == null || climaLead.lon == null) return;
    setClimaCargando(true);
    try {
      const w = await getWeather(climaLead.lat, climaLead.lon);
      setClima(w);
    } catch (e) {
      toast.error('No se pudo consultar el clima', { description: errorMessage(e) });
    } finally {
      setClimaCargando(false);
    }
  };

  const conectarLinkedIn = async () => {
    try {
      const r = await getLinkedInAuth();
      const url = r.auth_url ?? r.url;
      if (url) {
        window.open(url, '_blank', 'noopener');
        toast.info('Autoriza la app en LinkedIn y regresa aquí.');
      } else {
        toast.error('El backend no devolvió una URL de autorización.');
      }
    } catch (e) {
      toast.error('LinkedIn no está configurado', { description: errorMessage(e) });
    }
  };

  const liConectado = linkedin?.conectado ?? linkedin?.connected ?? false;

  return (
    <div className="flex h-full flex-col">
      <Topbar titulo="Operación" subtitulo="El motor del Radar: genera y procesa información, en orden" />
      <div className="flex-1 space-y-6 overflow-y-auto p-6">
        {error && <Alert variant="destructive"><AlertTitle>Error al cargar la bitácora</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>}
        {bloqueo && (
          <Alert variant="warning">
            <AlertTitle>⛔ {bloqueo.paso} bloqueado</AlertTitle>
            <AlertDescription>{bloqueo.motivo}</AlertDescription>
          </Alert>
        )}

        {/* ── Territorio objetivo del Radar ─────────────────────────── */}
        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <CardTitle>Territorio del Radar</CardTitle>
                <CardDescription>
                  Elige estado, municipio y zona (colonia/CP) antes de lanzar la etapa 01.
                  Estos datos viajan al workflow de n8n y definen dónde busca Google Maps.
                  Se guardan en este navegador para la próxima corrida.
                </CardDescription>
              </div>
              {targetDefinido && (
                <Badge variant="accent" className="max-w-full truncate" title={resumenUbicacion}>
                  📍 {resumenUbicacion}
                </Badge>
              )}
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Field label="Estado (entidad)" htmlFor="radar-entidad">
                <NativeSelect
                  id="radar-entidad"
                  className="w-full"
                  value={geo.sel.entidad}
                  onChange={(e) => { geo.cambiar('entidad', e.target.value); setUbicacionValidada(null); }}
                >
                  <option value="">Todo México / corredores por defecto</option>
                  {entidades.map((v) => <option key={v} value={v}>{v}</option>)}
                </NativeSelect>
              </Field>
              <Field label="Municipio / alcaldía" htmlFor="radar-municipio">
                <Input
                  id="radar-municipio"
                  list="radar-municipios"
                  placeholder="Ej. Querétaro"
                  value={geo.sel.municipio}
                  onChange={(e) => { geo.cambiar('municipio', e.target.value); setUbicacionValidada(null); }}
                />
                <datalist id="radar-municipios">
                  {geo.opts.municipios.map((v) => <option key={v} value={v} />)}
                </datalist>
              </Field>
              <Field label="Zona / colonia" htmlFor="radar-colonia">
                <Input
                  id="radar-colonia"
                  list="radar-colonias"
                  placeholder="Ej. Centro, Juriquilla…"
                  value={geo.sel.colonia}
                  onChange={(e) => { geo.cambiar('colonia', e.target.value); setUbicacionValidada(null); }}
                />
                <datalist id="radar-colonias">
                  {geo.opts.colonias.map((v) => <option key={v} value={v} />)}
                </datalist>
              </Field>
              <Field label="CP (opcional)" htmlFor="radar-cp">
                <Input
                  id="radar-cp"
                  placeholder="Ej. 76000"
                  value={geo.sel.cp}
                  onChange={(e) => { geo.cambiar('cp', e.target.value); setUbicacionValidada(null); }}
                />
              </Field>
            </div>
            <Field label="Giros a buscar (separados por coma)" htmlFor="radar-giros">
              <Input
                id="radar-giros"
                placeholder="bodegas, centros logísticos, plantas industriales"
                value={girosTxt}
                onChange={(e) => setGirosTxt(e.target.value)}
              />
            </Field>
            <div className="flex flex-wrap items-center gap-2">
              <Button type="button" variant="outline" size="sm" onClick={validarUbicacion} disabled={validandoUbicacion || !targetDefinido}>
                {validandoUbicacion && <Spinner size={14} />} Validar ubicación
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => { geo.limpiar(); setGirosTxt(''); setUbicacionValidada(null); }}
              >
                Limpiar territorio
              </Button>
              <p className="text-xs text-muted-foreground">
                {targetDefinido
                  ? `Se buscará en: ${resumenUbicacion || 'la zona elegida'} · ${giros.length ? giros.join(' · ') : 'giros por defecto del workflow'}.`
                  : 'Sin territorio: la etapa 01 usa los corredores por defecto (Toluca y Querétaro).'}
              </p>
            </div>
            {ubicacionValidada && (
              <Alert variant="info">
                <AlertDescription>Geocodificación válida: <strong>{ubicacionValidada}</strong>. Puedes ajustar municipio/zona antes de lanzar la etapa.</AlertDescription>
              </Alert>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Pipeline de ejecución</CardTitle>
                <CardDescription>
                  Pulsa ▶ para lanzar un paso (pide confirmación). Las etapas Radar corren en orden: 02 requiere 01 en OK; 03 y 04 requieren 02 en OK (regla R10). Si la previa no está en OK, el botón se deshabilita con el motivo 🔒.
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
                  const motivo = motivoBloqueo(p, ultimoRun);
                  const wf = workflowDe(p);
                  return (
                    <React.Fragment key={p.id}>
                      <div className="flex w-56 shrink-0 flex-col rounded-lg border bg-card p-4 shadow-sm">
                        <div className="mb-2 flex items-center justify-between gap-2">
                          <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{wf?.nombre ?? p.titulo}</span>
                          {runBadge(run?.estado)}
                        </div>
                        <p className="mb-2 text-xs leading-snug text-muted-foreground">{wf?.descripcion ?? p.descripcion}</p>
                        <p className="mb-2">
                          <Badge variant="outline" className="font-mono text-[10px]">🕐 {p.cron}</Badge>
                        </p>
                        <p className="mb-1 text-[11px] font-medium">{textoUltima(run)}</p>
                        {run?.estado === 'error' && (
                          <p className="mb-2 text-[11px] font-medium text-destructive">{detalleRunTexto(run.detalle)}</p>
                        )}
                        <div className="mt-auto">
                          <Button
                            size="sm"
                            className="w-full"
                            variant={p.grupo === 'radar' ? 'default' : 'secondary'}
                            disabled={enCurso || !!motivo}
                            onClick={() => setConfirmar(p)}
                            title={motivo ?? `Lanzar ${p.id}`}
                          >
                            {enCurso ? <Spinner size={14} /> : '▶'} Ejecutar etapa {p.id.replace('radar-', '').replace('etl-', 'ETL ')}
                          </Button>
                          {motivo && <p className="mt-2 text-[11px] text-warning">🔒 {motivo}</p>}
                          {bloqueo?.paso === p.id && (
                            <p className="mt-2 text-[11px] text-warning">⛔ {bloqueo.motivo}</p>
                          )}
                          {p.id === 'radar-02' && (
                            <div className="mt-3 border-t pt-3">
                              <Button size="sm" variant="secondary" className="w-full" onClick={enriquecerGeo} disabled={enriqueciendo}
                                title="Deriva entidad/municipio/colonia/CP/SCIAN de los leads (POST /leads/enrich-geo, idempotente)">
                                {enriqueciendo ? 'Enriqueciendo…' : '🌎 Enriquecer geografía'}
                              </Button>
                              {enrichMsg && <p className="mt-2 text-[11px] font-medium text-primary">{enrichMsg}</p>}
                            </div>
                          )}
                        </div>
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

        <div className="grid gap-4 lg:grid-cols-3">
          <Card>
            <CardHeader>
              <CardTitle>Providers</CardTitle>
              <CardDescription>Modo actual de cada capacidad (local $0 / nube). Se gestionan en Sistema.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              {providers.length === 0 ? (
                <p className="text-sm text-muted-foreground">Sin providers reportados por la API.</p>
              ) : (
                <>
                  <ul className="space-y-1.5 text-sm">
                    {providers.map((p) => (
                      <li key={p.name} className="flex items-center gap-2">
                        <span className="font-mono text-xs font-semibold">{p.name}</span>
                        <span className="text-xs text-muted-foreground">{p.provider}</span>
                        <Badge variant={p.mode === 'cloud' ? 'default' : p.mode === 'local' ? 'secondary' : 'outline'} className="ml-auto">{p.mode}</Badge>
                      </li>
                    ))}
                  </ul>
                  <Button size="sm" variant="outline" onClick={() => navigate('/sistema')}>Gestionar en Sistema</Button>
                </>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>LinkedIn · página de empresa</CardTitle>
              <CardDescription>Fuente de las señales cálidas de la etapa 05.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <div className="flex items-center gap-2">
                <span className="inline-block h-3 w-3 rounded-full" style={{ backgroundColor: liConectado ? '#2F9E44' : '#8a93a6' }} aria-hidden />
                <span className="font-medium">{liConectado ? 'Conectado' : 'No conectado'}</span>
                {linkedinExpirado(linkedin) && <Badge variant="warning">Token expirado — reconecta</Badge>}
              </div>
              {linkedin?.nota && <p className="text-xs text-muted-foreground">{linkedin.nota}</p>}
              <p className="text-[11px] text-muted-foreground">
                Alcance honesto: la API de LinkedIn no permite buscar prospectos; aquí se monitorean las señales de tu propia página.
              </p>
              <div className="flex gap-2">
                {!liConectado && <Button size="sm" onClick={conectarLinkedIn}>Conectar LinkedIn</Button>}
                <Button size="sm" variant="outline" onClick={() => navigate('/sistema')}>Ver en Sistema</Button>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Clima de la zona</CardTitle>
              <CardDescription>Open-Meteo vía <code>GET /geo/weather</code> (caché 6 h). Alimenta el bonus por calor de la etapa 02.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              {!climaLead ? (
                <p className="text-muted-foreground">Sin leads con coordenadas todavía: corre la etapa 01 para poblar el Radar.</p>
              ) : (
                <>
                  <p className="font-medium">{climaLead.nombre}</p>
                  <p className="text-xs text-muted-foreground">
                    Lead con mayor score · temp. de zona registrada: {climaLead.temp_zona != null ? `${climaLead.temp_zona} °C` : 'sin procesar por la 02'}
                  </p>
                  {clima && (
                    <p className="font-mono text-lg font-bold">
                      {clima.temperature_c != null ? `${clima.temperature_c} °C` : '—'}
                      {clima.cached && <span className="ml-2 text-xs font-normal text-muted-foreground">(caché)</span>}
                    </p>
                  )}
                  <Button size="sm" variant="outline" onClick={consultarClima} disabled={climaCargando}>
                    {climaCargando ? 'Consultando…' : 'Consultar clima actual'}
                  </Button>
                </>
              )}
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Bitácora de corridas</CardTitle>
            <CardDescription>Últimas ejecuciones de todos los pipelines (Radar + ETL). Las filas en error se pintan en rojo.</CardDescription>
          </CardHeader>
          <CardContent>
            {runs.length === 0 ? (
              <p className="text-sm text-muted-foreground">Sin ejecuciones aún. Corre la etapa 01 para empezar.</p>
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
                      <tr key={r.run_id} className={cn('border-b last:border-0', r.estado === 'error' && 'bg-destructive/5 text-destructive')}>
                        <td className="py-2 pr-4 font-mono text-xs">{r.pipeline}</td>
                        <td className="py-2 pr-4">{runBadge(r.estado)}</td>
                        <td className="py-2 pr-4 font-mono text-xs">{r.started_at ? new Date(r.started_at).toLocaleString('es-MX') : '—'}</td>
                        <td className="py-2 pr-4 font-mono text-xs">{r.finished_at ? new Date(r.finished_at).toLocaleString('es-MX') : '—'}</td>
                        <td className={cn('py-2 text-xs', r.estado === 'error' ? 'font-medium' : 'text-muted-foreground')}>{detalleRunTexto(r.detalle)}</td>
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

      <Dialog open={!!confirmar} onOpenChange={(o) => { if (!o) setConfirmar(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>¿Ejecutar {confirmar?.id}?</DialogTitle>
            <DialogDescription>
              {confirmar?.titulo} — {confirmar?.descripcion} Puede tardar varios minutos (el scraper visita Google Maps).
            </DialogDescription>
            {confirmar?.id === 'radar-01' && (
              <div className="rounded-md border bg-muted/40 p-3 text-xs">
                <p><strong>Territorio:</strong> {resumenUbicacion}</p>
                <p><strong>Giros:</strong> {giros.length ? giros.join(' · ') : 'por defecto del workflow (bodegas, centros logísticos, plantas industriales)'}</p>
                <p className="mt-1 text-muted-foreground">Si n8n no tiene el webhook activo, verás el motivo y no se creará una corrida falsa.</p>
              </div>
            )}
            {confirmar?.grupo === 'radar' && confirmar?.id !== 'radar-01' && (
              <p className="text-xs text-muted-foreground">Esta etapa se dispara en n8n y requiere que la etapa previa esté en OK.</p>
            )}
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmar(null)}>Cancelar</Button>
            <Button
              onClick={() => { const p = confirmar; setConfirmar(null); if (p) ejecutar(p); }}
              disabled={!confirmar || corriendo === confirmar?.id}
            >
              ▶ Ejecutar etapa
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

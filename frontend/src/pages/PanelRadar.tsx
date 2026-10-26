import * as React from 'react';
import { useNavigate } from 'react-router-dom';
import { Topbar } from '@/components/layout/Topbar';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/Alert';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Skeleton } from '@/components/ui/Skeleton';
import { Chart } from '@/components/ui/Chart';
import {
  get, getLeadsCount, errorMessage,
  ETAPAS_RADAR, lineaColor,
  type LeadCurado, type PipelineRun,
} from '@/lib/api';
import {
  getRuns, runsComoArray, detalleRunTexto,
  getLinkedInStatus, linkedinExpirado, type LinkedInStatusReal,
} from '@/lib/apiGeo';

const LINEAS = [
  { id: 'koolkat', label: 'Koolkat' },
  { id: 'solar', label: 'Solar' },
  { id: 'evaporativa', label: 'Evaporativa' },
] as const;

const BUCKETS = [
  { label: '0–20', min: 0, max: 20 },
  { label: '21–40', min: 21, max: 40 },
  { label: '41–60', min: 41, max: 60 },
  { label: '61–80', min: 61, max: 80 },
  { label: '81–100', min: 81, max: 100 },
];

function diaClave(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

export default function PanelRadar() {
  const navigate = useNavigate();
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [total, setTotal] = React.useState<number | null>(null);
  const [porEtapa, setPorEtapa] = React.useState<Record<string, number>>({});
  const [porLinea, setPorLinea] = React.useState<Record<string, number>>({});
  const [muestra, setMuestra] = React.useState<LeadCurado[]>([]);
  const [runs, setRuns] = React.useState<PipelineRun[]>([]);
  const [linkedin, setLinkedin] = React.useState<LinkedInStatusReal | null>(null);

  const cargar = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [cTotal, etapas, lineas, rMuestra, rRuns, rLi] = await Promise.allSettled([
        getLeadsCount(),
        Promise.all(ETAPAS_RADAR.map((e) => getLeadsCount({ etapa: e.id }))),
        Promise.all(LINEAS.map((l) => getLeadsCount({ linea: l.id }))),
        get<{ items?: LeadCurado[] } | LeadCurado[]>('/leads/curados', { limit: 100 }),
        getRuns(200),
        getLinkedInStatus(),
      ]);
      if (cTotal.status === 'fulfilled') setTotal(cTotal.value.total);
      if (etapas.status === 'fulfilled') {
        const m: Record<string, number> = {};
        ETAPAS_RADAR.forEach((e, i) => { m[e.id] = etapas.value[i]?.total ?? 0; });
        setPorEtapa(m);
      }
      if (lineas.status === 'fulfilled') {
        const m: Record<string, number> = {};
        LINEAS.forEach((l, i) => { m[l.id] = lineas.value[i]?.total ?? 0; });
        setPorLinea(m);
      }
      if (rMuestra.status === 'fulfilled') {
        const r = rMuestra.value;
        setMuestra(Array.isArray(r) ? r : (r.items ?? []));
      }
      if (rRuns.status === 'fulfilled') setRuns(runsComoArray(rRuns.value));
      if (rLi.status === 'fulfilled') setLinkedin(rLi.value);
      if (cTotal.status === 'rejected' && rMuestra.status === 'rejected') {
        setError(errorMessage(cTotal.reason));
      }
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => { cargar(); }, [cargar]);

  const kpis = React.useMemo(() => {
    const scores = muestra.map((l) => l.score ?? 0).filter((v) => v > 0);
    const scoreProm = scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : 0;
    return {
      total: total ?? muestra.length,
      nuevos: porEtapa['nuevo'] ?? 0,
      scoreProm,
      oportunidades: (porEtapa['reunion'] ?? 0) + (porEtapa['propuesta'] ?? 0),
      ganados: porEtapa['ganado'] ?? 0,
      perdidos: porEtapa['perdido'] ?? 0,
      sobreMuestra: (total ?? 0) > muestra.length,
    };
  }, [total, porEtapa, muestra]);

  const lineasEnCero = LINEAS.filter((l) => (porLinea[l.id] ?? 0) === 0 && (total ?? 0) > 0);

  const erroresSemana = React.useMemo(() => {
    const desde = Date.now() - 7 * 24 * 3600 * 1000;
    const errs = runs.filter(
      (r) => r.estado === 'error' && r.started_at && new Date(r.started_at).getTime() >= desde,
    );
    return { n: errs.length, reciente: errs[0] };
  }, [runs]);

  const actividad = React.useMemo(() => {
    const dias: { clave: string; etiqueta: string; ok: number; error: number }[] = [];
    for (let i = 13; i >= 0; i--) {
      const d = new Date();
      d.setDate(d.getDate() - i);
      dias.push({
        clave: diaClave(d),
        etiqueta: d.toLocaleDateString('es-MX', { day: '2-digit', month: 'short' }),
        ok: 0, error: 0,
      });
    }
    const idx = new Map(dias.map((d, i) => [d.clave, i]));
    for (const r of runs) {
      if (!r.started_at) continue;
      const i = idx.get(diaClave(new Date(r.started_at)));
      if (i === undefined) continue;
      if (r.estado === 'ok') dias[i].ok += 1;
      if (r.estado === 'error') dias[i].error += 1;
    }
    return dias;
  }, [runs]);

  const buckets = React.useMemo(
    () => BUCKETS.map((b) => ({
      label: b.label,
      value: muestra.filter((l) => (l.score ?? 0) >= b.min && (l.score ?? 0) <= b.max).length,
    })),
    [muestra],
  );

  const funnel = ETAPAS_RADAR
    .filter((e) => e.id !== 'perdido')
    .map((e) => ({ name: e.label, value: porEtapa[e.id] ?? 0 }));

  const dona = LINEAS.map((l) => ({
    name: l.label,
    value: porLinea[l.id] ?? 0,
    itemStyle: { color: lineaColor(l.id) },
  }));

  return (
    <div className="flex h-full flex-col">
      <Topbar titulo="Panel Radar" subtitulo="Vista ejecutiva: cómo van tus leads hoy" />
      <div className="flex-1 space-y-6 overflow-y-auto p-6">
        {error && (
          <Alert variant="destructive">
            <AlertTitle>Error al cargar el panel</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {loading ? (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-28" />)}
          </div>
        ) : (
          <>
            {/* ── Alertas accionables (§4.1) ─────────────────────────── */}
            <div className="space-y-3">
              {(total ?? 0) === 0 && (
                <Alert variant="info">
                  <AlertTitle>Sin leads aún</AlertTitle>
                  <AlertDescription className="flex flex-wrap items-center gap-3">
                    <span>El Radar todavía no generó prospectos. Corre la etapa 01 desde Operación.</span>
                    <Button size="sm" onClick={() => navigate('/operacion')}>Ir a Operación</Button>
                  </AlertDescription>
                </Alert>
              )}
              {lineasEnCero.length > 0 && (
                <Alert variant="warning">
                  <AlertTitle>Sin leads para: {lineasEnCero.map((l) => l.label).join(', ')}</AlertTitle>
                  <AlertDescription className="flex flex-wrap items-center gap-3">
                    <span>Alguna línea quedó en 0 (cobertura incompleta). Corre la 01/02 o revisa la regla de línea por mes.</span>
                    <Button size="sm" variant="outline" onClick={() => navigate('/operacion')}>Ir a Operación</Button>
                  </AlertDescription>
                </Alert>
              )}
              {erroresSemana.n > 0 && (
                <Alert variant="destructive">
                  <AlertTitle>{erroresSemana.n} {erroresSemana.n === 1 ? 'error' : 'errores'} esta semana</AlertTitle>
                  <AlertDescription className="flex flex-wrap items-center gap-3">
                    <span>
                      Más reciente: {erroresSemana.reciente?.pipeline}
                      {erroresSemana.reciente ? ` — ${detalleRunTexto(erroresSemana.reciente.detalle)}` : ''}
                    </span>
                    <Button size="sm" variant="outline" onClick={() => navigate('/sistema')}>Ver en Sistema</Button>
                  </AlertDescription>
                </Alert>
              )}
              {linkedinExpirado(linkedin) && (
                <Alert variant="warning">
                  <AlertTitle>Token de LinkedIn expirado</AlertTitle>
                  <AlertDescription className="flex flex-wrap items-center gap-3">
                    <span>La etapa 05 no podrá leer las señales de tu página hasta reconectar.</span>
                    <Button size="sm" variant="outline" onClick={() => navigate('/sistema')}>Ver en Sistema</Button>
                  </AlertDescription>
                </Alert>
              )}
            </div>

            {/* ── 4 KPIs (§4.1) ──────────────────────────────────────── */}
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
              <Card>
                <CardHeader className="pb-2">
                  <CardDescription className="text-xs font-semibold uppercase tracking-wider">Leads totales</CardDescription>
                  <p className="font-mono text-3xl font-bold">{kpis.total}</p>
                </CardHeader>
                <CardContent><p className="text-[11px] text-muted-foreground">{kpis.nuevos} nuevos por trabajar</p></CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardDescription className="text-xs font-semibold uppercase tracking-wider">Score promedio</CardDescription>
                  <p className="font-mono text-3xl font-bold">{kpis.scoreProm.toFixed(0)}</p>
                </CardHeader>
                <CardContent>
                  <p className="text-[11px] text-muted-foreground">
                    de 100{kpis.sobreMuestra ? ` · sobre los primeros ${muestra.length} leads` : ''}
                  </p>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardDescription className="text-xs font-semibold uppercase tracking-wider">Oportunidades</CardDescription>
                  <p className="font-mono text-3xl font-bold">{kpis.oportunidades}</p>
                </CardHeader>
                <CardContent><p className="text-[11px] text-muted-foreground">Reunión + propuesta en curso</p></CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardDescription className="text-xs font-semibold uppercase tracking-wider">Ganados</CardDescription>
                  <p className="font-mono text-3xl font-bold">{kpis.ganados}</p>
                </CardHeader>
                <CardContent><p className="text-[11px] text-muted-foreground">{kpis.perdidos} perdidos</p></CardContent>
              </Card>
            </div>

            {/* ── 4 gráficas (§4.1) ──────────────────────────────────── */}
            <div className="grid gap-4 lg:grid-cols-2">
              <Card>
                <CardHeader><CardTitle>Embudo de conversión</CardTitle></CardHeader>
                <CardContent>
                  <Chart
                    height={300}
                    option={{
                      tooltip: { trigger: 'item', formatter: '{b}: {c}' },
                      series: [{
                        type: 'funnel', left: '10%', width: '80%',
                        label: { formatter: '{b}: {c}' },
                        data: funnel,
                      }],
                    }}
                  />
                </CardContent>
              </Card>
              <Card>
                <CardHeader><CardTitle>Leads por línea recomendada</CardTitle></CardHeader>
                <CardContent>
                  <Chart
                    height={300}
                    option={{
                      tooltip: { trigger: 'item' },
                      legend: { bottom: 0 },
                      series: [{
                        type: 'pie', radius: ['45%', '70%'],
                        data: dona,
                        label: { formatter: '{b}: {c} ({d}%)' },
                      }],
                    }}
                  />
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle>Distribución de score</CardTitle>
                  {kpis.sobreMuestra && (
                    <CardDescription>Sobre los primeros {muestra.length} leads cargados.</CardDescription>
                  )}
                </CardHeader>
                <CardContent>
                  <Chart
                    height={300}
                    option={{
                      tooltip: { trigger: 'axis' },
                      grid: { left: 8, right: 16, top: 24, bottom: 8, containLabel: true },
                      xAxis: { type: 'category', data: buckets.map((b) => b.label) },
                      yAxis: { type: 'value' },
                      series: [{ type: 'bar', data: buckets.map((b) => b.value), itemStyle: { color: '#0E5FD8' } }],
                    }}
                  />
                </CardContent>
              </Card>
              <Card>
                <CardHeader><CardTitle>Actividad · últimos 14 días</CardTitle></CardHeader>
                <CardContent>
                  <Chart
                    height={300}
                    option={{
                      tooltip: { trigger: 'axis' },
                      legend: { bottom: 0 },
                      grid: { left: 8, right: 16, top: 24, bottom: 32, containLabel: true },
                      xAxis: { type: 'category', data: actividad.map((d) => d.etiqueta) },
                      yAxis: { type: 'value', minInterval: 1 },
                      series: [
                        { name: 'Corridas OK', type: 'line', smooth: true, data: actividad.map((d) => d.ok), itemStyle: { color: '#2F9E44' } },
                        { name: 'Corridas con error', type: 'line', smooth: true, data: actividad.map((d) => d.error), itemStyle: { color: '#D64545' } },
                      ],
                    }}
                  />
                </CardContent>
              </Card>
            </div>

            {/* ── ¿Cómo funciona el Radar? (§4.1) ────────────────────── */}
            <Card>
              <CardHeader><CardTitle>¿Cómo funciona el Radar?</CardTitle></CardHeader>
              <CardContent>
                <div className="grid gap-4 md:grid-cols-3">
                  {[
                    { n: '1', t: 'Operación genera', d: 'Las etapas 01→05 capturan negocios en Google Maps, los deduplican, les ponen score y línea, y procesan señales.' },
                    { n: '2', t: 'Leads se trabaja', d: 'En la lista de Leads contactas (llamada/WhatsApp), mueves cada lead por las 6 etapas y registras notas y señales.' },
                    { n: '3', t: 'Panel muestra el resultado', d: 'Este panel resume el embudo, las líneas y la actividad para decidir dónde poner el esfuerzo comercial.' },
                  ].map((p) => (
                    <div key={p.n} className="flex gap-3">
                      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10 font-mono text-sm font-bold text-primary">{p.n}</span>
                      <div>
                        <p className="text-sm font-semibold">{p.t}</p>
                        <p className="text-xs leading-relaxed text-muted-foreground">{p.d}</p>
                      </div>
                    </div>
                  ))}
                </div>
                <div className="mt-4 flex items-center gap-2">
                  <Badge variant="secondary">El Radar propone, tú decides</Badge>
                  <span className="text-[11px] text-muted-foreground">El sistema nunca contacta clientes solo.</span>
                </div>
              </CardContent>
            </Card>
          </>
        )}
      </div>
    </div>
  );
}

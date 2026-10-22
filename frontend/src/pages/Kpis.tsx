import * as React from 'react';
import { useNavigate } from 'react-router-dom';
import { Topbar } from '@/components/layout/Topbar';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/Alert';
import { Skeleton } from '@/components/ui/Skeleton';
import { Empty } from '@/components/ui/Empty';
import { Chart } from '@/components/ui/Chart';
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from '@/components/ui/Tooltip';
import { get, errorMessage, type Lead, type LeadCurado, ETAPAS_RADAR, lineaColor } from '@/lib/api';
import { estratoColor } from '@/lib/geo';
import { useGeisStore } from '@/store';

interface KpiCardData {
  titulo: string;
  valor: string;
  delta?: string;
  deltaDir?: 'up' | 'down' | 'flat';
  fuente: string;
  formula?: string;
}

export default function Kpis() {
  const navigate = useNavigate();
  const [leads, setLeads] = React.useState<Lead[]>([]);
  const [curados, setCurados] = React.useState<LeadCurado[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const territorio = useGeisStore((s) => s.territorio);

  React.useEffect(() => {
    let vivo = true;
    get<{ items?: Lead[]; data?: Lead[] } | Lead[]>('/leads', { limit: 100 })
      .then((r) => {
        if (!vivo) return;
        setLeads(Array.isArray(r) ? r : (r.items ?? r.data ?? []));
      })
      .catch((e) => vivo && setError(errorMessage(e)));
    get<{ items?: LeadCurado[] } | LeadCurado[]>('/leads/curados', { limit: 100 })
      .then((r) => {
        if (!vivo) return;
        setCurados(Array.isArray(r) ? r : (r.items ?? []));
      })
      .catch(() => { /* radar opcional: la página base no depende de él */ })
      .finally(() => vivo && setLoading(false));
    return () => { vivo = false; };
  }, []);

  const cards = React.useMemo<KpiCardData[]>(() => {
    const idts = leads.map((l) => l.idt ?? 0).filter((v) => v > 0);
    const scores = leads.map((l) => l.score ?? 0).filter((v) => v > 0);
    const prom = (a: number[]) => (a.length ? a.reduce((x, y) => x + y, 0) / a.length : 0);
    return [
      { titulo: 'Plantas elegibles', valor: String(leads.length), fuente: 'DENUE · edición vigente', formula: 'Conteo de establecimientos con estrato e IDT válidos en el territorio' },
      { titulo: 'IDT promedio', valor: `${prom(idts).toFixed(0)}/100`, fuente: 'Modelo IDT v1', formula: 'Promedio del Índice de Demanda Térmica (§3.4 del SRS)' },
      { titulo: 'Score promedio de cuenta', valor: `${prom(scores).toFixed(0)}/100`, fuente: 'Modelo de scoring', formula: 'Promedio ponderado de los 5 componentes del score' },
      { titulo: 'Densidad de competencia', valor: `${leads.filter((l) => (l.idt ?? 0) < 40).length} compet.`, fuente: 'DENUE', formula: 'Establecimientos del mismo giro en el territorio' },
    ];
  }, [leads]);

  const estratos = React.useMemo(() => {
    const m = new Map<string, number>();
    for (const l of leads) m.set(l.estrato ?? 'Sin estrato', (m.get(l.estrato ?? 'Sin estrato') ?? 0) + 1);
    return [...m.entries()].map(([name, value]) => ({ name, value, itemStyle: { color: estratoColor(name) } }));
  }, [leads]);

  const topScian = React.useMemo(() => {
    const m = new Map<string, number>();
    for (const l of leads) {
      const k = l.scian_code ? `${l.scian_code} ${(l.scian_desc ?? '').slice(0, 24)}` : 'Sin SCIAN';
      m.set(k, (m.get(k) ?? 0) + 1);
    }
    const top = [...m.entries()].sort((a, b) => b[1] - a[1]).slice(0, 10);
    return { labels: top.map(([k]) => k), values: top.map(([, v]) => v) };
  }, [leads]);

  /* ----- Módulo Radar: KPIs, funnel por etapa y dona por línea ----- */
  const radar = React.useMemo(() => {
    const porEtapa = (e: string) => curados.filter((l) => (l.etapa ?? 'nuevo') === e).length;
    return {
      nuevos: porEtapa('nuevo'),
      contactados: porEtapa('contactado'),
      reuniones: porEtapa('reunion'),
      funnel: ETAPAS_RADAR.map((e) => ({ name: e.label, value: porEtapa(e.id) })),
      dona: ['koolkat', 'solar', 'evaporativa'].map((linea) => ({
        name: { koolkat: 'Koolkat', solar: 'Solar', evaporativa: 'Evaporativa' }[linea],
        value: curados.filter((l) => (l.linea_recomendada ?? '').toLowerCase() === linea).length,
        itemStyle: { color: lineaColor(linea) },
      })),
    };
  }, [curados]);

  return (
    <div className="flex h-full flex-col">
      <Topbar
        titulo="Panel de KPIs"
        subtitulo={territorio ? `Territorio: ${territorio.nombre}` : 'Inteligencia comercial del territorio activo'}
      />
      <div className="flex-1 space-y-6 overflow-y-auto p-6">
        {error && <Alert variant="destructive"><AlertTitle>Error al cargar</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>}

        {loading ? (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-32" />)}
          </div>
        ) : leads.length === 0 ? (
          <Empty
            title="Sin datos para el territorio"
            description="No hay establecimientos cargados. Dibuja un polígono en el Mapa o ajusta los filtros del territorio activo."
            icon="📊"
            action={{ label: 'Ir al mapa', onClick: () => navigate('/mapa') }}
          />
        ) : (
          <>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
              {cards.map((c) => (
                <TooltipProvider key={c.titulo}>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Card className="cursor-default">
                        <CardHeader className="pb-2">
                          <CardDescription className="text-xs font-semibold uppercase tracking-wider">{c.titulo}</CardDescription>
                          <p className="font-mono text-3xl font-bold">{c.valor}</p>
                        </CardHeader>
                        <CardContent>
                          {c.delta && (
                            <Badge variant={c.deltaDir === 'up' ? 'success' : c.deltaDir === 'down' ? 'destructive' : 'secondary'}>
                              {c.deltaDir === 'up' ? '▲' : c.deltaDir === 'down' ? '▼' : '━'} {c.delta}
                            </Badge>
                          )}
                          <p className="mt-2 text-[11px] text-muted-foreground">Pasa el cursor para ver fórmula y fuente</p>
                        </CardContent>
                      </Card>
                    </TooltipTrigger>
                    <TooltipContent className="max-w-xs">
                      <p className="font-semibold">{c.titulo}</p>
                      {c.formula && <p className="mt-1">{c.formula}</p>}
                      <p className="mt-1 text-primary-foreground/80">Fuente: {c.fuente}</p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              ))}
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              <Card>
                <CardHeader><CardTitle>Distribución por estrato</CardTitle></CardHeader>
                <CardContent>
                  <Chart
                    height={300}
                    option={{
                      tooltip: { trigger: 'item' },
                      legend: { bottom: 0, type: 'scroll' },
                      series: [{ type: 'pie', radius: ['45%', '70%'], data: estratos, label: { formatter: '{b}: {c}' } }],
                    }}
                  />
                </CardContent>
              </Card>
              <Card>
                <CardHeader><CardTitle>Top 10 clases SCIAN</CardTitle></CardHeader>
                <CardContent>
                  <Chart
                    height={300}
                    option={{
                      tooltip: { trigger: 'axis' },
                      grid: { left: 8, right: 16, top: 8, bottom: 8, containLabel: true },
                      xAxis: { type: 'value' },
                      yAxis: { type: 'category', data: [...topScian.labels].reverse(), axisLabel: { fontSize: 11 } },
                      series: [{ type: 'bar', data: [...topScian.values].reverse(), itemStyle: { color: '#0E5FD8' } }],
                    }}
                  />
                </CardContent>
              </Card>
            </div>

            {/* Módulo Radar: pipeline comercial */}
            {curados.length > 0 && (
              <>
                <div>
                  <h2 className="text-lg font-semibold tracking-tight">Módulo Radar · pipeline comercial</h2>
                  <p className="text-xs text-muted-foreground">Leads curados por el scraper y el scoring conductual (<code>GET /leads/curados</code>).</p>
                </div>
                <div className="grid gap-4 md:grid-cols-3">
                  <Card>
                    <CardHeader className="pb-2"><CardDescription className="text-xs font-semibold uppercase tracking-wider">Leads nuevos</CardDescription><p className="font-mono text-3xl font-bold">{radar.nuevos}</p></CardHeader>
                    <CardContent><p className="text-[11px] text-muted-foreground">Etapa «nuevo» · pendientes de primer contacto</p></CardContent>
                  </Card>
                  <Card>
                    <CardHeader className="pb-2"><CardDescription className="text-xs font-semibold uppercase tracking-wider">Contactados</CardDescription><p className="font-mono text-3xl font-bold">{radar.contactados}</p></CardHeader>
                    <CardContent><p className="text-[11px] text-muted-foreground">Etapa «contactado» · ya hubo primer contacto</p></CardContent>
                  </Card>
                  <Card>
                    <CardHeader className="pb-2"><CardDescription className="text-xs font-semibold uppercase tracking-wider">Reuniones</CardDescription><p className="font-mono text-3xl font-bold">{radar.reuniones}</p></CardHeader>
                    <CardContent><p className="text-[11px] text-muted-foreground">Etapa «reunión» · visita o llamada agendada</p></CardContent>
                  </Card>
                </div>
                <div className="grid gap-4 lg:grid-cols-2">
                  <Card>
                    <CardHeader><CardTitle>Funnel por etapa</CardTitle></CardHeader>
                    <CardContent>
                      <Chart
                        height={320}
                        option={{
                          tooltip: { trigger: 'item', formatter: '{b}: {c}' },
                          series: [{
                            type: 'funnel',
                            left: '10%', width: '80%',
                            label: { formatter: '{b}: {c}' },
                            data: radar.funnel,
                          }],
                        }}
                      />
                    </CardContent>
                  </Card>
                  <Card>
                    <CardHeader><CardTitle>Línea recomendada</CardTitle></CardHeader>
                    <CardContent>
                      <Chart
                        height={320}
                        option={{
                          tooltip: { trigger: 'item' },
                          legend: { bottom: 0 },
                          series: [{ type: 'pie', radius: ['45%', '70%'], data: radar.dona, label: { formatter: '{b}: {c}' } }],
                        }}
                      />
                    </CardContent>
                  </Card>
                </div>
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}

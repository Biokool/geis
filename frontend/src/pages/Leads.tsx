import * as React from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import type { ColumnDef } from '@tanstack/react-table';
import { Topbar } from '@/components/layout/Topbar';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/Alert';
import { Skeleton } from '@/components/ui/Skeleton';
import { Badge } from '@/components/ui/Badge';
import { Button, buttonVariants } from '@/components/ui/Button';
import { DataTable } from '@/components/ui/DataTable';
import { Drawer } from '@/components/ui/Drawer';
import { Textarea } from '@/components/ui/Textarea';
import { Input } from '@/components/ui/Input';
import { Field } from '@/components/ui/Field';
import { Separator } from '@/components/ui/Separator';
import { Progress } from '@/components/ui/Progress';
import { Slider } from '@/components/ui/Slider';
import { NativeSelect } from '@/components/ui/NativeSelect';
import { Empty } from '@/components/ui/Empty';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/Dialog';
import {
  get, patch, errorMessage,
  desdeEspacial, desdeRadar,
  type Lead, type LeadCurado, type LeadUnificado,
  ETAPAS_RADAR, lineaColor,
} from '@/lib/api';
import {
  useGeoFiltros, postEnrichGeo, getLeadsCountGeo, postSignal,
  whyLinea, normPhone, normWeb,
} from '@/lib/apiGeo';
import { estratoColor } from '@/lib/geo';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

const ETAPA_BADGE: Record<string, 'default' | 'secondary' | 'outline' | 'accent' | 'success' | 'destructive'> = {
  nuevo: 'secondary', contactado: 'outline', reunion: 'accent', propuesta: 'default', ganado: 'success', perdido: 'destructive',
};

/** Lead unificado + geografía derivada (migración 0005) que expone /leads/curados. */
type LeadGeo = LeadUnificado & {
  entidad?: string | null;
  colonia?: string | null;
  cp?: string | null;
  scian?: string | null;
};

function conGeo(l: LeadCurado): LeadGeo {
  const g = l as LeadCurado & {
    entidad?: string | null; municipio?: string | null;
    colonia?: string | null; cp?: string | null; scian?: string | null;
  };
  return {
    ...desdeRadar(l),
    municipio: g.municipio ?? undefined,
    entidad: g.entidad, colonia: g.colonia, cp: g.cp, scian: g.scian,
  };
}

const TIPOS_SENAL = ['hallazgo', 'ampliación', 'cambio de gerente', 'licitación', 'nota de prensa', 'otro'];
function lineaLabel(l?: string): string {
  const v = (l ?? '').toLowerCase();
  if (v === 'koolkat') return 'Koolkat';
  if (v === 'solar') return 'Solar';
  if (v === 'evaporativa') return 'Evaporativa';
  return l ?? '—';
}
function ComponentRow({ k, v }: { k: string; v: unknown }) {
  let txt: string;
  if (typeof v === 'number') txt = v.toFixed(1);
  else if (v !== null && typeof v === 'object') {
    const o = v as Record<string, unknown>;
    txt = 'x' in o || 'w' in o ? `x=${String(o.x ?? '?')} · w=${String(o.w ?? '?')}` : JSON.stringify(o);
  } else txt = String(v ?? '—');
  return (<div className="flex justify-between gap-4"><dt className="text-muted-foreground">{k}</dt><dd className="font-mono">{txt}</dd></div>);
}
function FichaItem({ k, v }: { k: string; v?: string }) {
  return (<div><dt className="text-xs text-muted-foreground">{k}</dt><dd className="font-medium">{v ?? '—'}</dd></div>);
}

function EtapaStepper({ lead, onCambiar, cambiando }: { lead: LeadUnificado; onCambiar: (etapa: string) => void; cambiando: boolean }) {
  const actual = (lead.etapa ?? 'nuevo').toLowerCase();
  const idx = ETAPAS_RADAR.findIndex((e) => e.id === actual);
  return (
    <div className="flex min-w-[12rem] flex-wrap items-center gap-0.5" role="group" aria-label="Cambiar etapa">
      {ETAPAS_RADAR.map((e, i) => {
        const activo = i === idx;
        const alcanzado = idx >= 0 && i <= idx;
        return (
          <React.Fragment key={e.id}>
            <button type="button" disabled={cambiando} onClick={() => onCambiar(e.id)} title={`Cambiar a «${e.label}»`}
              className={cn('flex h-6 w-6 items-center justify-center rounded-full border text-[10px] font-bold transition-colors',
                activo ? 'border-primary bg-primary text-primary-foreground' : alcanzado ? 'border-primary/50 bg-primary/15 text-primary' : 'border-input bg-background text-muted-foreground hover:border-primary/50')}>
              {i + 1}
            </button>
            {i < ETAPAS_RADAR.length - 1 && <span className={cn('h-px w-2', alcanzado ? 'bg-primary/50' : 'bg-input')} aria-hidden />}
          </React.Fragment>
        );
      })}
      <span className="ml-2 text-xs text-muted-foreground">{ETAPAS_RADAR[idx]?.label ?? actual}</span>
    </div>
  );
}

interface Pagina<T> { items?: T[]; data?: T[]; next_cursor?: string | null }

export default function Leads() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [espaciales, setEspaciales] = React.useState<LeadUnificado[]>([]);
  const [radar, setRadar] = React.useState<LeadGeo[]>([]);
  const [cursorEsp, setCursorEsp] = React.useState<string | null>(null);
  const [cursorRad, setCursorRad] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [cargandoMas, setCargandoMas] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [totalRadarReal, setTotalRadarReal] = React.useState<number | null>(null);

  const [origen, setOrigen] = React.useState<'todos' | 'espacial' | 'radar'>('todos');
  const [busqueda, setBusqueda] = React.useState('');
  const [fEtapa, setFEtapa] = React.useState('');
  const [fLinea, setFLinea] = React.useState('');
  const [scoreMin, setScoreMin] = React.useState(0);

  const [ficha, setFicha] = React.useState<LeadGeo | null>(null);
  const [notas, setNotas] = React.useState('');
  const [guardandoNotas, setGuardandoNotas] = React.useState(false);
  const [cambiandoEtapa, setCambiandoEtapa] = React.useState(false);
  const [senalOpen, setSenalOpen] = React.useState(false);
  const [senalEmpresa, setSenalEmpresa] = React.useState('');
  const [senalGiro, setSenalGiro] = React.useState('');
  const [senalTipo, setSenalTipo] = React.useState('hallazgo');
  const [senalEvidencia, setSenalEvidencia] = React.useState('');
  const deepLinkProcesado = React.useRef(false);

  // Filtros geográficos en cascada (GET /catalogs/geo-filters) — se combinan
  // en AND con búsqueda/etapa/línea/origen/score y viajan a /leads/curados
  // y /leads/count como query params.
  const geo = useGeoFiltros();
  const [enriqueciendo, setEnriqueciendo] = React.useState(false);
  const [enrichMsg, setEnrichMsg] = React.useState<string | null>(null);

  const cargar = React.useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const [rEsp, rRad] = await Promise.allSettled([
        get<Pagina<Lead> | Lead[]>('/leads', { limit: 100 }),
        get<Pagina<LeadCurado> | LeadCurado[]>('/leads/curados', { limit: 100, ...geo.params }),
      ]);
      if (rEsp.status === 'fulfilled') {
        const r = rEsp.value;
        const items = Array.isArray(r) ? r : (r.items ?? r.data ?? []);
        setEspaciales(items.map(desdeEspacial));
        setCursorEsp(Array.isArray(r) ? null : (r.next_cursor ?? null));
      }
      if (rRad.status === 'fulfilled') {
        const r = rRad.value;
        const items = Array.isArray(r) ? r : (r.items ?? r.data ?? []);
        setRadar(items.map(conGeo));
        setCursorRad(Array.isArray(r) ? null : (r.next_cursor ?? null));
      }
      if (rEsp.status === 'rejected' && rRad.status === 'rejected') setError(errorMessage(rEsp.reason));
      try { const c = await getLeadsCountGeo({ ...geo.params }); setTotalRadarReal(c.total); } catch { setTotalRadarReal(null); }
    } finally { setLoading(false); }
  }, [geo.params]);

  React.useEffect(() => { cargar(); }, [cargar]);
  React.useEffect(() => { setNotas(ficha?.notas ?? ''); }, [ficha]);

  const cargarMas = async () => {
    setCargandoMas(true);
    try {
      if (cursorEsp) {
        const r = await get<Pagina<Lead> | Lead[]>('/leads', { limit: 100, cursor: cursorEsp });
        const items = Array.isArray(r) ? r : (r.items ?? r.data ?? []);
        setEspaciales((prev) => [...prev, ...items.map(desdeEspacial)]);
        setCursorEsp(Array.isArray(r) ? null : (r.next_cursor ?? null));
      }
      if (cursorRad) {
        const r = await get<Pagina<LeadCurado> | LeadCurado[]>('/leads/curados', { limit: 100, cursor: cursorRad, ...geo.params });
        const items = Array.isArray(r) ? r : (r.items ?? r.data ?? []);
        setRadar((prev) => [...prev, ...items.map(conGeo)]);
        setCursorRad(Array.isArray(r) ? null : (r.next_cursor ?? null));
      }
      if (!cursorEsp && !cursorRad) toast.info('No hay más páginas', { description: 'Ya se cargaron todos los leads disponibles de cada origen.' });
    } catch (e) { toast.error('No se pudo cargar más', { description: errorMessage(e) }); }
    finally { setCargandoMas(false); }
  };

  const todos = React.useMemo(() => {
    let arr = [...espaciales, ...radar];
    if (origen !== 'todos') arr = arr.filter((l) => l.origen === origen);
    if (busqueda.trim()) arr = arr.filter((l) => l.nombre.toLowerCase().includes(busqueda.trim().toLowerCase()));
    if (fEtapa) arr = arr.filter((l) => l.origen === 'radar' && (l.etapa ?? 'nuevo') === fEtapa);
    if (fLinea) arr = arr.filter((l) => l.origen === 'radar' && (l.linea ?? '').toLowerCase() === fLinea);
    if (scoreMin > 0) arr = arr.filter((l) => (l.score ?? 0) >= scoreMin);
    arr.sort((a, b) => (b.score ?? 0) - (a.score ?? 0));
    return arr;
  }, [espaciales, radar, origen, busqueda, fEtapa, fLinea, scoreMin]);

  // Deep-link ?lead= / ?denue=
  React.useEffect(() => {
    if (loading || deepLinkProcesado.current) return;
    const leadParam = searchParams.get('lead');
    const denueParam = searchParams.get('denue');
    if (!leadParam && !denueParam) { deepLinkProcesado.current = true; return; }
    deepLinkProcesado.current = true;
    if (leadParam) {
      const found = radar.find((l) => String(l.lead_id) === leadParam);
      if (found) { setFicha(found); return; }
      get<LeadCurado>(`/leads/curados/${leadParam}`)
        .then((l) => setFicha(conGeo(l)))
        .catch(() => toast.info('Lead no encontrado', { description: `No se encontró el lead Radar ${leadParam} en la página cargada ni por ID.` }));
    }
    if (denueParam) {
      const found = espaciales.find((l) => l.denue_id === denueParam);
      if (found) { setFicha(found); return; }
      toast.info('Establecimiento no cargado', { description: `El establecimiento ${denueParam} no está en la página cargada. Usa «Cargar más» o búscalo por nombre.` });
    }
  }, [loading, radar, espaciales, searchParams]);

  const cambiarEtapa = async (lead: LeadUnificado, etapa: string) => {
    if (lead.origen !== 'radar' || lead.lead_id == null) return;
    if ((lead.etapa ?? 'nuevo') === etapa) return;
    setCambiandoEtapa(true);
    try {
      await patch(`/leads/curados/${lead.lead_id}`, { etapa });
      const upd = (l: LeadUnificado) => (l.lead_id === lead.lead_id && l.origen === 'radar' ? { ...l, etapa } : l);
      setRadar((prev) => prev.map(upd));
      setFicha((f) => (f && f.lead_id === lead.lead_id ? { ...f, etapa } : f));
      toast.success(`«${lead.nombre}» → ${ETAPAS_RADAR.find((e) => e.id === etapa)?.label ?? etapa}`);
    } catch (e) { toast.error('No se pudo cambiar la etapa', { description: errorMessage(e) }); }
    finally { setCambiandoEtapa(false); }
  };

  const guardarNotas = async () => {
    if (!ficha || ficha.lead_id == null) return;
    setGuardandoNotas(true);
    try {
      await patch(`/leads/curados/${ficha.lead_id}`, { notas });
      setRadar((prev) => prev.map((l) => (l.lead_id === ficha.lead_id ? { ...l, notas } : l)));
      setFicha({ ...ficha, notas });
      toast.success('Notas guardadas');
    } catch (e) { toast.error('No se pudieron guardar las notas', { description: errorMessage(e) }); }
    finally { setGuardandoNotas(false); }
  };

  const abrirSenal = () => {
    if (!ficha) return;
    setSenalEmpresa(ficha.nombre);
    setSenalGiro(ficha.giro ?? '');
    setSenalTipo('hallazgo');
    setSenalEvidencia('');
    setSenalOpen(true);
  };

  const registrarSenal = async () => {
    if (!ficha) return;
    try {
      // POST /signals real (signals.py): {titulo, detalle, empresa_ref, fuente}.
      // El tipo viaja en el título y el giro en el detalle, como el original
      // componía `evidencia = tipo + ' — ' + evidencia` (inventario #42).
      await postSignal({
        titulo: `${senalTipo} — ${senalEmpresa}`,
        detalle: senalGiro ? `${senalEvidencia} (giro: ${senalGiro})` : senalEvidencia,
        empresa_ref: senalEmpresa,
        fuente: 'manual',
      });
      setSenalOpen(false); setSenalEvidencia('');
      toast.success('Señal registrada', { description: 'La etapa 03 la procesa (+25 score si hay match con un lead).' });
    } catch (e) { toast.error('No se pudo registrar la señal', { description: errorMessage(e) }); }
  };

  // Botón «Enriquecer geografía»: SIEMPRE visible en el panel geo.
  // Decisión: la estimación por muestra (¿algún lead cargado sin entidad?)
  // puede dar falsos negativos con la paginación por cursor — un lead sin
  // entidad puede estar en una página no cargada — así que el botón no se
  // oculta; el tooltip lo explica y el POST es idempotente.
  const muestraSinEntidad = radar.some((l) => !l.entidad);
  const enriquecerGeo = async () => {
    setEnriqueciendo(true); setEnrichMsg(null);
    try {
      const r = await postEnrichGeo(500);
      const msg = `${r.actualizados} leads actualizados · ${r.pendientes} pendientes (con geometría: ${r.detalle.con_geometria} · solo CP: ${r.detalle.solo_cp} · sin datos: ${r.detalle.sin_datos}).`;
      setEnrichMsg(msg);
      toast.success('Geografía enriquecida', { description: msg });
      geo.recargar();
      await cargar();
    } catch (e) { toast.error('No se pudo enriquecer la geografía', { description: errorMessage(e) }); }
    finally { setEnriqueciendo(false); }
  };

  const columns = React.useMemo<ColumnDef<LeadUnificado>[]>(() => [
    {
      accessorKey: 'nombre', header: 'Nombre',
      cell: ({ row }) => (<button type="button" className="text-left font-medium text-primary hover:underline" onClick={() => setFicha(row.original)} title="Ver ficha completa">{row.original.nombre}</button>),
    },
    {
      accessorKey: 'origen', header: 'Origen',
      cell: ({ row }) => row.original.origen === 'radar'
        ? <Badge variant="default">Radar</Badge>
        : <Badge variant="secondary">Espacial</Badge>,
    },
    { accessorKey: 'giro', header: 'Giro', cell: ({ row }) => <span className="text-xs">{row.original.giro ?? '—'}</span> },
    {
      accessorKey: 'linea', header: 'Línea',
      cell: ({ row }) => row.original.linea
        ? <Badge style={{ backgroundColor: lineaColor(row.original.linea), color: '#fff' }} className="border-transparent">{lineaLabel(row.original.linea)}</Badge>
        : <span className="text-muted-foreground">—</span>,
    },
    {
      accessorKey: 'etapa', header: 'Etapa',
      cell: ({ row }) => row.original.origen === 'radar'
        ? <Badge variant={ETAPA_BADGE[(row.original.etapa ?? 'nuevo').toLowerCase()] ?? 'secondary'}>{ETAPAS_RADAR.find((e) => e.id === (row.original.etapa ?? 'nuevo').toLowerCase())?.label ?? row.original.etapa}</Badge>
        : <span className="text-xs text-muted-foreground" title="Los espaciales no tienen etapa comercial">N/A</span>,
    },
    {
      accessorKey: 'score', header: 'Score',
      cell: ({ row }) => (<div className="flex min-w-[7rem] items-center gap-2"><Progress value={row.original.score ?? 0} className="h-2 w-16" /><span className="font-mono text-sm font-semibold">{row.original.score ?? '—'}</span></div>),
    },
    { accessorKey: 'municipio', header: 'Municipio', cell: ({ row }) => row.original.municipio ?? '—' },
    {
      accessorKey: 'estrato', header: 'Estrato',
      cell: ({ row }) => row.original.estrato
        ? <Badge style={{ backgroundColor: estratoColor(row.original.estrato), color: '#fff' }} className="border-transparent">{row.original.estrato}</Badge>
        : <span className="text-muted-foreground">—</span>,
    },
  ], []);

  const wa = ficha ? normPhone(ficha.telefono) : null;
  const webUrl = ficha ? normWeb(ficha.web) : null;
  const mapsUrl = ficha
    ? (ficha.lat != null && ficha.lon != null
      ? `https://www.google.com/maps/search/?api=1&query=${ficha.lat},${ficha.lon}`
      : `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(ficha.direccion ?? ficha.nombre)}`)
    : '#';
  const linkedinUrl = ficha ? `https://www.linkedin.com/search/results/companies/?keywords=${encodeURIComponent(ficha.nombre)}` : '#';
  const sinDatos = !loading && espaciales.length === 0 && radar.length === 0;

  return (
    <div className="flex h-full flex-col">
      <Topbar titulo="Leads" subtitulo="Una sola lista: matriz espacial (DENUE) + pipeline comercial (Radar)" />
      <div className="flex-1 overflow-y-auto p-6">
        <div className="space-y-4">
          <div className="flex flex-wrap items-baseline gap-3">
            <h2 className="text-lg font-semibold">{totalRadarReal != null ? `${totalRadarReal} leads` : 'Leads'}</h2>
            <span className="text-sm text-muted-foreground">total Radar real (GET /leads/count) · mostrando {todos.length} según filtros/cargados ({espaciales.length} espaciales + {radar.length} radar cargados)</span>
            <Button variant="ghost" size="sm" className="ml-auto" onClick={() => { cargar(); toast.info('Recargando leads…'); }}>Recargar</Button>
          </div>

          {error && (<Alert variant="destructive"><AlertTitle>Error al cargar leads</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>)}

          {/* Filtros */}
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex gap-1" role="group" aria-label="Filtro por origen">
              {([['todos', 'Todos'], ['espacial', 'Espacial'], ['radar', 'Radar']] as const).map(([id, label]) => (
                <Button key={id} size="sm" variant={origen === id ? 'default' : 'outline'} onClick={() => setOrigen(id)}>{label}</Button>
              ))}
            </div>
            <Input placeholder="Buscar por nombre…" value={busqueda} onChange={(e) => setBusqueda(e.target.value)} className="max-w-xs" aria-label="Buscar por nombre" />
            <label className="flex items-center gap-2 text-sm">Etapa
              <NativeSelect value={fEtapa} onChange={(e) => setFEtapa(e.target.value)} aria-label="Filtrar por etapa">
                <option value="">Todas</option>
                {ETAPAS_RADAR.map((e) => <option key={e.id} value={e.id}>{e.label}</option>)}
              </NativeSelect>
            </label>
            <label className="flex items-center gap-2 text-sm">Línea
              <NativeSelect value={fLinea} onChange={(e) => setFLinea(e.target.value)} aria-label="Filtrar por línea">
                <option value="">Todas</option>
                <option value="koolkat">Koolkat</option>
                <option value="solar">Solar</option>
                <option value="evaporativa">Evaporativa</option>
              </NativeSelect>
            </label>
            <div className="flex min-w-[12rem] items-center gap-2">
              <span className="text-sm">Score mín. {scoreMin}</span>
              <Slider value={[scoreMin]} onValueChange={(v) => setScoreMin(v[0] ?? 0)} max={100} step={5} className="w-28" aria-label="Score mínimo" />
            </div>
          </div>
          {fEtapa && <p className="text-xs text-muted-foreground">Nota: el filtro de etapa aplica solo a leads Radar — los espaciales no tienen etapa comercial y se excluyen mientras este filtro esté activo.</p>}
          {fLinea && <p className="text-xs text-muted-foreground">Nota: el filtro de línea aplica solo a leads Radar.</p>}

          {/* Filtros geográficos en cascada (Sección 2 · nuevo) */}
          <Card>
            <CardHeader className="pb-2">
              <div className="flex flex-wrap items-center gap-3">
                <CardTitle className="text-base">Filtros geográficos</CardTitle>
                {geo.activo && <Badge variant="accent">Filtro geo activo</Badge>}
                {muestraSinEntidad && radar.length > 0 && <Badge variant="warning">Hay leads cargados sin entidad</Badge>}
                <div className="ml-auto flex gap-2">
                  {geo.activo && <Button variant="ghost" size="sm" onClick={geo.limpiar}>Limpiar geografía</Button>}
                  <Button
                    size="sm" variant="secondary" onClick={enriquecerGeo} disabled={enriqueciendo}
                    title="Deriva entidad, municipio, colonia, CP y SCIAN de los leads que aún no los tienen (POST /leads/enrich-geo, idempotente). Siempre visible: la muestra cargada puede no incluir todos los leads sin entidad."
                  >
                    {enriqueciendo ? 'Enriqueciendo…' : '🌎 Enriquecer geografía'}
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-2">
              <div className="flex flex-wrap items-center gap-3">
                <label className="flex items-center gap-2 text-sm">Entidad
                  <NativeSelect value={geo.sel.entidad} onChange={(e) => geo.cambiar('entidad', e.target.value)} aria-label="Filtrar por entidad">
                    <option value="">Todas</option>
                    {geo.opts.entidades.map((v) => <option key={v} value={v}>{v}</option>)}
                  </NativeSelect>
                </label>
                <label className="flex items-center gap-2 text-sm">Municipio
                  <NativeSelect value={geo.sel.municipio} onChange={(e) => geo.cambiar('municipio', e.target.value)} aria-label="Filtrar por municipio">
                    <option value="">Todos</option>
                    {geo.opts.municipios.map((v) => <option key={v} value={v}>{v}</option>)}
                  </NativeSelect>
                </label>
                <label className="flex items-center gap-2 text-sm">Colonia
                  <NativeSelect value={geo.sel.colonia} onChange={(e) => geo.cambiar('colonia', e.target.value)} aria-label="Filtrar por colonia">
                    <option value="">Todas</option>
                    {geo.opts.colonias.map((v) => <option key={v} value={v}>{v}</option>)}
                  </NativeSelect>
                </label>
                <label className="flex items-center gap-2 text-sm">CP
                  <NativeSelect value={geo.sel.cp} onChange={(e) => geo.cambiar('cp', e.target.value)} aria-label="Filtrar por código postal">
                    <option value="">Todos</option>
                    {geo.opts.cps.map((v) => <option key={v} value={v}>{v}</option>)}
                  </NativeSelect>
                </label>
                <label className="flex items-center gap-2 text-sm">SCIAN
                  <NativeSelect value={geo.sel.scian} onChange={(e) => geo.cambiar('scian', e.target.value)} aria-label="Filtrar por SCIAN">
                    <option value="">Todos</option>
                    {geo.opts.scians.map((v) => <option key={v} value={v}>{v}</option>)}
                  </NativeSelect>
                </label>
              </div>
              <p className="text-xs text-muted-foreground">
                Cascada desde <code>GET /catalogs/geo-filters</code> (leads + establecimientos DENUE). Los filtros geo se combinan en AND con búsqueda, etapa, línea, origen y score, y aplican a los leads Radar (los espaciales se filtran por su propio municipio en la tabla).
              </p>
              {enrichMsg && <p className="text-xs font-medium text-primary">{enrichMsg}</p>}
            </CardContent>
          </Card>

          {loading ? (
            <div className="space-y-2"><Skeleton className="h-10 w-64" /><Skeleton className="h-96" /></div>
          ) : sinDatos ? (
            <div className="space-y-3">
              <Empty title="Sin leads de ningún origen" description="Falta cargar datos: lanza el pipeline 01 desde Operación para generar leads Radar, o dibuja un polígono en el Mapa para explorar establecimientos DENUE." icon="🎯" action={{ label: 'Ir a Operación', onClick: () => navigate('/operacion') }} />
              <div className="flex justify-center"><Button variant="outline" onClick={() => navigate('/mapa')}>Ir al mapa</Button></div>
            </div>
          ) : (
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle>Lista unificada</CardTitle>
                <span className="text-xs text-muted-foreground">Orden: score descendente por defecto</span>
              </CardHeader>
              <CardContent className="space-y-3">
                <DataTable columns={columns} data={todos} pageSize={20} emptyText="Sin leads con estos filtros. Ajusta origen, etapa, línea o score mínimo." />
                <div className="flex flex-wrap items-center gap-3">
                  <Button variant="outline" size="sm" onClick={cargarMas} disabled={cargandoMas || (!cursorEsp && !cursorRad)}>{cargandoMas ? 'Cargando…' : 'Cargar más'}</Button>
                  <span className="text-xs text-muted-foreground">
                    {(!cursorEsp && !cursorRad) ? `Mostrando los primeros ${espaciales.length} espaciales y ${radar.length} radar de cada origen (sin más páginas).` : 'Hay más páginas disponibles en al menos un origen.'}
                  </span>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      <Drawer open={!!ficha} onClose={() => setFicha(null)} title="Ficha del lead">
        {ficha && (
          <div className="space-y-4 text-sm">
            <div>
              <h4 className="text-base font-semibold">{ficha.nombre}</h4>
              <p className="text-xs text-muted-foreground">{ficha.giro ?? '—'} · {ficha.direccion ?? 'Sin dirección'}</p>
              <div className="mt-2 flex flex-wrap gap-2">
                <Badge variant={ficha.origen === 'radar' ? 'default' : 'secondary'}>{ficha.origen === 'radar' ? 'Radar' : 'Espacial'}</Badge>
                {ficha.linea && <Badge style={{ backgroundColor: lineaColor(ficha.linea), color: '#fff' }} className="border-transparent">{lineaLabel(ficha.linea)}</Badge>}
                {ficha.origen === 'radar' && ficha.etapa && <Badge variant={ETAPA_BADGE[(ficha.etapa ?? 'nuevo').toLowerCase()] ?? 'secondary'}>{ETAPAS_RADAR.find((e) => e.id === (ficha.etapa ?? 'nuevo').toLowerCase())?.label ?? ficha.etapa}</Badge>}
                {ficha.score !== undefined && <Badge variant="outline" className="font-mono">Score {ficha.score}</Badge>}
                {ficha.enriquecido_apollo && <Badge variant="accent">Apollo ✓</Badge>}
                {ficha.crm_synced_at && <Badge variant="success">CRM ✓ {new Date(ficha.crm_synced_at).toLocaleDateString('es-MX')}</Badge>}
              </div>
            </div>
            {ficha.origen === 'radar' && (
              <>
                <Separator />
                <div>
                  <p className="mb-1 font-semibold">💡 Por qué este lead</p>
                  <p className="text-xs leading-relaxed text-muted-foreground">{whyLinea(ficha.giro, ficha.linea)}</p>
                </div>
              </>
            )}
            <Separator />
            <div>
              <p className="mb-2 font-semibold">📞 Cómo contactarlo</p>
              <div className="grid grid-cols-2 gap-2">
                <a href={wa ? `tel:${wa}` : undefined} aria-disabled={!wa} className={cn(buttonVariants({ variant: 'outline', size: 'sm' }), !wa && 'pointer-events-none opacity-50')}>☎️ Llamar</a>
                <a href={wa ? `https://wa.me/${wa}` : undefined} target="_blank" rel="noopener noreferrer" aria-disabled={!wa} className={cn(buttonVariants({ variant: 'outline', size: 'sm' }), !wa && 'pointer-events-none opacity-50')}>💬 WhatsApp</a>
                <a href={webUrl ?? undefined} target="_blank" rel="noopener noreferrer" aria-disabled={!webUrl} className={cn(buttonVariants({ variant: 'outline', size: 'sm' }), !webUrl && 'pointer-events-none opacity-50')}>🌐 Abrir sitio</a>
                <a href={linkedinUrl} target="_blank" rel="noopener noreferrer" className={buttonVariants({ variant: 'outline', size: 'sm' })}>💼 Buscar en LinkedIn</a>
                <a href={mapsUrl} target="_blank" rel="noopener noreferrer" className={cn(buttonVariants({ variant: 'outline', size: 'sm' }), 'col-span-2')}>📍 Ver mapa</a>
              </div>
              {!wa && (
                <p className="mt-1 text-[11px] text-warning">
                  {ficha.telefono
                    ? 'El teléfono registrado no es un número MX válido (menos de 10 dígitos): búscalo en su sitio web o en LinkedIn.'
                    : 'Sin teléfono registrado — búscalo en su sitio web o LinkedIn.'}
                </p>
              )}
              {!webUrl && <p className="mt-1 text-[11px] text-muted-foreground">Sin sitio registrado.</p>}
              <p className="mt-1 text-[11px] text-muted-foreground">Tel: {ficha.telefono ?? '—'} · Correo: {ficha.correo ?? '—'} · Web: {ficha.web ?? '—'}{ficha.rating != null ? ` · Rating: ${ficha.rating}` : ''}</p>
              <p className="text-[11px] text-muted-foreground">GEIS nunca inventa datos de contacto: los campos vacíos viajan vacíos.</p>
            </div>
            <Separator />
            <div>
              <p className="mb-2 font-semibold">Etapa del pipeline</p>
              {ficha.origen === 'radar' ? (
                <EtapaStepper lead={ficha} cambiando={cambiandoEtapa} onCambiar={(e) => cambiarEtapa(ficha, e)} />
              ) : (
                <p className="text-xs text-muted-foreground">No aplicable: los leads espaciales (DENUE) no tienen etapa comercial. La etapa se gestiona solo en leads Radar.</p>
              )}
            </div>
            {ficha.origen === 'radar' && (
              <>
                <Separator />
                <div>
                  <Field label="Notas del SDR" htmlFor="notas">
                    <Textarea id="notas" value={notas} onChange={(e) => setNotas(e.target.value)} placeholder="Ej. Llamé el lunes, pidió cotización…" rows={4} />
                  </Field>
                  <Button size="sm" className="mt-2" onClick={guardarNotas} disabled={guardandoNotas}>{guardandoNotas ? 'Guardando…' : 'Guardar notas'}</Button>
                </div>
                <Separator />
                <div className="space-y-2">
                  <p className="font-semibold">Señales</p>
                  <p className="text-xs text-muted-foreground">Registra una señal manual. El pipeline radar-03 la procesa y puede sumar score.</p>
                  <Button size="sm" variant="secondary" onClick={abrirSenal}>➕ Registrar señal</Button>
                </div>
              </>
            )}
            {ficha.desglose && Object.keys(ficha.desglose).length > 0 && (
              <>
                <Separator />
                <div>
                  <p className="mb-1 font-semibold">Desglose del score</p>
                  <dl className="space-y-1">{Object.entries(ficha.desglose).map(([k, v]) => <ComponentRow key={k} k={k} v={v} />)}</dl>
                </div>
              </>
            )}
            <dl className="grid grid-cols-2 gap-x-4 gap-y-2 pt-2">
              <FichaItem k="Fuente" v={ficha.source} />
              <FichaItem k="Temp. zona" v={ficha.temp_zona !== undefined ? `${ficha.temp_zona} °C` : undefined} />
              <FichaItem k="Entidad" v={ficha.entidad ?? undefined} />
              <FichaItem k="Municipio" v={ficha.municipio} />
              <FichaItem k="Colonia" v={ficha.colonia ?? undefined} />
              <FichaItem k="CP" v={ficha.cp ?? undefined} />
              <FichaItem k="SCIAN" v={ficha.scian ?? ficha.crudoEspacial?.scian_code} />
              <FichaItem k="Estrato" v={ficha.estrato} />
              <FichaItem k="IDT" v={ficha.idt !== undefined ? String(ficha.idt) : undefined} />
              <FichaItem k="DENUE" v={ficha.denue_id} />
            </dl>
          </div>
        )}
      </Drawer>

      <Dialog open={senalOpen} onOpenChange={setSenalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Registrar señal</DialogTitle>
            <DialogDescription>Señal manual sobre «{ficha?.nombre}». Llega a <code>warm_signals</code> vía <code>POST /signals</code>; la etapa 03 la procesa (+25).</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <Field label="Empresa" htmlFor="senal-e" required><Input id="senal-e" value={senalEmpresa} onChange={(e) => setSenalEmpresa(e.target.value)} placeholder="Nombre de la empresa" /></Field>
            <Field label="Giro" htmlFor="senal-g"><Input id="senal-g" value={senalGiro} onChange={(e) => setSenalGiro(e.target.value)} placeholder="Ej. bodegas, plantas industriales…" /></Field>
            <Field label="Tipo" htmlFor="senal-tipo">
              <NativeSelect id="senal-tipo" value={senalTipo} onChange={(e) => setSenalTipo(e.target.value)} aria-label="Tipo de señal">
                {TIPOS_SENAL.map((t) => <option key={t} value={t}>{t}</option>)}
              </NativeSelect>
            </Field>
            <Field label="Evidencia" htmlFor="senal-ev" required><Textarea id="senal-ev" value={senalEvidencia} onChange={(e) => setSenalEvidencia(e.target.value)} placeholder="Qué pasó, cuándo, evidencia…" rows={3} /></Field>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setSenalOpen(false)}>Cancelar</Button>
            <Button onClick={registrarSenal} disabled={!senalEmpresa.trim() || !senalEvidencia.trim()}>Registrar señal</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

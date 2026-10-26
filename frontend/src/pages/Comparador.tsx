import * as React from 'react';
import { useNavigate } from 'react-router-dom';
import { Topbar } from '@/components/layout/Topbar';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/Alert';
import { Skeleton } from '@/components/ui/Skeleton';
import { Empty } from '@/components/ui/Empty';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Checkbox } from '@/components/ui/Checkbox';
import { Input } from '@/components/ui/Input';
import { Field } from '@/components/ui/Field';
import { Spinner } from '@/components/ui/Spinner';
import {
  get, geocode, createInvestigation, compareItems, patchInvestigation,
  errorMessage, type Investigation, type CompareItem, type CompareResponse,
} from '@/lib/api';
import { verdictColor } from '@/lib/geo';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

const mxnFmt = (v?: number | null) => typeof v === 'number' ? new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN', maximumFractionDigits: 0 }).format(v) : '—';
const numFmt = (v?: number | null) => typeof v === 'number' ? v.toLocaleString('es-MX') : '—';
const decFmt = (v?: number | null) => typeof v === 'number' ? v.toFixed(2) : '—';

type MetricKey = 'ism' | 'tam' | 'competencia' | 'poblacion' | 'huff_score';
const METRICAS: { key: MetricKey; label: string; mayorMejor: boolean; fmt: (v?: number | null) => string }[] = [
  { key: 'ism', label: 'ISM', mayorMejor: true, fmt: decFmt },
  { key: 'tam', label: 'TAM', mayorMejor: true, fmt: mxnFmt },
  { key: 'competencia', label: 'Competencia', mayorMejor: false, fmt: numFmt },
  { key: 'poblacion', label: 'Población', mayorMejor: true, fmt: numFmt },
  { key: 'huff_score', label: 'Huff', mayorMejor: true, fmt: decFmt },
];

export default function Comparador() {
  const navigate = useNavigate();
  const [items, setItems] = React.useState<Investigation[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [seleccion, setSeleccion] = React.useState<string[]>([]);
  const [comparando, setComparando] = React.useState(false);
  const [resultado, setResultado] = React.useState<CompareResponse | null>(null);
  const [ganadora, setGanadora] = React.useState<string | null>(null);
  const [marcandoGanadora, setMarcandoGanadora] = React.useState(false);
  const [dirNueva, setDirNueva] = React.useState('');
  const [giroNuevo, setGiroNuevo] = React.useState('');
  const [agregando, setAgregando] = React.useState(false);

  React.useEffect(() => {
    get<{ items?: Investigation[]; data?: Investigation[] } | Investigation[]>('/investigations', { limit: 100 })
      .then((r) => {
        const arr = Array.isArray(r) ? r : (r.items ?? r.data ?? []);
        setItems(arr);
        // Ganadora persistente: la investigación marcada es_principal.
        const principal = arr.find((i) => i.es_principal);
        if (principal) setGanadora(principal.investigation_id);
        // Preselección desde localStorage
        try {
          const raw = localStorage.getItem('geis:comparar');
          if (raw) {
            const ids = JSON.parse(raw) as string[];
            const validas = ids.filter((id) => arr.some((i) => i.investigation_id === id)).slice(0, 6);
            if (validas.length) setSeleccion(validas);
          }
        } catch { /* localStorage no disponible o JSON inválido */ }
      })
      .catch((e) => setError(errorMessage(e)))
      .finally(() => setLoading(false));
  }, []);

  const toggle = (id: string, checked: boolean) => {
    setSeleccion((prev) => {
      if (checked) {
        if (prev.length >= 6) { toast.warning('Máximo 6 ubicaciones', { description: 'Desmarca una para agregar otra.' }); return prev; }
        return [...prev, id];
      }
      return prev.filter((x) => x !== id);
    });
  };

  /** Dirección directa: geocodifica, crea la investigación (queda en Historial) y la selecciona. */
  const agregarDireccion = async () => {
    if (!dirNueva.trim() || seleccion.length >= 6) return;
    setAgregando(true);
    try {
      const g = await geocode({ address: dirNueva.trim() });
      const inv = await createInvestigation({
        title: giroNuevo.trim() ? `${giroNuevo.trim()} · ${g.label}` : `Ubicación · ${g.label}`,
        investigation_type: 'location_viability',
        territory_kind: 'point_buffers',
        center_lat: g.lat,
        center_lon: g.lon,
        radii_m: [1000, 2000],
        params: { giro: giroNuevo.trim() || undefined },
      });
      setItems((prev) => [inv, ...prev]);
      setSeleccion((prev) => [...prev, inv.investigation_id]);
      setDirNueva('');
      setGiroNuevo('');
      toast.success('Ubicación agregada', { description: `Se creó la investigación «${inv.title}»: queda guardada en tu Historial.` });
    } catch (e) {
      toast.error('No se pudo agregar la ubicación', { description: errorMessage(e) });
    } finally { setAgregando(false); }
  };

  const comparar = async () => {
    setComparando(true);
    try {
      const res = await compareItems(seleccion.map((id) => ({ investigation_id: id })));
      setResultado(res);
    } catch (e) {
      toast.error('No se pudo comparar', { description: errorMessage(e) });
    } finally { setComparando(false); }
  };

  /** Ganadora persistente: PATCH es_principal=true (el backend desmarca las demás). */
  const elegirGanadora = async (it: CompareItem) => {
    // Los ítems de punto directo no tienen investigación que marcar.
    const existe = items.some((i) => i.investigation_id === it.id);
    if (!existe) {
      toast.info('Este punto no es una investigación guardada', { description: 'Solo las ubicaciones guardadas pueden marcarse como ganadora persistente.' });
      return;
    }
    setMarcandoGanadora(true);
    try {
      await patchInvestigation(it.id, { es_principal: true });
      setGanadora(it.id);
      setItems((prev) => prev.map((i) => ({ ...i, es_principal: i.investigation_id === it.id })));
      toast.success('Ganadora guardada', { description: `${it.nombre ?? it.id} quedó como ubicación principal (persiste en el servidor).` });
    } catch (e) {
      toast.error('No se pudo guardar la ganadora', { description: errorMessage(e) });
    } finally { setMarcandoGanadora(false); }
  };

  const mejorPorMetrica = React.useMemo(() => {
    const map = new Map<MetricKey, string>();
    if (!resultado) return map;
    for (const m of METRICAS) {
      let bestId: string | null = null; let bestVal: number | null = null;
      for (const it of resultado.items) {
        const v = it[m.key] as number | null | undefined;
        if (typeof v !== 'number') continue;
        if (bestVal === null || (m.mayorMejor ? v > bestVal : v < bestVal)) { bestVal = v; bestId = it.id; }
      }
      if (bestId) map.set(m.key, bestId);
    }
    return map;
  }, [resultado]);

  return (
    <div className="flex h-full flex-col">
      <Topbar titulo="Comparador multi-ubicación" subtitulo="Tabla comparativa de ubicaciones candidatas · selecciona de 2 a 6, o agrega una dirección directa" />
      <div className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-5xl space-y-4">
          {error && <Alert variant="destructive"><AlertTitle>Error</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>}
          {loading ? (
            <div className="space-y-2"><Skeleton className="h-10 w-64" /><Skeleton className="h-64" /></div>
          ) : (
            <>
              <Card>
                <CardHeader>
                  <CardTitle>Agregar por dirección directa</CardTitle>
                  <CardDescription>
                    Escribe una dirección o pega un link de Google Maps: se geocodifica y se crea la investigación al momento.
                    <strong> Quedará guardada en tu Historial</strong>, como cualquier otra investigación. Máximo 6 ubicaciones en total.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="grid gap-3 sm:grid-cols-[1fr_2fr_auto] sm:items-end">
                    <Field label="Giro (opcional)" htmlFor="cmp-giro">
                      <Input id="cmp-giro" placeholder="Ej. Cafetería" value={giroNuevo} onChange={(e) => setGiroNuevo(e.target.value)} />
                    </Field>
                    <Field label="Dirección o link de Maps" htmlFor="cmp-dir">
                      <Input id="cmp-dir" placeholder="Col. Roma Norte, CDMX — o el link de Maps" value={dirNueva} onChange={(e) => setDirNueva(e.target.value)} />
                    </Field>
                    <Button onClick={agregarDireccion} disabled={agregando || !dirNueva.trim() || seleccion.length >= 6}>
                      {agregando && <Spinner size={14} />} Agregar ubicación
                    </Button>
                  </div>
                  {seleccion.length >= 6 && <p className="text-xs text-muted-foreground">Ya tienes 6 ubicaciones seleccionadas (el máximo). Desmarca una para agregar otra.</p>}
                </CardContent>
              </Card>

              {items.length === 0 ? (
                <Empty title="Sin investigaciones para comparar" description="Todavía no hay ubicaciones guardadas. Agrega dos direcciones con el formulario de arriba (quedan en tu Historial) o crea una investigación en el Mapa." icon="⚖️" action={{ label: 'Ir al mapa', onClick: () => navigate('/mapa') }} />
              ) : (
              <Card>
                <CardHeader>
                  <CardTitle>Selecciona ubicaciones ({seleccion.length}/6)</CardTitle>
                  <CardDescription>Marca de 2 a 6 investigaciones y pulsa «Comparar». La preselección puede venir del Historial. La ganadora (🏆) se guarda en el servidor.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-2">
                  {items.map((inv) => {
                    const id = inv.investigation_id;
                    const checked = seleccion.includes(id);
                    return (
                      <label key={id} className="flex cursor-pointer items-center gap-3 rounded-md border px-3 py-2 hover:bg-muted/50">
                        <Checkbox checked={checked} onCheckedChange={(c) => toggle(id, c === true)} />
                        <span className="flex-1 font-medium">{inv.title ?? `Investigación ${id.slice(0, 8)}`}</span>
                        {(inv.es_principal || ganadora === id) && <Badge variant="success">🏆 Principal</Badge>}
                        {inv.verdict && <Badge style={{ backgroundColor: verdictColor(inv.verdict), color: '#fff' }} className="border-transparent">{inv.verdict}</Badge>}
                        <span className="text-xs text-muted-foreground">{inv.created_at ? new Date(inv.created_at).toLocaleDateString('es-MX') : ''}</span>
                      </label>
                    );
                  })}
                  <div className="flex items-center gap-3 pt-2">
                    <Button onClick={comparar} disabled={seleccion.length < 2 || seleccion.length > 6 || comparando}>{comparando ? 'Comparando…' : `Comparar (${seleccion.length})`}</Button>
                    {seleccion.length < 2 && <span className="text-xs text-muted-foreground">Selecciona al menos 2 para comparar.</span>}
                  </div>
                </CardContent>
              </Card>
              )}

              {resultado && resultado.items.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle>Comparación</CardTitle>
                    <CardDescription>La celda verde es la mejor en su fila. TAM en MXN; población con separadores. Fuente: POST /analysis/compare (datos reales del backend).</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b text-left">
                            <th className="py-2 pr-4 text-xs uppercase tracking-wider text-muted-foreground">Métrica</th>
                            {resultado.items.map((it: CompareItem) => (
                              <th key={it.id} className={cn('py-2 pr-4', ganadora === it.id && 'text-green-700')}>
                                <span className="font-semibold">{it.nombre ?? it.id.slice(0, 8)}</span>
                                {ganadora === it.id && <Badge variant="success" className="ml-2">Ganadora</Badge>}
                                {it.territorio && <span className="block text-xs font-normal text-muted-foreground">{String(it.territorio)}</span>}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          <tr className="border-b">
                            <td className="py-2 pr-4 font-medium">Veredicto</td>
                            {resultado.items.map((it) => (
                              <td key={it.id} className="py-2 pr-4">
                                {it.veredicto ? <Badge style={{ backgroundColor: verdictColor(it.veredicto), color: '#fff' }} className="border-transparent">{it.veredicto}</Badge> : '—'}
                              </td>
                            ))}
                          </tr>
                          {METRICAS.map((m) => (
                            <tr key={m.key} className="border-b last:border-0">
                              <td className="py-2 pr-4 font-medium">{m.label}</td>
                              {resultado.items.map((it) => {
                                const esMejor = mejorPorMetrica.get(m.key) === it.id;
                                return (
                                  <td key={it.id} className={cn('py-2 pr-4 font-mono', esMejor && 'bg-green-100 font-bold text-green-900 dark:bg-green-900/30 dark:text-green-200')}>
                                    {m.fmt(it[m.key] as number | null | undefined)}
                                  </td>
                                );
                              })}
                            </tr>
                          ))}
                          <tr>
                            <td className="py-2 pr-4" />
                            {resultado.items.map((it) => (
                              <td key={it.id} className="py-2 pr-4">
                                <Button size="sm" variant={ganadora === it.id ? 'default' : 'outline'} disabled={marcandoGanadora} onClick={() => { void elegirGanadora(it); }}>
                                  {ganadora === it.id ? '✓ Ganadora' : 'Elegir ganadora'}
                                </Button>
                              </td>
                            ))}
                          </tr>
                        </tbody>
                      </table>
                    </div>
                    <p className="text-xs text-muted-foreground">La ganadora se guarda en el servidor (<code>es_principal</code>): persiste al recargar y al marcar otra, la anterior se desmarca automáticamente.</p>
                    {ganadora && <div className={cn('rounded-md border-2 border-green-600 p-3 text-sm')}>🏆 Ubicación principal (ganadora): <strong>{resultado.items.find((i) => i.id === ganadora)?.nombre ?? items.find((i) => i.investigation_id === ganadora)?.title ?? ganadora}</strong></div>}
                  </CardContent>
                </Card>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

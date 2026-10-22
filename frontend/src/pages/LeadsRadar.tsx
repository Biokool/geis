import * as React from 'react';
import type { ColumnDef } from '@tanstack/react-table';
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
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/Popover';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/Dialog';
import { get, patch, post, errorMessage, type LeadCurado, ETAPAS_RADAR, lineaColor } from '@/lib/api';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

const ETAPA_BADGE: Record<string, 'default' | 'secondary' | 'outline' | 'accent' | 'success' | 'destructive'> = {
  nuevo: 'secondary',
  contactado: 'outline',
  reunion: 'accent',
  propuesta: 'default',
  ganado: 'success',
  perdido: 'destructive',
};

function normalizarTelefono(tel?: string): string {
  const d = (tel ?? '').replace(/\D/g, '');
  if (!d) return '';
  if (d.length === 10) return `52${d}`;      // fijo/celular MX sin lada país
  if (d.length === 12 && d.startsWith('52')) return d;
  if (d.length === 11 && d.startsWith('521')) return `52${d.slice(3)}`;
  return d;
}

function lineaLabel(l?: string): string {
  const v = (l ?? '').toLowerCase();
  if (v === 'koolkat') return 'Koolkat';
  if (v === 'solar') return 'Solar';
  if (v === 'evaporativa') return 'Evaporativa';
  return l ?? '—';
}

/** Desglose de score_components: soporta valores numéricos u objetos {x, w}. */
function ComponentRow({ k, v }: { k: string; v: unknown }) {
  let txt: string;
  if (typeof v === 'number') txt = v.toFixed(1);
  else if (v !== null && typeof v === 'object') {
    const o = v as Record<string, unknown>;
    txt = 'x' in o || 'w' in o
      ? `x=${String(o.x ?? '?')} · w=${String(o.w ?? '?')}`
      : JSON.stringify(o);
  } else txt = String(v ?? '—');
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-muted-foreground">{k}</dt>
      <dd className="font-mono">{txt}</dd>
    </div>
  );
}

function ScoreDesglosado({ lead }: { lead: LeadCurado }) {
  const comp = lead.score_components;
  return (
    <Popover>
      <PopoverTrigger asChild>
        <div className="flex min-w-[7rem] cursor-default items-center gap-2">
          <Progress value={lead.score ?? 0} className="h-2 w-16" />
          <span className="font-mono text-sm font-semibold">{lead.score ?? '—'}</span>
        </div>
      </PopoverTrigger>
      <PopoverContent>
        <p className="mb-2 text-sm font-semibold">Desglose del score (0–100)</p>
        {comp && Object.keys(comp).length ? (
          <dl className="space-y-1 text-xs">
            {Object.entries(comp).map(([k, v]) => <ComponentRow key={k} k={k} v={v} />)}
          </dl>
        ) : (
          <p className="text-xs text-muted-foreground">Sin desglose disponible.</p>
        )}
        <p className="mt-2 text-[11px] text-muted-foreground">
          Espacial (IDT, tamaño, acceso, densidad, contacto) + conductual (temperatura &gt; 30 °C, señales, LinkedIn).
        </p>
      </PopoverContent>
    </Popover>
  );
}

function EtapaStepper({ lead, onCambiar, cambiando }: { lead: LeadCurado; onCambiar: (etapa: string) => void; cambiando: boolean }) {
  const actual = (lead.etapa ?? 'nuevo').toLowerCase();
  const idx = ETAPAS_RADAR.findIndex((e) => e.id === actual);
  return (
    <div className="flex min-w-[12rem] items-center gap-0.5" role="group" aria-label="Cambiar etapa">
      {ETAPAS_RADAR.map((e, i) => {
        const activo = i === idx;
        const alcanzado = idx >= 0 && i <= idx;
        return (
          <React.Fragment key={e.id}>
            <button
              type="button"
              disabled={cambiando}
              onClick={() => onCambiar(e.id)}
              title={`Cambiar a «${e.label}»`}
              className={cn(
                'flex h-6 w-6 items-center justify-center rounded-full border text-[10px] font-bold transition-colors',
                activo ? 'border-primary bg-primary text-primary-foreground' : alcanzado ? 'border-primary/50 bg-primary/15 text-primary' : 'border-input bg-background text-muted-foreground hover:border-primary/50',
              )}
            >
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

function FichaItem({ k, v }: { k: string; v?: string }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{k}</dt>
      <dd className="font-medium">{v ?? '—'}</dd>
    </div>
  );
}

export default function LeadsRadar() {
  const [leads, setLeads] = React.useState<LeadCurado[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [fEtapa, setFEtapa] = React.useState('');
  const [fLinea, setFLinea] = React.useState('');
  const [ficha, setFicha] = React.useState<LeadCurado | null>(null);
  const [notas, setNotas] = React.useState('');
  const [guardandoNotas, setGuardandoNotas] = React.useState(false);
  const [cambiandoEtapa, setCambiandoEtapa] = React.useState(false);
  const [senalOpen, setSenalOpen] = React.useState(false);
  const [senalTitulo, setSenalTitulo] = React.useState('');
  const [senalDetalle, setSenalDetalle] = React.useState('');

  const cargar = React.useCallback(() => {
    setLoading(true);
    setError(null);
    const q: Record<string, string> = { limit: '100' };
    if (fEtapa) q.etapa = fEtapa;
    if (fLinea) q.linea = fLinea;
    get<{ items?: LeadCurado[] } | LeadCurado[]>('/leads/curados', q)
      .then((r) => setLeads(Array.isArray(r) ? r : (r.items ?? [])))
      .catch((e) => setError(errorMessage(e)))
      .finally(() => setLoading(false));
  }, [fEtapa, fLinea]);

  React.useEffect(() => { cargar(); }, [cargar]);

  React.useEffect(() => { setNotas(ficha?.notas ?? ''); }, [ficha]);

  const cambiarEtapa = async (lead: LeadCurado, etapa: string) => {
    if ((lead.etapa ?? 'nuevo') === etapa) return;
    setCambiandoEtapa(true);
    try {
      await patch(`/leads/curados/${lead.lead_id}`, { etapa });
      setLeads((prev) => prev.map((l) => (l.lead_id === lead.lead_id ? { ...l, etapa } : l)));
      setFicha((f) => (f && f.lead_id === lead.lead_id ? { ...f, etapa } : f));
      toast.success(`«${lead.nombre}» → ${ETAPAS_RADAR.find((e) => e.id === etapa)?.label ?? etapa}`);
    } catch (e) {
      toast.error('No se pudo cambiar la etapa', { description: errorMessage(e) });
    } finally {
      setCambiandoEtapa(false);
    }
  };

  const guardarNotas = async () => {
    if (!ficha) return;
    setGuardandoNotas(true);
    try {
      await patch(`/leads/curados/${ficha.lead_id}`, { notas });
      setLeads((prev) => prev.map((l) => (l.lead_id === ficha.lead_id ? { ...l, notas } : l)));
      setFicha({ ...ficha, notas });
      toast.success('Notas guardadas');
    } catch (e) {
      toast.error('No se pudieron guardar las notas', { description: errorMessage(e) });
    } finally {
      setGuardandoNotas(false);
    }
  };

  const registrarSenal = async () => {
    if (!ficha) return;
    try {
      await post('/signals', { titulo: senalTitulo, detalle: senalDetalle, empresa_ref: ficha.nombre });
      setSenalOpen(false);
      setSenalTitulo('');
      setSenalDetalle('');
      toast.success('Señal registrada', { description: 'El pipeline radar-03 la procesará (+score si hay match).' });
    } catch (e) {
      toast.error('No se pudo registrar la señal', { description: errorMessage(e) });
    }
  };

  const columns = React.useMemo<ColumnDef<LeadCurado>[]>(() => [
    {
      accessorKey: 'nombre',
      header: 'Nombre',
      cell: ({ row }) => {
        const l = row.original;
        return (
          <button type="button" className="text-left font-medium text-primary hover:underline" onClick={() => setFicha(l)} title="Abrir ficha de contacto">
            {l.nombre}
          </button>
        );
      },
    },
    { accessorKey: 'giro', header: 'Giro', cell: ({ row }) => <span className="text-xs">{row.original.giro ?? '—'}</span> },
    {
      accessorKey: 'linea_recomendada',
      header: 'Línea',
      cell: ({ row }) => {
        const l = row.original.linea_recomendada ?? '';
        return (
          <Badge style={{ backgroundColor: lineaColor(l), color: '#fff' }} className="border-transparent">
            {lineaLabel(l)}
          </Badge>
        );
      },
    },
    {
      accessorKey: 'etapa',
      header: 'Etapa',
      cell: ({ row }) => <EtapaStepper lead={row.original} cambiando={cambiandoEtapa} onCambiar={(e) => cambiarEtapa(row.original, e)} />,
    },
    { header: 'Score', cell: ({ row }) => <ScoreDesglosado lead={row.original} /> },
    {
      accessorKey: 'temp_zona',
      header: 'Temp. zona',
      cell: ({ row }) => <span className="font-mono text-xs">{row.original.temp_zona !== undefined ? `${row.original.temp_zona} °C` : '—'}</span>,
    },
  ], [cambiandoEtapa]);

  const wa = ficha ? normalizarTelefono(ficha.telefono) : '';
  const linkedinUrl = ficha ? `https://www.linkedin.com/search/results/companies/?keywords=${encodeURIComponent(ficha.nombre)}` : '#';

  return (
    <>
      <div className="space-y-4">
        {error && (
          <Alert variant="destructive">
            <AlertTitle>Error al cargar leads curados</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <div className="flex flex-wrap items-center gap-2 text-sm">
          <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Etapa:</span>
          {[{ id: '', label: 'Todas' }, ...ETAPAS_RADAR].map((e) => (
            <Button key={e.id} size="sm" variant={fEtapa === e.id ? 'default' : 'outline'} className="h-7 px-2 text-xs" onClick={() => setFEtapa(e.id)}>
              {e.label}
            </Button>
          ))}
          <span className="ml-4 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Línea:</span>
          {[{ id: '', label: 'Todas' }, { id: 'koolkat', label: 'Koolkat' }, { id: 'solar', label: 'Solar' }, { id: 'evaporativa', label: 'Evaporativa' }].map((l) => (
            <Button key={l.id} size="sm" variant={fLinea === l.id ? 'default' : 'outline'} className="h-7 px-2 text-xs" onClick={() => setFLinea(l.id)}>
              {l.label}
            </Button>
          ))}
          <Button variant="ghost" size="sm" className="ml-auto h-7 text-xs" onClick={() => { cargar(); toast.info('Recargando leads…'); }}>Recargar</Button>
        </div>

        {loading ? (
          <div className="space-y-2"><Skeleton className="h-10 w-64" /><Skeleton className="h-96" /></div>
        ) : (
          <Card>
            <CardHeader><CardTitle>Pipeline comercial</CardTitle></CardHeader>
            <CardContent>
              <DataTable
                columns={columns}
                data={leads}
                searchKey="nombre"
                searchPlaceholder="Buscar por nombre…"
                pageSize={20}
                emptyText="Sin leads curados. Lanza el pipeline radar-01 en Operación para generarlos."
              />
            </CardContent>
          </Card>
        )}
      </div>

      {/* Drawer: ficha "Cómo contactarlo" */}
      <Drawer open={!!ficha} onClose={() => setFicha(null)} title="Ficha del lead">
        {ficha && (
          <div className="space-y-4 text-sm">
            <div>
              <h4 className="text-base font-semibold">{ficha.nombre}</h4>
              <p className="text-xs text-muted-foreground">{ficha.giro ?? '—'} · {ficha.direccion ?? 'Sin dirección'}</p>
              <div className="mt-2 flex gap-2">
                <Badge style={{ backgroundColor: lineaColor(ficha.linea_recomendada), color: '#fff' }} className="border-transparent">
                  {lineaLabel(ficha.linea_recomendada)}
                </Badge>
                <Badge variant={ETAPA_BADGE[(ficha.etapa ?? 'nuevo').toLowerCase()] ?? 'secondary'}>
                  {ETAPAS_RADAR.find((e) => e.id === (ficha.etapa ?? 'nuevo').toLowerCase())?.label ?? ficha.etapa}
                </Badge>
                {ficha.score !== undefined && <Badge variant="outline" className="font-mono">Score {ficha.score}</Badge>}
              </div>
            </div>
            <Separator />

            <div>
              <p className="mb-2 font-semibold">📞 Cómo contactarlo</p>
              <div className="grid grid-cols-2 gap-2">
                <a
                  href={ficha.telefono ? `tel:${ficha.telefono}` : undefined}
                  aria-disabled={!ficha.telefono}
                  className={cn(buttonVariants({ variant: 'outline', size: 'sm' }), !ficha.telefono && 'pointer-events-none opacity-50')}
                >
                  ☎️ Llamar
                </a>
                <a
                  href={wa ? `https://wa.me/${wa}` : undefined}
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-disabled={!wa}
                  className={cn(buttonVariants({ variant: 'outline', size: 'sm' }), !wa && 'pointer-events-none opacity-50')}
                >
                  💬 WhatsApp
                </a>
                <a
                  href={ficha.web ?? undefined}
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-disabled={!ficha.web}
                  className={cn(buttonVariants({ variant: 'outline', size: 'sm' }), !ficha.web && 'pointer-events-none opacity-50')}
                >
                  🌐 Abrir sitio
                </a>
                <a
                  href={linkedinUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={buttonVariants({ variant: 'outline', size: 'sm' })}
                >
                  💼 Buscar en LinkedIn
                </a>
              </div>
              <p className="mt-1 text-[11px] text-muted-foreground">
                Tel: {ficha.telefono ?? '—'} · Web: {ficha.web ?? '—'} · Rating: {ficha.rating ?? '—'}
              </p>
            </div>
            <Separator />

            <div>
              <p className="mb-2 font-semibold">Etapa del pipeline</p>
              <EtapaStepper lead={ficha} cambiando={cambiandoEtapa} onCambiar={(e) => cambiarEtapa(ficha, e)} />
            </div>
            <Separator />

            <div>
              <Field label="Notas del SDR" htmlFor="notas">
                <Textarea id="notas" value={notas} onChange={(e) => setNotas(e.target.value)} placeholder="Ej. Llamé el lunes, pidió cotización de 3 equipos…" rows={4} />
              </Field>
              <Button size="sm" className="mt-2" onClick={guardarNotas} disabled={guardandoNotas}>
                {guardandoNotas ? 'Guardando…' : 'Guardar notas'}
              </Button>
            </div>
            <Separator />

            <div className="space-y-2">
              <p className="font-semibold">Señales</p>
              <p className="text-xs text-muted-foreground">
                Registra una señal manual (ej. «vieron nuestra página», «pidieron cotización en feria»). El pipeline radar-03 la procesa y puede sumar score.
              </p>
              <Button size="sm" variant="secondary" onClick={() => setSenalOpen(true)}>➕ Registrar señal</Button>
            </div>

            {ficha.score_components && Object.keys(ficha.score_components).length > 0 && (
              <>
                <Separator />
                <div>
                  <p className="mb-1 font-semibold">Desglose del score</p>
                  <dl className="space-y-1">
                    {Object.entries(ficha.score_components).map(([k, v]) => <ComponentRow key={k} k={k} v={v} />)}
                  </dl>
                </div>
              </>
            )}

            <dl className="grid grid-cols-2 gap-x-4 gap-y-2 pt-2">
              <FichaItem k="Fuente" v={ficha.source} />
              <FichaItem k="Temp. zona" v={ficha.temp_zona !== undefined ? `${ficha.temp_zona} °C` : undefined} />
            </dl>
          </div>
        )}
      </Drawer>

      {/* Dialog: registrar señal */}
      <Dialog open={senalOpen} onOpenChange={setSenalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Registrar señal</DialogTitle>
            <DialogDescription>
              Señal manual sobre «{ficha?.nombre}». Llega a <code>warm_signals</code> vía <code>POST /signals</code>.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <Field label="Título" htmlFor="senal-t" required>
              <Input id="senal-t" value={senalTitulo} onChange={(e) => setSenalTitulo(e.target.value)} placeholder="Ej. Interacción cálida en feria" />
            </Field>
            <Field label="Detalle" htmlFor="senal-d">
              <Textarea id="senal-d" value={senalDetalle} onChange={(e) => setSenalDetalle(e.target.value)} placeholder="Qué pasó, cuándo, evidencia…" rows={3} />
            </Field>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setSenalOpen(false)}>Cancelar</Button>
            <Button onClick={registrarSenal} disabled={!senalTitulo.trim()}>Registrar</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

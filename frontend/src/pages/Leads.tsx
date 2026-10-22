import * as React from 'react';
import type { ColumnDef } from '@tanstack/react-table';
import { Topbar } from '@/components/layout/Topbar';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/Alert';
import { Skeleton } from '@/components/ui/Skeleton';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { DataTable } from '@/components/ui/DataTable';
import { Drawer } from '@/components/ui/Drawer';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/Tabs';
import { HoverCard, HoverCardContent, HoverCardTrigger } from '@/components/ui/HoverCard';
import { Progress } from '@/components/ui/Progress';
import { Separator } from '@/components/ui/Separator';
import { get, errorMessage, type Lead } from '@/lib/api';
import { estratoColor } from '@/lib/geo';
import { toast } from 'sonner';
import LeadsRadar from './LeadsRadar';

function ContactoIconos({ lead }: { lead: Lead }) {
  return (
    <span className="flex gap-1.5 text-base" aria-label="Canales de contacto">
      {lead.telefono ? <span title={lead.telefono}>☎️</span> : <span className="opacity-20" title="Sin teléfono">☎️</span>}
      {lead.correo ? <span title={lead.correo}>✉️</span> : <span className="opacity-20" title="Sin correo">✉️</span>}
      {lead.sitio_web ? <span title={lead.sitio_web}>🌐</span> : <span className="opacity-20" title="Sin sitio web">🌐</span>}
    </span>
  );
}

function ScoreBar({ lead }: { lead: Lead }) {
  const bd = lead.score_breakdown;
  return (
    <HoverCard>
      <HoverCardTrigger asChild>
        <div className="flex min-w-[7rem] cursor-default items-center gap-2">
          <Progress value={lead.score ?? 0} className="h-2 w-16" />
          <span className="font-mono text-sm font-semibold">{lead.score ?? '—'}</span>
        </div>
      </HoverCardTrigger>
      <HoverCardContent>
        <p className="mb-2 text-sm font-semibold">Desglose del score</p>
        {bd && Object.keys(bd).length ? (
          <dl className="space-y-1 text-xs">
            {Object.entries(bd).map(([k, v]) => (
              <div key={k} className="flex justify-between gap-4">
                <dt className="text-muted-foreground">{k}</dt>
                <dd className="font-mono">{typeof v === 'number' ? v.toFixed(1) : String(v)}</dd>
              </div>
            ))}
          </dl>
        ) : (
          <p className="text-xs text-muted-foreground">Sin desglose disponible.</p>
        )}
      </HoverCardContent>
    </HoverCard>
  );
}

export default function Leads() {
  const [leads, setLeads] = React.useState<Lead[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [ficha, setFicha] = React.useState<Lead | null>(null);

  const cargar = React.useCallback(() => {
    setLoading(true);
    setError(null);
    get<{ items?: Lead[]; data?: Lead[] } | Lead[]>('/leads', { limit: 100 })
      .then((r) => setLeads(Array.isArray(r) ? r : (r.items ?? r.data ?? [])))
      .catch((e) => setError(errorMessage(e)))
      .finally(() => setLoading(false));
  }, []);

  React.useEffect(() => { cargar(); }, [cargar]);

  const columns = React.useMemo<ColumnDef<Lead>[]>(() => [
    {
      accessorKey: 'razon_social',
      header: 'Razón social',
      cell: ({ row }) => {
        const l = row.original;
        const nombre = l.razon_social ?? l.nombre ?? '—';
        return (
          <button type="button" className="text-left font-medium text-primary hover:underline" onClick={() => setFicha(l)} title="Ver ficha completa">
            {nombre}
          </button>
        );
      },
    },
    {
      accessorKey: 'scian_code',
      header: 'SCIAN',
      cell: ({ row }) => <span className="font-mono text-xs">{row.original.scian_code ?? '—'}</span>,
    },
    {
      accessorKey: 'estrato',
      header: 'Estrato',
      cell: ({ row }) => (
        <Badge style={{ backgroundColor: estratoColor(row.original.estrato), color: '#fff' }} className="border-transparent">
          {row.original.estrato ?? '—'}
        </Badge>
      ),
    },
    { accessorKey: 'municipio', header: 'Municipio', cell: ({ row }) => row.original.municipio ?? '—' },
    { header: 'Contacto', cell: ({ row }) => <ContactoIconos lead={row.original} /> },
    {
      accessorKey: 'idt',
      header: 'IDT',
      cell: ({ row }) => <span className="font-mono">{row.original.idt ?? '—'}</span>,
    },
    { header: 'Score', cell: ({ row }) => <ScoreBar lead={row.original} /> },
    {
      accessorKey: 'distancia_km',
      header: 'Distancia',
      cell: ({ row }) => <span className="font-mono text-xs">{row.original.distancia_km !== undefined ? `${row.original.distancia_km.toFixed(1)} km` : '—'}</span>,
    },
    {
      accessorKey: 'estado',
      header: 'Estado',
      cell: ({ row }) => row.original.estado ? <Badge variant="outline">{row.original.estado}</Badge> : <span className="text-muted-foreground">—</span>,
    },
  ], []);

  return (
    <div className="flex h-full flex-col">
      <Topbar titulo="Leads" subtitulo="Matriz espacial (DENUE) + pipeline comercial (Radar)" />
      <Tabs defaultValue="denue" className="flex min-h-0 flex-1 flex-col">
        <div className="shrink-0 border-b px-6 pt-3">
          <TabsList>
            <TabsTrigger value="denue">🗺️ Espaciales (DENUE)</TabsTrigger>
            <TabsTrigger value="radar">🎯 Curados (Radar)</TabsTrigger>
          </TabsList>
        </div>
        <TabsContent value="denue" className="m-0 min-h-0 flex-1 overflow-y-auto p-6">
          {error && (
            <Alert variant="destructive" className="mb-4">
              <AlertTitle>Error al cargar leads</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          {loading ? (
            <div className="space-y-2"><Skeleton className="h-10 w-64" /><Skeleton className="h-96" /></div>
          ) : (
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle>Matriz de scoring</CardTitle>
                <Button variant="outline" size="sm" onClick={() => { cargar(); toast.info('Recargando leads…'); }}>
                  Recargar
                </Button>
              </CardHeader>
              <CardContent>
                <DataTable
                  columns={columns}
                  data={leads}
                  searchKey="razon_social"
                  searchPlaceholder="Buscar por razón social…"
                  pageSize={20}
                  emptyText="Sin leads. Ajusta los filtros del territorio o dibuja un polígono en el Mapa."
                />
              </CardContent>
            </Card>
          )}
        </TabsContent>
        <TabsContent value="radar" className="m-0 min-h-0 flex-1 overflow-y-auto p-6">
          <LeadsRadar />
        </TabsContent>
      </Tabs>

      <Drawer open={!!ficha} onClose={() => setFicha(null)} title="Ficha del establecimiento">
        {ficha && (
          <div className="space-y-4 text-sm">
            <div>
              <h4 className="text-base font-semibold">{ficha.razon_social ?? ficha.nombre}</h4>
              <p className="font-mono text-xs text-muted-foreground">DENUE: {ficha.denue_id ?? '—'}</p>
            </div>
            <Separator />
            <dl className="grid grid-cols-2 gap-x-4 gap-y-2">
              <FichaItem k="SCIAN" v={ficha.scian_code} />
              <FichaItem k="Estrato" v={ficha.estrato} />
              <FichaItem k="Municipio" v={ficha.municipio} />
              <FichaItem k="IDT" v={ficha.idt !== undefined ? String(ficha.idt) : undefined} />
              <FichaItem k="Score" v={ficha.score !== undefined ? String(ficha.score) : undefined} />
              <FichaItem k="Estado" v={ficha.estado} />
            </dl>
            <div>
              <p className="mb-1 font-semibold">Domicilio</p>
              <p className="text-muted-foreground">{ficha.direccion ?? 'No disponible'}</p>
            </div>
            <div>
              <p className="mb-1 font-semibold">Contacto</p>
              <p className="text-muted-foreground">Tel: {ficha.telefono || '— (el DENUE no lo trae)'}</p>
              <p className="text-muted-foreground">Correo: {ficha.correo || '—'}</p>
              <p className="text-muted-foreground">Web: {ficha.sitio_web || '—'}</p>
              <p className="mt-1 text-xs text-muted-foreground">GEIS nunca inventa datos de contacto: los campos vacíos viajan vacíos.</p>
            </div>
            {ficha.score_breakdown && (
              <div>
                <p className="mb-1 font-semibold">Desglose del score</p>
                <dl className="space-y-1">
                  {Object.entries(ficha.score_breakdown).map(([k, v]) => (
                    <div key={k} className="flex justify-between text-xs">
                      <dt className="text-muted-foreground">{k}</dt>
                      <dd className="font-mono">{typeof v === 'number' ? v.toFixed(1) : String(v)}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            )}
          </div>
        )}
      </Drawer>
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

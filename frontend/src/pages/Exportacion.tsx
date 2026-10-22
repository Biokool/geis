import * as React from 'react';
import { Topbar } from '@/components/layout/Topbar';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Field } from '@/components/ui/Field';
import { Empty } from '@/components/ui/Empty';
import { Separator } from '@/components/ui/Separator';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/Tooltip';
import { downloadBlob } from '@/lib/geo';
import { apiBlob, errorMessage } from '@/lib/api';
import { useGeisStore } from '@/store';
import { toast } from 'sonner';

const SIN_ENDPOINT = 'Fase 2: el backend aún no expone este endpoint, así que la acción está deshabilitada.';

/** Botón deshabilitado con explicación (regla: cero botones muertos). */
function BotonPendiente({ children, motivo = SIN_ENDPOINT }: { children: React.ReactNode; motivo?: string }) {
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <span className="inline-flex cursor-not-allowed">
            <Button disabled aria-disabled="true">{children}</Button>
          </span>
        </TooltipTrigger>
        <TooltipContent className="max-w-xs">{motivo}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

export default function Exportacion() {
  const territorio = useGeisStore((s) => s.territorio);
  const [reportId, setReportId] = React.useState('');
  const [crmUrl, setCrmUrl] = React.useState('');
  const [error, setError] = React.useState<string | null>(null);
  const [exportando, setExportando] = React.useState(false);

  /** Exportación real vía POST /leads/export (CSV con IDT y score calculados). */
  const exportarCsv = async () => {
    setExportando(true);
    setError(null);
    try {
      const blob = await apiBlob('/leads/export', { method: 'POST', query: { formato: 'csv' } });
      downloadBlob(blob, `leads-${new Date().toISOString().slice(0, 10)}.csv`, 'text/csv');
      toast.success('Exportación de leads lista');
    } catch (e) {
      const msg = errorMessage(e);
      setError(msg);
      toast.error('Falló la exportación', { description: msg });
    } finally {
      setExportando(false);
    }
  };

  const exportarTerritorio = () => {
    if (!territorio?.geojson) { toast.warning('No hay territorio activo'); return; }
    try {
      downloadBlob(
        JSON.stringify({ type: 'FeatureCollection', features: [{ type: 'Feature', properties: { nombre: territorio.nombre }, geometry: territorio.geojson }] }, null, 2),
        `${territorio.nombre.replace(/\s+/g, '-').toLowerCase()}.geojson`,
        'application/geo+json',
      );
      toast.success('Territorio exportado como GeoJSON');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo exportar el territorio.');
    }
  };

  return (
    <div className="flex h-full flex-col">
      <Topbar titulo="Centro de exportación" subtitulo="Territorio · leads · PDF · CRM" />
      <div className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-4xl space-y-6">
          {error && <Alert variant="destructive"><AlertTitle>Error</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>}

          <Card>
            <CardHeader>
              <CardTitle>Territorio (GeoJSON)</CardTitle>
              <CardDescription>Geometría del territorio activo para usarla en otros sistemas.</CardDescription>
            </CardHeader>
            <CardContent>
              {territorio?.geojson ? (
                <div className="flex flex-wrap items-center gap-3">
                  <p className="text-sm">Territorio activo: <strong>{territorio.nombre}</strong></p>
                  <Button variant="outline" onClick={exportarTerritorio}>Descargar GeoJSON</Button>
                </div>
              ) : (
                <Empty title="Sin territorio activo" description="Dibuja un polígono en el Mapa o guárdalo en Geofencing para exportarlo." icon="⬡" />
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Reporte en PDF</CardTitle>
              <CardDescription>Portada + 13 secciones + fuentes citadas.</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-wrap items-end gap-3">
              <Field label="ID del reporte" htmlFor="rid" className="min-w-[16rem] flex-1">
                <Input id="rid" placeholder="rep_01H…" value={reportId} onChange={(e) => setReportId(e.target.value)} />
              </Field>
              <BotonPendiente motivo="Fase 2: aún no existe el endpoint GET /reports/{id}/pdf en el backend.">
                Descargar PDF
              </BotonPendiente>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Leads (CSV / Excel)</CardTitle>
              <CardDescription>Columnas configurables · incluye denue_id como llave externa estable.</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap items-center gap-3">
                <Button onClick={exportarCsv} disabled={exportando}>
                  {exportando ? 'Exportando…' : 'Exportar leads (CSV)'}
                </Button>
                <BotonPendiente motivo="Fase 2: el endpoint POST /leads/export aún no genera Excel (responde 501 honesto).">
                  Excel
                </BotonPendiente>
                <p className="text-xs text-muted-foreground">CSV con IDT y score calculados · hasta 5,000 filas.</p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Sincronización con CRM</CardTitle>
              <CardDescription>Envío en lote con idempotencia por (crm, denue_id).</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-wrap items-end gap-3">
              <Field label="Webhook del CRM" htmlFor="crm" hint="HubSpot, Salesforce o webhook genérico" className="min-w-[16rem] flex-1">
                <Input id="crm" placeholder="https://…" value={crmUrl} onChange={(e) => setCrmUrl(e.target.value)} />
              </Field>
              <BotonPendiente motivo="Fase 2: aún no existe el endpoint POST /leads/sync en el backend.">
                Sincronizar leads
              </BotonPendiente>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>API keys personales</CardTitle>
              <CardDescription>Conecta GEIS a tu flujo comercial.</CardDescription>
            </CardHeader>
            <CardContent>
              <Empty
                title="Fase 2 — API keys"
                description="La gestión de llaves personales aún no tiene endpoint en el backend, así que no se puede administrar desde aquí."
                icon="🔑"
              />
            </CardContent>
          </Card>
          <Separator />
        </div>
      </div>
    </div>
  );
}

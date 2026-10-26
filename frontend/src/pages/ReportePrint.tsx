import * as React from 'react';
import { useParams } from 'react-router-dom';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Spinner } from '@/components/ui/Spinner';
import { getReport, getInvestigation, errorMessage, type ReportOutS1 } from '@/lib/api';
import { ReporteCuerpo, type ReportPayloadFull } from './Reporte';

/**
 * Vista imprimible del reporte (`/reporte/:id/imprimir`).
 * El botón «PDF» del reporte navega aquí; el usuario guarda con
 * «Guardar como PDF» del diálogo de impresión del navegador.
 */
export default function ReportePrint() {
  const { id } = useParams<{ id: string }>();
  const [reporte, setReporte] = React.useState<ReportOutS1 | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [invTipo, setInvTipo] = React.useState<string | null>(null);
  const impresoRef = React.useRef(false);

  React.useEffect(() => {
    if (!id) return;
    let vivo = true;
    getReport(id)
      .then((r) => { if (vivo) setReporte(r); })
      .catch((e) => { if (vivo) setError(errorMessage(e)); });
    try {
      const invId = localStorage.getItem(`geis:reporte-inv:${id}`);
      if (invId) {
        getInvestigation(invId)
          .then((inv) => { if (vivo) setInvTipo(inv.investigation_type ?? null); })
          .catch(() => { /* modo normal */ });
      }
    } catch { /* localStorage no disponible */ }
    return () => { vivo = false; };
  }, [id]);

  // Impresión automática al terminar de cargar (con botón manual de respaldo).
  React.useEffect(() => {
    if (!reporte || impresoRef.current) return;
    impresoRef.current = true;
    const t = window.setTimeout(() => window.print(), 700);
    return () => window.clearTimeout(t);
  }, [reporte]);

  const payload = reporte?.payload as ReportPayloadFull | undefined;

  return (
    <div className="mx-auto max-w-4xl p-6 print:p-0">
      <style>{`
        @media print {
          aside, nav, header[data-sidebar], .no-print { display: none !important; }
          body { background: #fff !important; }
          .print-root { padding: 0 !important; max-width: 100% !important; }
          .print-root .leaflet-container { display: none !important; }
        }
      `}</style>
      <div className="no-print mb-4 flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-muted-foreground">Vista para impresión — usa «Guardar como PDF» en el diálogo de tu navegador.</p>
        <Button onClick={() => window.print()}>Imprimir / Guardar PDF</Button>
      </div>

      {!reporte && !error && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground"><Spinner size={16} /> Cargando reporte para imprimir…</div>
      )}
      {error && (
        <Alert variant="destructive">
          <AlertTitle>No se pudo cargar el reporte</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {reporte && payload && (
        <div className="print-root">
          <ReporteCuerpo payload={payload} interactivo={false} modoInmobiliario={invTipo === 'real_estate'} />
          <p className="mt-6 font-mono text-xs text-muted-foreground">ID del reporte: {reporte.report_id} · Generado con GEIS (fuentes nominales en la sección «Fuentes y datos utilizados»).</p>
        </div>
      )}
    </div>
  );
}

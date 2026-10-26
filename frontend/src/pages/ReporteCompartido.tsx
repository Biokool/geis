import * as React from 'react';
import { useParams } from 'react-router-dom';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/Alert';
import { Card, CardContent } from '@/components/ui/Card';
import { Spinner } from '@/components/ui/Spinner';
import { ApiError, getSharedReport, type SharedReport } from '@/lib/api';
import { ReporteCuerpo, type ReportPayloadFull } from './Reporte';

/** Vista pública de solo lectura de un reporte compartido (`/r/:token`). */
export default function ReporteCompartido() {
  const { token } = useParams<{ token: string }>();
  const [datos, setDatos] = React.useState<SharedReport | null>(null);
  const [noDisponible, setNoDisponible] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!token) return;
    let vivo = true;
    getSharedReport(token)
      .then((d) => { if (vivo) setDatos(d); })
      .catch((e) => {
        if (!vivo) return;
        if (e instanceof ApiError && e.status === 404) setNoDisponible(true);
        else setError(e instanceof Error ? e.message : 'Ocurrió un error inesperado.');
      });
    return () => { vivo = false; };
  }, [token]);

  if (noDisponible) {
    return (
      <div className="mx-auto flex min-h-[60vh] max-w-lg items-center p-6">
        <Card className="w-full">
          <CardContent className="space-y-2 py-10 text-center">
            <p className="text-4xl" aria-hidden>🔒</p>
            <p className="text-lg font-semibold">Este enlace ya no está disponible</p>
            <p className="text-sm text-muted-foreground">
              El link pudo expirar, haber sido revocado por quien lo compartió, o no existir.
              Pide a la persona que te lo envió que genere un link invitado nuevo desde su reporte.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-lg p-6">
        <Alert variant="destructive">
          <AlertTitle>No se pudo abrir el reporte compartido</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      </div>
    );
  }

  if (!datos) {
    return (
      <div className="mx-auto flex max-w-lg items-center gap-2 p-6 text-sm text-muted-foreground">
        <Spinner size={16} /> Cargando reporte compartido…
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl space-y-4 p-6">
      <p className="text-xs text-muted-foreground">
        Vista de solo lectura compartida con un link invitado de GEIS.
        {datos.expira_en && ` El enlace vence el ${new Date(datos.expira_en).toLocaleDateString('es-MX')}.`}
      </p>
      <ReporteCuerpo payload={datos.payload as ReportPayloadFull} interactivo={false} />
    </div>
  );
}

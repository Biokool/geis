import { Topbar } from '@/components/layout/Topbar';
import { Empty } from '@/components/ui/Empty';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/Alert';

export default function Comparador() {
  return (
    <div className="flex h-full flex-col">
      <Topbar titulo="Comparador multi-ubicación" subtitulo="Tabla comparativa de ubicaciones candidatas" />
      <div className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-3xl space-y-4">
          <Empty
            title="Fase 2 — Comparador multi-ubicación"
            description="El comparador (tabla de N ubicaciones con veredicto, ISM, TAM, competencia, población, NSE y score Huff; SRS §6.6) aún no está implementado en el backend. No hay endpoint de comparación disponible, así que no hay nada que mostrar todavía."
            icon="⚖️"
          />
          <Alert variant="info">
            <AlertTitle>Qué incluirá cuando exista</AlertTitle>
            <AlertDescription>
              Columnas = ubicaciones, filas = métricas, celdas con semáforo y botón «elegir ganadora» que la promueve a investigación principal. Equivale a los planes Cazador/Pro de la plataforma de referencia.
            </AlertDescription>
          </Alert>
        </div>
      </div>
    </div>
  );
}

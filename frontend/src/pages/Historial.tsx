import * as React from 'react';
import { useNavigate } from 'react-router-dom';
import { Topbar } from '@/components/layout/Topbar';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/Alert';
import { Skeleton } from '@/components/ui/Skeleton';
import { Empty } from '@/components/ui/Empty';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Spinner } from '@/components/ui/Spinner';
import { Checkbox } from '@/components/ui/Checkbox';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/AlertDialog';
import { get, post, deleteInvestigation, errorMessage, type Investigation } from '@/lib/api';
import { verdictColor } from '@/lib/geo';
import { toast } from 'sonner';

export default function Historial() {
  const navigate = useNavigate();
  const [items, setItems] = React.useState<Investigation[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [procesando, setProcesando] = React.useState<string | null>(null);
  const [compararSel, setCompararSel] = React.useState<string[]>(() => { try { const r = localStorage.getItem('geis:comparar'); return r ? (JSON.parse(r) as string[]) : []; } catch { return []; } });
  const [borrarId, setBorrarId] = React.useState<string | null>(null);
  const [borrando, setBorrando] = React.useState(false);

  const cargar = React.useCallback(() => {
    setLoading(true);
    setError(null);
    get<{ items?: Investigation[]; data?: Investigation[] } | Investigation[]>('/investigations')
      .then((r) => setItems(Array.isArray(r) ? r : (r.items ?? r.data ?? [])))
      .catch((e) => setError(errorMessage(e)))
      .finally(() => setLoading(false));
  }, []);

  React.useEffect(() => { cargar(); }, [cargar]);

  /** Re-ejecución = clonar la investigación (el backend no tiene /rerun). */
  const reejecutar = async (inv: Investigation) => {
    const id = inv.investigation_id;
    setProcesando(id);
    try {
      await post('/investigations', {
        title: `${inv.title ?? 'Investigación'} (re-ejecución)`,
        investigation_type: inv.investigation_type ?? 'location_viability',
        vertical: inv.vertical ?? null,
        territory_kind: inv.territory_kind ?? 'point_buffers',
        center_lat: inv.center_lat ?? null,
        center_lon: inv.center_lon ?? null,
        radii_m: inv.radii_m ?? [1000, 2000],
        params: { ...(inv.params ?? {}), clonada_de: id },
      });
      toast.success('Investigación re-ejecutada', { description: 'Se clonó como una nueva investigación.' });
      cargar();
    } catch (e) {
      toast.error('No se pudo re-ejecutar', { description: errorMessage(e) });
    } finally {
      setProcesando(null);
    }
  };

  const toggleComparar = (id: string, checked: boolean) => {
    setCompararSel((prev) => {
      let next: string[];
      if (checked) {
        if (prev.length >= 5) { toast.warning('Máximo 5 para comparar', { description: 'Ya tienes 5 seleccionadas; desmarca una.' }); return prev; }
        next = [...prev, id];
      } else {
        next = prev.filter((x) => x !== id);
      }
      try { localStorage.setItem('geis:comparar', JSON.stringify(next)); } catch { /* sin persistencia */ }
      return next;
    });
  };

  const confirmarBorrado = async () => {
    if (!borrarId) return;
    setBorrando(true);
    try {
      await deleteInvestigation(borrarId);
      toast.success('Investigación eliminada');
      setCompararSel((prev) => { const n = prev.filter((x) => x !== borrarId); try { localStorage.setItem('geis:comparar', JSON.stringify(n)); } catch { /* noop */ } return n; });
      setBorrarId(null);
      cargar();
    } catch (e) {
      toast.error('No se pudo eliminar', { description: errorMessage(e) });
    } finally { setBorrando(false); }
  };

  return (
    <div className="flex h-full flex-col">
      <Topbar titulo="Historial de investigaciones" subtitulo="Cronología con veredicto, edición de datos y re-ejecución" />
      <div className="flex-1 overflow-y-auto p-6">
        {items.length > 0 && (
          <div className="mb-4 flex flex-wrap items-center gap-3">
            <Button size="sm" disabled={compararSel.length < 2} onClick={() => navigate('/comparador')}>
              Comparar selección ({compararSel.length})
            </Button>
            <span className="text-xs text-muted-foreground">Marca «Comparar» en hasta 5 tarjetas. La selección se guarda en este navegador.</span>
          </div>
        )}
        {error && (
          <Alert variant="destructive" className="mb-4">
            <AlertTitle>Error</AlertTitle>
            <AlertDescription>
              <p className="mb-2">{error}</p>
              <Button variant="outline" size="sm" onClick={cargar}>Reintentar</Button>
            </AlertDescription>
          </Alert>
        )}
        {loading ? (
          <div className="space-y-3">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-28" />)}</div>
        ) : items.length === 0 ? (
          <Empty
            title="Sin investigaciones guardadas"
            description="Genera un reporte o analiza un polígono en el Mapa y guárdalo para verlo aquí con su linaje de datos."
            icon="🕘"
            action={{ label: 'Ir al mapa', onClick: () => navigate('/mapa') }}
          />
        ) : (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {items.map((inv) => {
              const id = inv.investigation_id;
              const titulo = inv.title ?? `Investigación ${id.slice(0, 8)}`;
              const ediciones = inv.lineage?.editions;
              return (
                <Card key={id}>
                  <CardHeader className="pb-2">
                    <div className="flex items-start justify-between gap-2">
                      <CardTitle className="text-base">{titulo}</CardTitle>
                      {inv.verdict && (
                        <Badge style={{ backgroundColor: verdictColor(inv.verdict), color: '#fff' }} className="shrink-0 border-transparent">
                          {inv.verdict}
                        </Badge>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {inv.investigation_type ?? 'análisis'} · {inv.created_at ? new Date(inv.created_at).toLocaleString('es-MX') : 'fecha desconocida'}
                    </p>
                  </CardHeader>
                  <CardContent className="space-y-3 text-sm">
                    <p className="text-xs text-muted-foreground">
                      Datos: {Array.isArray(ediciones) && ediciones.length ? ediciones.join(', ') : 'edición desconocida'}
                      {inv.lineage?.model_version && ` · modelos ${inv.lineage.model_version}`}
                    </p>
                    {inv.scores && Object.keys(inv.scores).length > 0 && (
                      <dl className="grid grid-cols-2 gap-1 text-xs">
                        {Object.entries(inv.scores).slice(0, 4).map(([k, v]) => (
                          <div key={k} className="flex justify-between gap-2">
                            <dt className="text-muted-foreground">{k}</dt>
                            <dd className="font-mono">{String(v)}</dd>
                          </div>
                        ))}
                      </dl>
                    )}
                    <div className="flex flex-wrap gap-2 pt-1">
                      <Button size="sm" variant="outline" disabled={procesando === id} onClick={() => reejecutar(inv)}>
                        {procesando === id && <Spinner size={14} />}
                        Re-ejecutar
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => navigate(`/mapa?inv=${id}`)}>Ver en mapa</Button>
                      <Button size="sm" variant="outline" onClick={() => navigate(`/reporte?id=${id}`)}>Reporte</Button>
                      <label className="flex cursor-pointer items-center gap-2 text-xs">
                        <Checkbox checked={compararSel.includes(id)} onCheckedChange={(c) => toggleComparar(id, c === true)} />
                        Comparar
                      </label>
                      <Button size="sm" variant="ghost" className="text-destructive" onClick={() => setBorrarId(id)}>
                        Borrar
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}
      </div>
      <AlertDialog open={!!borrarId} onOpenChange={(o) => { if (!o) setBorrarId(null); }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>¿Eliminar esta investigación?</AlertDialogTitle>
            <AlertDialogDescription>Esta acción borra la investigación del servidor y no se puede deshacer.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={borrando}>Cancelar</AlertDialogCancel>
            <AlertDialogAction onClick={(e) => { e.preventDefault(); confirmarBorrado(); }} disabled={borrando} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
              {borrando ? 'Eliminando…' : 'Eliminar'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

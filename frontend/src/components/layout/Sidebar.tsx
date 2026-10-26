import * as React from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { useGeisStore } from '@/store';
import { Badge } from '@/components/ui/Badge';
import { getLeadsCount } from '@/lib/api';

type NavItem = { to: string; label: string; icon: string };
type Seccion = 'ubicaciones' | 'radar';

const CLAVE_SECCION = 'geis:seccion';

const INICIO: NavItem = { to: '/', label: 'Inicio', icon: '🏠' };

const UBICACIONES: NavItem[] = [
  { to: '/analizar', label: 'Analizar', icon: '🔍' },
  { to: '/reporte', label: 'Reporte', icon: '📄' },
  { to: '/mapa', label: 'Mapa', icon: '🗺️' },
  { to: '/comparador', label: 'Comparador', icon: '⚖️' },
  { to: '/historial', label: 'Historial', icon: '🕘' },
  { to: '/aprende', label: 'Aprende', icon: '🎓' },
];

const RADAR: NavItem[] = [
  { to: '/panel-radar', label: 'Panel Radar', icon: '🎯' },
  { to: '/operacion', label: 'Operación', icon: '⚙️' },
  { to: '/leads', label: 'Leads', icon: '👥' },
  { to: '/mapa?modo=radar', label: 'Mapa Radar', icon: '📡' },
  { to: '/kpis', label: 'KPIs', icon: '📊' },
  { to: '/geofencing', label: 'Geofencing', icon: '⬡' },
  { to: '/exportacion', label: 'Exportación', icon: '📤' },
];

const SISTEMA: NavItem[] = [
  { to: '/sistema', label: 'Sistema', icon: '🖥️' },
  { to: '/configuracion', label: 'Configuración', icon: '🛠️' },
  { to: '/asistente', label: 'Asistente IA', icon: '🤖' },
];

const PRIMERA_DE: Record<Seccion, string> = {
  ubicaciones: '/analizar',
  radar: '/panel-radar',
};

function seccionGuardada(): Seccion {
  try {
    return localStorage.getItem(CLAVE_SECCION) === 'radar' ? 'radar' : 'ubicaciones';
  } catch {
    return 'ubicaciones';
  }
}

/** Sección a la que pertenece una ruta; null = ruta común (Inicio / Sistema). */
function seccionDeRuta(pathname: string, search: string): Seccion | null {
  if (pathname === '/mapa') {
    return new URLSearchParams(search).get('modo') === 'radar' ? 'radar' : 'ubicaciones';
  }
  if (RADAR.some((i) => i.to.split('?')[0] === pathname)) return 'radar';
  if (UBICACIONES.some((i) => i.to === pathname)) return 'ubicaciones';
  return null;
}

function pertenece(item: NavItem, pathname: string, search: string): boolean {
  if (item.to === '/mapa?modo=radar') {
    return pathname === '/mapa' && new URLSearchParams(search).get('modo') === 'radar';
  }
  if (item.to === '/mapa') {
    return pathname === '/mapa' && new URLSearchParams(search).get('modo') !== 'radar';
  }
  return item.to === pathname;
}

function Item({
  item, onNavegar, leadsTotal,
}: {
  item: NavItem; onNavegar?: () => void; leadsTotal?: number | null;
}) {
  const location = useLocation();
  const activoEspecial = item.to.includes('?') || item.to === '/mapa'
    ? pertenece(item, location.pathname, location.search)
    : undefined;
  return (
    <NavLink
      to={item.to}
      end={item.to === '/'}
      onClick={onNavegar}
      className={({ isActive }) =>
        cn(
          'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-muted',
          (activoEspecial ?? isActive) ? 'bg-primary/10 text-primary' : 'text-muted-foreground',
        )
      }
    >
      <span className="text-base" aria-hidden>{item.icon}</span>
      <span className="flex-1">{item.label}</span>
      {item.to === '/leads' && leadsTotal != null && leadsTotal > 0 && (
        <Badge variant="secondary" className="ml-auto text-[11px]">{leadsTotal}</Badge>
      )}
    </NavLink>
  );
}

export function SidebarNav({ onNavegar }: { onNavegar?: () => void }) {
  const territorio = useGeisStore((s) => s.territorio);
  const [leadsTotal, setLeadsTotal] = React.useState<number | null>(null);
  const [seccion, setSeccion] = React.useState<Seccion>(seccionGuardada);
  const location = useLocation();
  const navigate = useNavigate();

  React.useEffect(() => {
    let vivo = true;
    getLeadsCount()
      .then((r) => { if (vivo) setLeadsTotal(r.total); })
      .catch(() => { if (vivo) setLeadsTotal(null); });
    return () => { vivo = false; };
  }, []);

  // La ruta manda: si se llega por enlace directo a una página de la otra
  // sección, el selector se sincroniza con ella.
  React.useEffect(() => {
    const deRuta = seccionDeRuta(location.pathname, location.search);
    if (deRuta && deRuta !== seccion) {
      setSeccion(deRuta);
      try { localStorage.setItem(CLAVE_SECCION, deRuta); } catch { /* sin storage */ }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname, location.search]);

  const cambiarSeccion = (s: Seccion) => {
    setSeccion(s);
    try { localStorage.setItem(CLAVE_SECCION, s); } catch { /* sin storage */ }
    const deRuta = seccionDeRuta(location.pathname, location.search);
    if (deRuta !== s) {
      navigate(PRIMERA_DE[s]);
    }
    onNavegar?.();
  };

  const itemsSeccion = seccion === 'radar' ? RADAR : UBICACIONES;

  return (
    <div className="flex h-full flex-col">
      <div className="p-2 pb-0">
        <div
          className="grid grid-cols-2 gap-1 rounded-lg bg-muted p-1"
          role="tablist"
          aria-label="Sección del sistema"
        >
          <button
            type="button"
            role="tab"
            aria-selected={seccion === 'ubicaciones'}
            onClick={() => cambiarSeccion('ubicaciones')}
            className={cn(
              'rounded-md px-2 py-1.5 text-xs font-semibold transition-colors',
              seccion === 'ubicaciones' ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground',
            )}
          >
            📍 Ubicaciones
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={seccion === 'radar'}
            onClick={() => cambiarSeccion('radar')}
            className={cn(
              'rounded-md px-2 py-1.5 text-xs font-semibold transition-colors',
              seccion === 'radar' ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground',
            )}
          >
            🎯 Radar
          </button>
        </div>
      </div>
      <nav className="flex-1 space-y-1 overflow-y-auto p-2" aria-label="Navegación principal">
        <Item item={INICIO} onNavegar={onNavegar} leadsTotal={leadsTotal} />
        <div>
          <p className="px-3 pb-1 pt-3 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            {seccion === 'radar' ? 'Radar · Biokool' : 'Ubicaciones'}
          </p>
          {itemsSeccion.map((item) => (
            <Item key={item.to} item={item} onNavegar={onNavegar} leadsTotal={leadsTotal} />
          ))}
        </div>
        <div>
          <p className="px-3 pb-1 pt-3 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Sistema</p>
          {SISTEMA.map((item) => (
            <Item key={item.to} item={item} onNavegar={onNavegar} leadsTotal={leadsTotal} />
          ))}
        </div>
      </nav>
      <div className="border-t p-3">
        <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Territorio</p>
        <p className="mt-1 truncate text-sm font-medium" title={territorio?.nombre}>
          {territorio?.nombre ?? 'Sin territorio activo'}
        </p>
      </div>
    </div>
  );
}

export function Sidebar() {
  return (
    <aside className="hidden h-full w-60 shrink-0 flex-col border-r bg-card md:flex">
      <div className="flex items-center gap-2 border-b p-4">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-geis-primary text-lg font-bold text-white">G</div>
        <div>
          <p className="text-sm font-bold leading-none">GEIS</p>
          <p className="text-[11px] text-muted-foreground">Geomarketing MX</p>
        </div>
      </div>
      <div className="min-h-0 flex-1">
        <SidebarNav />
      </div>
    </aside>
  );
}

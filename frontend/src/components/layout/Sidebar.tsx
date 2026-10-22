import * as React from 'react';
import { NavLink } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { useGeisStore } from '@/store';
import { Badge } from '@/components/ui/Badge';
import { getLeadsCount } from '@/lib/api';

type NavItem = { to: string; label: string; icon: string };

const INICIO: NavItem = { to: '/', label: 'Inicio', icon: '🏠' };

const GRUPOS: { titulo: string; items: NavItem[] }[] = [
  {
    titulo: '1 · Inteligencia',
    items: [
      { to: '/mapa', label: 'Mapa', icon: '🗺️' },
      { to: '/reporte', label: 'Reporte', icon: '📄' },
      { to: '/comparador', label: 'Comparador', icon: '⚖️' },
      { to: '/historial', label: 'Historial', icon: '🕘' },
    ],
  },
  {
    titulo: '2 · Prospección',
    items: [
      { to: '/leads', label: 'Leads', icon: '🎯' },
      { to: '/kpis', label: 'KPIs', icon: '📊' },
    ],
  },
  {
    titulo: '3 · Operación',
    items: [
      { to: '/operacion', label: 'Operación', icon: '⚙️' },
      { to: '/geofencing', label: 'Geofencing', icon: '⬡' },
      { to: '/exportacion', label: 'Exportación', icon: '📤' },
    ],
  },
  {
    titulo: '4 · Sistema',
    items: [
      { to: '/sistema', label: 'Sistema', icon: '🖥️' },
      { to: '/configuracion', label: 'Configuración', icon: '🛠️' },
      { to: '/asistente', label: 'Asistente IA', icon: '🤖' },
    ],
  },
];

function Item({ item, onNavegar, leadsTotal }: { item: NavItem; onNavegar?: () => void; leadsTotal?: number | null }) {
  return (
    <NavLink
      to={item.to}
      end={item.to === '/'}
      onClick={onNavegar}
      className={({ isActive }) =>
        cn(
          'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-muted',
          isActive ? 'bg-primary/10 text-primary' : 'text-muted-foreground',
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

  React.useEffect(() => {
    let vivo = true;
    getLeadsCount()
      .then((r) => { if (vivo) setLeadsTotal(r.total); })
      .catch(() => { if (vivo) setLeadsTotal(null); });
    return () => { vivo = false; };
  }, []);

  return (
    <div className="flex h-full flex-col">
      <nav className="flex-1 space-y-1 overflow-y-auto p-2" aria-label="Navegación principal">
        <Item item={INICIO} onNavegar={onNavegar} leadsTotal={leadsTotal} />
        {GRUPOS.map((g) => (
          <div key={g.titulo}>
            <p className="px-3 pb-1 pt-3 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">{g.titulo}</p>
            {g.items.map((item) => (
              <Item key={item.to} item={item} onNavegar={onNavegar} leadsTotal={leadsTotal} />
            ))}
          </div>
        ))}
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

import { NavLink } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { useGeisStore } from '@/store';

const NAV = [
  { to: '/', label: 'Inicio', icon: '🏠' },
  { to: '/mapa', label: 'Mapa', icon: '🗺️' },
  { to: '/kpis', label: 'KPIs', icon: '📊' },
  { to: '/leads', label: 'Leads', icon: '🎯' },
  { to: '/reporte', label: 'Reporte', icon: '📄' },
  { to: '/comparador', label: 'Comparador', icon: '⚖️' },
  { to: '/historial', label: 'Historial', icon: '🕘' },
  { to: '/geofencing', label: 'Geofencing', icon: '⬡' },
  { to: '/exportacion', label: 'Exportación', icon: '📤' },
  { to: '/operacion', label: 'Operación', icon: '⚙️' },
  { to: '/sistema', label: 'Sistema', icon: '🖥️' },
];

const NAV_SISTEMA = [
  { to: '/configuracion', label: 'Configuración', icon: '🛠️' },
  { to: '/asistente', label: 'Asistente IA', icon: '🤖' },
];

function Enlaces({ items, onNavegar }: { items: typeof NAV; onNavegar?: () => void }) {
  return (
    <>
      {items.map((item) => (
        <NavLink
          key={item.to}
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
          {item.label}
        </NavLink>
      ))}
    </>
  );
}

/** Contenido de navegación, reutilizado en el drawer móvil. */
export function SidebarNav({ onNavegar }: { onNavegar?: () => void }) {
  const territorio = useGeisStore((s) => s.territorio);
  return (
    <div className="flex h-full flex-col">
      <nav className="flex-1 space-y-1 overflow-y-auto p-2" aria-label="Navegación principal">
        <Enlaces items={NAV} onNavegar={onNavegar} />
        <p className="px-3 pb-1 pt-3 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          Sistema
        </p>
        <Enlaces items={NAV_SISTEMA} onNavegar={onNavegar} />
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

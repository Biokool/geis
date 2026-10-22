import * as React from 'react';
import { useGeisStore } from '@/store';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from '@/components/ui/Tooltip';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/Sheet';
import { ThemeToggle } from './ThemeToggle';
import { SidebarNav } from './Sidebar';

export function Topbar({ titulo, subtitulo }: { titulo: string; subtitulo?: string }) {
  const territorio = useGeisStore((s) => s.territorio);
  const setTerritorio = useGeisStore((s) => s.setTerritorio);
  const usuario = useGeisStore((s) => s.usuario);
  const [menuAbierto, setMenuAbierto] = React.useState(false);

  return (
    <header className="flex h-16 shrink-0 items-center justify-between border-b bg-card px-4 md:px-6">
      <div className="flex min-w-0 items-center gap-2">
        <Button
          variant="ghost"
          size="icon"
          className="shrink-0 md:hidden"
          onClick={() => setMenuAbierto(true)}
          aria-label="Abrir menú de navegación"
        >
          ☰
        </Button>
        <div className="min-w-0">
          <h1 className="truncate text-[20px] font-semibold tracking-tight">{titulo}</h1>
          {subtitulo && <p className="truncate text-xs text-muted-foreground">{subtitulo}</p>}
        </div>
      </div>
      <div className="flex items-center gap-2">
        {territorio ? (
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Badge variant="accent" className="hidden cursor-default sm:inline-flex">
                  ⬡ {territorio.nombre}
                </Badge>
              </TooltipTrigger>
              <TooltipContent>
                Territorio activo{tipoStr(territorio.tipo)}{areaStr(territorio.area_km2)}
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        ) : (
          <Badge variant="outline" className="hidden sm:inline-flex">Sin territorio</Badge>
        )}
        {territorio && (
          <Button variant="ghost" size="sm" onClick={() => setTerritorio(null)} title="Limpiar territorio activo">
            Limpiar
          </Button>
        )}
        <ThemeToggle />
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-muted text-sm font-semibold" title={usuario}>
          {usuario[0]?.toUpperCase() ?? 'A'}
        </div>
      </div>
      <Sheet open={menuAbierto} onOpenChange={setMenuAbierto}>
        <SheetContent side="left" className="w-72 p-0">
          <SheetHeader className="border-b p-4 text-left">
            <SheetTitle>GEIS · Geomarketing MX</SheetTitle>
          </SheetHeader>
          <div className="h-[calc(100%-4.5rem)]">
            <SidebarNav onNavegar={() => setMenuAbierto(false)} />
          </div>
        </SheetContent>
      </Sheet>
    </header>
  );
}

function tipoStr(tipo?: string): string {
  return tipo ? ` · tipo: ${tipo}` : '';
}
function areaStr(area?: number): string {
  return area !== undefined ? ` · ${area.toFixed(1)} km²` : '';
}

import * as React from 'react';
import { cn } from '@/lib/utils';
import { Button } from './Button';

export interface CalendarProps {
  selected?: Date;
  onSelect?: (d: Date) => void;
  className?: string;
}

const MESES = ['enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre','octubre','noviembre','diciembre'];
const DIAS = ['Do','Lu','Ma','Mi','Ju','Vi','Sá'];

export function Calendar({ selected, onSelect, className }: CalendarProps) {
  const [vista, setVista] = React.useState(() => selected ?? new Date());
  const y = vista.getFullYear();
  const m = vista.getMonth();
  const primero = new Date(y, m, 1).getDay();
  const diasMes = new Date(y, m + 1, 0).getDate();
  const celdas: (number | null)[] = [...Array(primero).fill(null), ...Array.from({ length: diasMes }, (_, i) => i + 1)];
  while (celdas.length % 7) celdas.push(null);

  return (
    <div className={cn('p-3', className)}>
      <div className="mb-2 flex items-center justify-between">
        <Button variant="ghost" size="sm" onClick={() => setVista(new Date(y, m - 1, 1))} aria-label="Mes anterior">‹</Button>
        <span className="text-sm font-medium capitalize">{MESES[m]} {y}</span>
        <Button variant="ghost" size="sm" onClick={() => setVista(new Date(y, m + 1, 1))} aria-label="Mes siguiente">›</Button>
      </div>
      <div className="grid grid-cols-7 gap-1 text-center">
        {DIAS.map((d) => <span key={d} className="py-1 text-xs text-muted-foreground">{d}</span>)}
        {celdas.map((d, i) => {
          if (d === null) return <span key={i} />;
          const fecha = new Date(y, m, d);
          const esSel = selected && fecha.toDateString() === selected.toDateString();
          return (
            <button
              key={i}
              type="button"
              onClick={() => onSelect?.(fecha)}
              className={cn(
                'flex h-8 w-8 items-center justify-center rounded-md text-sm transition-colors hover:bg-accent/20',
                esSel && 'bg-primary text-primary-foreground hover:bg-primary/90',
              )}
            >
              {d}
            </button>
          );
        })}
      </div>
    </div>
  );
}

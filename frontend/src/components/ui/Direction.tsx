import { cn } from '@/lib/utils';

export interface DirectionProps {
  origin: string;
  destination: string;
  mode?: 'auto' | 'caminando' | 'transporte';
  className?: string;
}

/** Enlace de direcciones (Google Maps) para atractores de tráfico del reporte. */
export function Direction({ origin, destination, mode = 'auto', className }: DirectionProps) {
  const travel = mode === 'caminando' ? 'w' : mode === 'transporte' ? 'r' : 'd';
  const href = `https://www.google.com/maps/dir/?api=1&origin=${encodeURIComponent(origin)}&destination=${encodeURIComponent(destination)}&travelmode=${travel}`;
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className={cn('inline-flex items-center gap-1 text-sm text-primary hover:underline', className)}
    >
      <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M6 1a3.5 3.5 0 013.5 3.5c0 2.6-3.5 6.5-3.5 6.5S2.5 7.1 2.5 4.5A3.5 3.5 0 016 1z" stroke="currentColor"/><circle cx="6" cy="4.5" r="1.2" fill="currentColor"/></svg>
      Cómo llegar
    </a>
  );
}

import { cn } from '@/lib/utils';

export interface MarkerProps {
  color?: string;
  size?: number;
  pulse?: boolean;
  label?: string;
  className?: string;
}

/** Marcador de mapa estilizado (pines por estrato). */
export function Marker({ color = '#0E5FD8', size = 18, pulse, label, className }: MarkerProps) {
  return (
    <span className={cn('relative inline-flex items-center justify-center', className)} title={label} aria-label={label ?? 'Marcador'}>
      {pulse && (
        <span
          className="absolute inline-flex animate-ping rounded-full opacity-40"
          style={{ backgroundColor: color, width: size * 1.6, height: size * 1.6 }}
        />
      )}
      <svg width={size} height={size} viewBox="0 0 24 24" fill={color} stroke="#fff" strokeWidth="1.5">
        <path d="M12 2a7 7 0 017 7c0 5.2-7 13-7 13S5 14.2 5 9a7 7 0 017-7z" />
        <circle cx="12" cy="9" r="2.6" fill="#fff" stroke="none" />
      </svg>
    </span>
  );
}

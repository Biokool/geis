import * as React from 'react';
import { cn } from '@/lib/utils';

export interface TraceStep {
  label: string;
  status?: 'ok' | 'running' | 'error' | 'pending';
  detail?: string;
}

export interface TraceProps {
  steps: TraceStep[];
  className?: string;
}

/** Traza vertical de pasos (útil para jobs async: ETL, generación de PDF). */
export function Trace({ steps, className }: TraceProps) {
  return (
    <ol className={cn('space-y-0', className)}>
      {steps.map((s, i) => (
        <li key={i} className="relative flex gap-3 pb-5 last:pb-0">
          {i < steps.length - 1 && <span className="absolute left-[7px] top-5 h-full w-px bg-border" aria-hidden />}
          <span
            className={cn(
              'mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full border text-[9px]',
              s.status === 'ok' && 'border-success bg-success text-white',
              s.status === 'running' && 'border-primary bg-primary/20 text-primary animate-pulse',
              s.status === 'error' && 'border-destructive bg-destructive text-white',
              (!s.status || s.status === 'pending') && 'border-muted-foreground/40 text-transparent',
            )}
          >
            {s.status === 'ok' ? '✓' : s.status === 'error' ? '✕' : '•'}
          </span>
          <div className="min-w-0">
            <p className="text-sm font-medium">{s.label}</p>
            {s.detail && <p className="text-xs text-muted-foreground">{s.detail}</p>}
          </div>
        </li>
      ))}
    </ol>
  );
}

import * as React from 'react';
import { cn } from '@/lib/utils';

export interface StepperStep {
  id: string;
  label: string;
  description?: string;
}

export interface StepperProps extends React.HTMLAttributes<HTMLOListElement> {
  steps: StepperStep[];
  current: number;
  onStepClick?: (index: number) => void;
}

/**
 * Stepper estilo shadcn para wizards: numeración, estado completado/actual/pendiente
 * y línea conectora. Responsive: en móvil solo muestra el paso actual.
 */
export function Stepper({ steps, current, onStepClick, className, ...props }: StepperProps) {
  return (
    <ol
      className={cn('flex items-start gap-1 sm:gap-2', className)}
      aria-label="Progreso del asistente"
      {...props}
    >
      {steps.map((step, i) => {
        const done = i < current;
        const active = i === current;
        const clicable = onStepClick && i < current;
        return (
          <li key={step.id} className="flex min-w-0 flex-1 items-start">
            <button
              type="button"
              disabled={!clicable}
              onClick={() => clicable && onStepClick(i)}
              className={cn(
                'group flex w-full min-w-0 items-start gap-2 rounded-md p-1 text-left',
                clicable ? 'cursor-pointer' : 'cursor-default',
                active && 'outline-none',
              )}
              aria-current={active ? 'step' : undefined}
            >
              <span
                aria-hidden
                className={cn(
                  'flex h-7 w-7 shrink-0 items-center justify-center rounded-full border text-xs font-bold transition-colors',
                  done && 'border-primary bg-primary text-primary-foreground',
                  active && 'border-primary bg-primary/10 text-primary ring-2 ring-primary/30',
                  !done && !active && 'border-border bg-muted text-muted-foreground',
                )}
              >
                {done ? '✓' : i + 1}
              </span>
              <span className="hidden min-w-0 sm:block">
                <span
                  className={cn(
                    'block truncate text-sm font-medium',
                    active ? 'text-foreground' : done ? 'text-foreground' : 'text-muted-foreground',
                  )}
                >
                  {step.label}
                </span>
                {step.description && (
                  <span className="block truncate text-xs text-muted-foreground">{step.description}</span>
                )}
              </span>
            </button>
            {i < steps.length - 1 && (
              <span
                aria-hidden
                className={cn('mx-1 mt-3.5 h-px flex-1 sm:mx-2', i < current ? 'bg-primary' : 'bg-border')}
              />
            )}
          </li>
        );
      })}
    </ol>
  );
}

/** Etiqueta compacta del paso actual para móvil. */
export function StepperMobileLabel({ steps, current }: { steps: StepperStep[]; current: number }) {
  return (
    <p className="text-sm font-medium sm:hidden" aria-live="polite">
      Paso {current + 1} de {steps.length}: {steps[current]?.label}
    </p>
  );
}

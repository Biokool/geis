import * as React from 'react';
import { cn } from '@/lib/utils';
import { Label } from './Label';

export interface FieldProps extends React.HTMLAttributes<HTMLDivElement> {
  label?: string;
  hint?: string;
  error?: string;
  htmlFor?: string;
  required?: boolean;
}

export function Field({ label, hint, error, htmlFor, required, className, children, ...props }: FieldProps) {
  return (
    <div className={cn('space-y-1.5', className)} {...props}>
      {label && (
        <Label htmlFor={htmlFor}>
          {label} {required && <span className="text-destructive">*</span>}
        </Label>
      )}
      {children}
      {hint && !error && <p className="text-xs text-muted-foreground">{hint}</p>}
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  );
}

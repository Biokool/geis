import * as React from 'react';
import { cn } from '@/lib/utils';

export function InputGroup({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('flex w-full items-stretch', className)} {...props} />;
}

export function InputGroupAddon({ className, ...props }: React.HTMLAttributes<HTMLSpanElement>) {
  return (
    <span className={cn('inline-flex items-center gap-1 rounded-l-md border border-r-0 border-input bg-muted px-3 text-sm text-muted-foreground', className)} {...props} />
  );
}

export function InputGroupButton({ className, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      className={cn('inline-flex items-center gap-1 whitespace-nowrap rounded-r-md border border-l-0 border-input bg-secondary px-3 text-sm font-medium hover:bg-secondary/80', className)}
      {...props}
    />
  );
}

import * as React from 'react';
import { cn } from '@/lib/utils';

export interface NativeSelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {}

const NativeSelect = React.forwardRef<HTMLSelectElement, NativeSelectProps>(
  ({ className, children, ...props }, ref) => (
    <div className={cn('relative', className)}>
      <select
        ref={ref}
        className="flex h-9 w-full appearance-none items-center justify-between rounded-md border border-input bg-background px-3 py-2 pr-8 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
        {...props}
      >
        {children}
      </select>
      <svg width="14" height="14" viewBox="0 0 14 14" fill="none" className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 opacity-50">
        <path d="M3.5 5.5l3.5 3.5 3.5-3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
      </svg>
    </div>
  ),
);
NativeSelect.displayName = 'NativeSelect';

export { NativeSelect };

import * as React from 'react';
import { cn } from '@/lib/utils';

export function ButtonGroup({ className, orientation = 'horizontal', ...props }: React.HTMLAttributes<HTMLDivElement> & { orientation?: 'horizontal' | 'vertical' }) {
  return (
    <div
      role="group"
      className={cn(
        'inline-flex',
        orientation === 'horizontal' ? 'flex-row [&>*:not(:first-child)]:rounded-l-none [&>*:not(:last-child)]:rounded-r-none [&>*:not(:first-child)]:border-l-0' : 'flex-col [&>*:not(:first-child)]:rounded-t-none [&>*:not(:last-child)]:rounded-b-none [&>*:not(:first-child)]:border-t-0',
        className,
      )}
      {...props}
    />
  );
}

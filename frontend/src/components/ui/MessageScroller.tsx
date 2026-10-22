import * as React from 'react';
import { cn } from '@/lib/utils';

export interface MessageScrollerProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
}

/** Contenedor de mensajes con auto-scroll al fondo cuando llega contenido nuevo. */
export function MessageScroller({ className, children, ...props }: MessageScrollerProps) {
  const ref = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    const el = ref.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [children]);

  return (
    <div ref={ref} className={cn('flex flex-col gap-3 overflow-y-auto p-4', className)} {...props}>
      {children}
    </div>
  );
}

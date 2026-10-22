import * as React from 'react';
import { cn } from '@/lib/utils';
import { Button } from './Button';

export interface DrawerProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  children?: React.ReactNode;
  side?: 'right' | 'left';
  className?: string;
}

/** Drawer lateral simple para fichas de establecimiento (SRS §6.4: clic en razón social → drawer). */
export function Drawer({ open, onClose, title, children, side = 'right', className }: DrawerProps) {
  React.useEffect(() => {
    const fn = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    if (open) document.addEventListener('keydown', fn);
    return () => document.removeEventListener('keydown', fn);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50" role="dialog" aria-modal="true" aria-label={title ?? 'Panel lateral'}>
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <aside
        className={cn(
          'absolute inset-y-0 flex w-full max-w-md flex-col bg-background shadow-xl',
          side === 'right' ? 'right-0 border-l' : 'left-0 border-r',
          className,
        )}
      >
        <div className="flex items-center justify-between border-b p-4">
          {title && <h3 className="text-lg font-semibold">{title}</h3>}
          <Button variant="ghost" size="icon" onClick={onClose} aria-label="Cerrar">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
          </Button>
        </div>
        <div className="flex-1 overflow-y-auto p-4">{children}</div>
      </aside>
    </div>
  );
}

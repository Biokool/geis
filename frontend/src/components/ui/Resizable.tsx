import * as React from 'react';
import { cn } from '@/lib/utils';

export function ResizablePanelGroup({
  direction = 'horizontal',
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { direction?: 'horizontal' | 'vertical' }) {
  return (
    <div
      data-direction={direction}
      className={cn('flex h-full w-full', direction === 'horizontal' ? 'flex-row' : 'flex-col', className)}
      {...props}
    />
  );
}

export function ResizablePanel({
  defaultSize = 50,
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { defaultSize?: number }) {
  return <div className={cn('overflow-auto', className)} style={{ flex: `${defaultSize} 1 0%` }} {...props} />;
}

export function ResizableHandle({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  const ref = React.useRef<HTMLDivElement>(null);
  const dragging = React.useRef(false);

  React.useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const group = el.closest('[data-direction]') as HTMLElement | null;
    if (!group) return;
    const panels = Array.from(group.querySelectorAll(':scope > [data-panel]')) as HTMLElement[];
    const idx = panels.findIndex((p) => p === el.previousElementSibling || p === el.nextElementSibling);
    const onDown = (e: MouseEvent) => {
      dragging.current = true;
      e.preventDefault();
      const move = (ev: MouseEvent) => {
        if (!dragging.current) return;
        const rect = group.getBoundingClientRect();
        const isH = group.dataset.direction !== 'vertical';
        const ratio = isH ? (ev.clientX - rect.left) / rect.width : (ev.clientY - rect.top) / rect.height;
        if (idx >= 0 && panels[idx]) {
          panels[idx].style.flex = `${Math.max(5, Math.min(95, ratio * 100))} 1 0%`;
        }
      };
      const up = () => { dragging.current = false; window.removeEventListener('mousemove', move); window.removeEventListener('mouseup', up); };
      window.addEventListener('mousemove', move);
      window.addEventListener('mouseup', up);
    };
    el.addEventListener('mousedown', onDown);
    return () => el.removeEventListener('mousedown', onDown);
  }, []);

  return (
    <div
      ref={ref}
      role="separator"
      aria-orientation="horizontal"
      className={cn('relative flex w-1 shrink-0 cursor-col-resize items-center justify-center bg-border transition-colors hover:bg-primary/40', className)}
      {...props}
    />
  );
}

import * as React from 'react';
import { cn } from '@/lib/utils';

export function Sidebar({ className, ...props }: React.HTMLAttributes<HTMLElement>) {
  return <aside className={cn('flex h-full flex-col border-r bg-card', className)} {...props} />;
}

export function SidebarHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('flex items-center gap-2 border-b p-4', className)} {...props} />;
}

export function SidebarContent({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('flex-1 overflow-y-auto p-2', className)} {...props} />;
}

export function SidebarFooter({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('border-t p-4', className)} {...props} />;
}

export function SidebarItem({ className, active, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & { active?: boolean }) {
  return (
    <button
      type="button"
      className={cn(
        'flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-muted',
        active ? 'bg-primary/10 text-primary' : 'text-muted-foreground',
        className,
      )}
      {...props}
    />
  );
}

export function SidebarGroup({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('space-y-1 py-2', className)} {...props} />;
}

export function SidebarGroupLabel({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('px-3 py-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground', className)} {...props} />;
}

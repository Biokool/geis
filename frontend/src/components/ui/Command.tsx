import * as React from 'react';
import { cn } from '@/lib/utils';
import { Dialog, DialogContent } from './Dialog';

export function Command({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('flex h-full w-full flex-col overflow-hidden rounded-md bg-popover text-popover-foreground', className)} {...props} />;
}

export function CommandInput({ className, ...props }: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <div className="flex items-center border-b px-3">
      <svg width="14" height="14" viewBox="0 0 14 14" fill="none" className="mr-2 shrink-0 opacity-50"><circle cx="6" cy="6" r="4.5" stroke="currentColor"/><path d="M9.5 9.5L13 13" stroke="currentColor"/></svg>
      <input
        className={cn('flex h-10 w-full rounded-md bg-transparent py-3 text-sm outline-none placeholder:text-muted-foreground', className)}
        {...props}
      />
    </div>
  );
}

export function CommandList({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('max-h-[300px] overflow-y-auto overflow-x-hidden', className)} {...props} />;
}

export function CommandEmpty({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('py-6 text-center text-sm text-muted-foreground', className)} {...props} />;
}

export function CommandGroup({ className, heading, ...props }: React.HTMLAttributes<HTMLDivElement> & { heading?: string }) {
  return (
    <div className={cn('overflow-hidden p-1 text-foreground', className)} {...props}>
      {heading && <div className="px-2 py-1.5 text-xs font-medium text-muted-foreground">{heading}</div>}
      {props.children}
    </div>
  );
}

export function CommandItem({ className, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      className={cn('relative flex w-full cursor-default select-none items-center gap-2 rounded-sm px-2 py-1.5 text-sm outline-none hover:bg-accent/20 [&_svg]:size-4', className)}
      {...props}
    />
  );
}

export function CommandDialog({ children, ...props }: React.ComponentProps<typeof Dialog>) {
  return (
    <Dialog {...props}>
      <DialogContent className="overflow-hidden p-0">
        <Command className="[&_[cmdk-group-heading]]:px-2">{children}</Command>
      </DialogContent>
    </Dialog>
  );
}

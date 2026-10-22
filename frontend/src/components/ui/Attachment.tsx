import * as React from 'react';
import { cn } from '@/lib/utils';
import { Button } from './Button';

export interface AttachmentProps {
  name: string;
  size?: number;
  onRemove?: () => void;
  className?: string;
}

function formato(bytes?: number): string {
  if (bytes === undefined) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function Attachment({ name, size, onRemove, className }: AttachmentProps) {
  return (
    <div className={cn('flex items-center gap-2 rounded-md border bg-muted/50 px-3 py-2 text-sm', className)}>
      <svg width="14" height="14" viewBox="0 0 14 14" fill="none" className="shrink-0 text-muted-foreground">
        <path d="M8.5 1.5H3.5a1 1 0 00-1 1v9a1 1 0 001 1h7a1 1 0 001-1v-6.5l-3-3.5z" stroke="currentColor" strokeWidth="1.2"/>
        <path d="M8.5 1.5v3h3" stroke="currentColor" strokeWidth="1.2"/>
      </svg>
      <span className="min-w-0 flex-1 truncate font-medium">{name}</span>
      {size !== undefined && <span className="text-xs text-muted-foreground">{formato(size)}</span>}
      {onRemove && (
        <Button variant="ghost" size="sm" className="h-6 w-6 p-0" onClick={onRemove} aria-label={`Quitar ${name}`}>✕</Button>
      )}
    </div>
  );
}

export interface AttachmentListProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
}

export function AttachmentList({ className, children, ...props }: AttachmentListProps) {
  return <div className={cn('space-y-2', className)} {...props}>{children}</div>;
}

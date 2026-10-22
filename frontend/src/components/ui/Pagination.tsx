import * as React from 'react';
import { cn } from '@/lib/utils';
import { Button } from './Button';

export interface PaginationProps {
  page: number;
  totalPages: number;
  onChange: (p: number) => void;
  className?: string;
  siblingCount?: number;
}

function rango(page: number, total: number, siblings: number): (number | '…')[] {
  if (total <= 1) return [1];
  const izq = Math.max(1, page - siblings);
  const der = Math.min(total, page + siblings);
  const out: (number | '…')[] = [];
  if (izq > 1) { out.push(1); if (izq > 2) out.push('…'); }
  for (let i = izq; i <= der; i++) out.push(i);
  if (der < total) { if (der < total - 1) out.push('…'); out.push(total); }
  return out;
}

export function Pagination({ page, totalPages, onChange, className, siblingCount = 1 }: PaginationProps) {
  if (totalPages <= 1) return null;
  return (
    <nav className={cn('flex items-center justify-center gap-1', className)} aria-label="Paginación">
      <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => onChange(page - 1)} aria-label="Anterior">‹</Button>
      {rango(page, totalPages, siblingCount).map((p, i) =>
        p === '…' ? (
          <span key={`e${i}`} className="px-1 text-sm text-muted-foreground">…</span>
        ) : (
          <Button
            key={p}
            variant={p === page ? 'default' : 'ghost'}
            size="sm"
            onClick={() => onChange(p)}
            aria-current={p === page ? 'page' : undefined}
          >
            {p}
          </Button>
        ),
      )}
      <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => onChange(page + 1)} aria-label="Siguiente">›</Button>
    </nav>
  );
}

import * as React from 'react';
import { cn } from '@/lib/utils';
import { Button } from './Button';

export interface CarouselProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
}

export function Carousel({ className, children, ...props }: CarouselProps) {
  const [idx, setIdx] = React.useState(0);
  const items = React.Children.toArray(children);
  const n = items.length;
  const go = (d: number) => setIdx((i) => (i + d + n) % n);
  if (n === 0) return null;
  return (
    <div className={cn('relative overflow-hidden rounded-lg', className)} {...props}>
      <div className="flex transition-transform duration-300" style={{ transform: `translateX(-${idx * 100}%)` }}>
        {items.map((it, i) => (
          <div key={i} className="w-full shrink-0">{it}</div>
        ))}
      </div>
      {n > 1 && (
        <>
          <Button variant="outline" size="icon" className="absolute left-2 top-1/2 -translate-y-1/2 rounded-full bg-background/80" onClick={() => go(-1)} aria-label="Anterior">‹</Button>
          <Button variant="outline" size="icon" className="absolute right-2 top-1/2 -translate-y-1/2 rounded-full bg-background/80" onClick={() => go(1)} aria-label="Siguiente">›</Button>
          <div className="absolute bottom-2 left-1/2 flex -translate-x-1/2 gap-1.5">
            {items.map((_, i) => (
              <button key={i} onClick={() => setIdx(i)} aria-label={`Ir a ${i + 1}`} className={cn('h-2 w-2 rounded-full', i === idx ? 'bg-primary' : 'bg-muted-foreground/40')} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

export function CarouselItem({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('', className)} {...props} />;
}

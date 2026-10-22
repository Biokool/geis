import * as React from 'react';
import { cn } from '@/lib/utils';
import { Bubble } from './Bubble';
import { Avatar, AvatarFallback } from './Avatar';

export interface MessageProps {
  from: 'user' | 'assistant' | 'system';
  author?: string;
  time?: string;
  children: React.ReactNode;
  className?: string;
}

export function Message({ from, author, time, children, className }: MessageProps) {
  const esUsuario = from === 'user';
  return (
    <div className={cn('flex gap-2', esUsuario ? 'flex-row-reverse' : 'flex-row', className)}>
      {!esUsuario && (
        <Avatar className="h-8 w-8">
          <AvatarFallback>{from === 'system' ? '⚙' : (author?.[0] ?? 'G')}</AvatarFallback>
        </Avatar>
      )}
      <div className={cn('flex max-w-[80%] flex-col gap-1', esUsuario ? 'items-end' : 'items-start')}>
        {(author || time) && (
          <div className="flex items-baseline gap-2 px-1">
            {author && <span className="text-xs font-semibold">{author}</span>}
            {time && <span className="text-[11px] text-muted-foreground">{time}</span>}
          </div>
        )}
        <Bubble variant={esUsuario ? 'outgoing' : 'incoming'}>{children}</Bubble>
      </div>
    </div>
  );
}

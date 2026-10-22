import * as React from 'react';
import { cn } from '@/lib/utils';

export interface InputOTPProps {
  length?: number;
  value?: string;
  onChange?: (v: string) => void;
  className?: string;
}

export function InputOTP({ length = 6, value = '', onChange, className }: InputOTPProps) {
  const refs = React.useRef<(HTMLInputElement | null)[]>([]);
  const chars = value.padEnd(length, ' ').slice(0, length).split('');

  const setChar = (i: number, ch: string) => {
    const arr = value.padEnd(length, ' ').slice(0, length).split('');
    arr[i] = ch.replace(/[^0-9a-zA-Z]/, '').slice(-1) || ' ';
    const next = arr.join('').trimEnd();
    onChange?.(next);
    if (ch && i < length - 1) refs.current[i + 1]?.focus();
  };

  return (
    <div className={cn('flex items-center gap-2', className)} role="group" aria-label="Código de verificación">
      {chars.map((c, i) => (
        <input
          key={i}
          ref={(el) => { refs.current[i] = el; }}
          value={c.trim()}
          maxLength={1}
          inputMode="numeric"
          autoComplete="one-time-code"
          onChange={(e) => setChar(i, e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Backspace' && !c.trim() && i > 0) refs.current[i - 1]?.focus();
          }}
          className="h-11 w-10 rounded-md border border-input bg-background text-center text-lg font-mono shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
          aria-label={`Dígito ${i + 1}`}
        />
      ))}
    </div>
  );
}

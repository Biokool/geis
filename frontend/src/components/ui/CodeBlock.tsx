import * as React from 'react';
import { cn } from '@/lib/utils';
import { Button } from './Button';

export interface CodeBlockProps {
  code: string;
  language?: string;
  className?: string;
  showCopy?: boolean;
}

export function CodeBlock({ code, language, className, showCopy = true }: CodeBlockProps) {
  const [copiado, setCopiado] = React.useState(false);
  const copiar = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopiado(true);
      setTimeout(() => setCopiado(false), 1500);
    } catch { /* portapapeles no disponible */ }
  };
  return (
    <div className={cn('relative rounded-lg border bg-[#0d1117] text-gray-100', className)}>
      {(language || showCopy) && (
        <div className="flex items-center justify-between border-b border-white/10 px-3 py-1.5">
          <span className="text-xs text-gray-400">{language ?? ''}</span>
          {showCopy && (
            <Button variant="ghost" size="sm" className="h-6 text-gray-300 hover:text-white" onClick={copiar}>
              {copiado ? 'Copiado ✓' : 'Copiar'}
            </Button>
          )}
        </div>
      )}
      <pre className="overflow-x-auto p-3 font-mono text-[13px] leading-relaxed"><code>{code}</code></pre>
    </div>
  );
}

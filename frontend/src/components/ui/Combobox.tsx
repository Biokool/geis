import * as React from 'react';
import { Popover, PopoverContent, PopoverTrigger } from './Popover';
import { Button } from './Button';
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from './Command';
import { cn } from '@/lib/utils';

export interface ComboboxOption {
  value: string;
  label: string;
}

export interface ComboboxProps {
  options: ComboboxOption[];
  value?: string;
  onChange?: (v: string) => void;
  placeholder?: string;
  searchPlaceholder?: string;
  emptyText?: string;
  className?: string;
}

export function Combobox({
  options, value, onChange, placeholder = 'Seleccionar…',
  searchPlaceholder = 'Buscar…', emptyText = 'Sin resultados.', className,
}: ComboboxProps) {
  const [open, setOpen] = React.useState(false);
  const [q, setQ] = React.useState('');
  const sel = options.find((o) => o.value === value);
  const filtradas = options.filter((o) => o.label.toLowerCase().includes(q.toLowerCase()));

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="outline" role="combobox" aria-expanded={open} className={cn('w-full justify-between', className)}>
          <span className="truncate">{sel ? sel.label : <span className="text-muted-foreground">{placeholder}</span>}</span>
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" className="ml-2 shrink-0 opacity-50"><path d="M3.5 5.5l3.5 3.5 3.5-3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[--radix-popover-trigger-width] min-w-[12rem] p-0" align="start">
        <Command>
          <CommandInput placeholder={searchPlaceholder} value={q} onChange={(e) => setQ(e.target.value)} />
          <CommandList>
            <CommandEmpty>{emptyText}</CommandEmpty>
            <CommandGroup>
              {filtradas.map((o) => (
                <CommandItem
                  key={o.value}
                  onClick={() => { onChange?.(o.value); setOpen(false); setQ(''); }}
                >
                  <svg width="12" height="12" viewBox="0 0 12 12" fill="none" className={cn('mr-1', o.value === value ? 'opacity-100' : 'opacity-0')}>
                    <path d="M2 6l2.5 2.5L10 3" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
                  </svg>
                  {o.label}
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}

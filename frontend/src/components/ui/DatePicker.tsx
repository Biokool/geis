import * as React from 'react';
import { Popover, PopoverContent, PopoverTrigger } from './Popover';
import { Button } from './Button';
import { Calendar } from './Calendar';

export interface DatePickerProps {
  value?: Date;
  onChange?: (d: Date | undefined) => void;
  placeholder?: string;
}

export function DatePicker({ value, onChange, placeholder = 'Elegir fecha' }: DatePickerProps) {
  const [open, setOpen] = React.useState(false);
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="outline" className="w-full justify-start text-left font-normal">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" className="mr-2"><rect x="1.5" y="2.5" width="11" height="10" rx="1.5" stroke="currentColor"/><path d="M1.5 5.5h11M4.5 1v3M9.5 1v3" stroke="currentColor"/></svg>
          {value ? value.toLocaleDateString('es-MX', { day: 'numeric', month: 'long', year: 'numeric' }) : <span className="text-muted-foreground">{placeholder}</span>}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0" align="start">
        <Calendar selected={value} onSelect={(d) => { onChange?.(d); setOpen(false); }} />
      </PopoverContent>
    </Popover>
  );
}

import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

const typographyVariants = cva('', {
  variants: {
    variant: {
      h1: 'text-[28px] font-bold tracking-tight',
      h2: 'text-[20px] font-semibold tracking-tight',
      h3: 'text-base font-semibold',
      body: 'text-[15px] leading-relaxed',
      small: 'text-sm',
      micro: 'text-xs text-muted-foreground',
      muted: 'text-sm text-muted-foreground',
      mono: 'font-mono text-sm',
      lead: 'text-lg text-muted-foreground',
    },
  },
  defaultVariants: { variant: 'body' },
});

export interface TypographyProps
  extends React.HTMLAttributes<HTMLElement>,
    VariantProps<typeof typographyVariants> {
  as?: 'h1' | 'h2' | 'h3' | 'h4' | 'p' | 'span' | 'div';
}

export function Typography({ variant, as, className, ...props }: TypographyProps) {
  const Tag = (as ?? (variant === 'h1' ? 'h1' : variant === 'h2' ? 'h2' : variant === 'h3' ? 'h3' : 'p')) as 'p';
  return <Tag className={cn(typographyVariants({ variant }), className)} {...props} />;
}

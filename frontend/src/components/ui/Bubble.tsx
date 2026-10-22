import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

const bubbleVariants = cva('max-w-[75%] rounded-2xl px-4 py-2 text-sm leading-relaxed shadow-sm', {
  variants: {
    variant: {
      incoming: 'bg-muted text-foreground rounded-tl-md',
      outgoing: 'bg-primary text-primary-foreground rounded-tr-md',
    },
  },
  defaultVariants: { variant: 'incoming' },
});

export interface BubbleProps extends React.HTMLAttributes<HTMLDivElement>, VariantProps<typeof bubbleVariants> {}

export function Bubble({ className, variant, ...props }: BubbleProps) {
  return <div className={cn(bubbleVariants({ variant }), className)} {...props} />;
}

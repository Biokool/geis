import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

const itemVariants = cva(
  'flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors',
  {
    variants: {
      variant: {
        default: 'hover:bg-muted',
        active: 'bg-primary/10 text-primary',
        destructive: 'text-destructive hover:bg-destructive/10',
      },
    },
    defaultVariants: { variant: 'default' },
  },
);

export interface ItemProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof itemVariants> {}

const Item = React.forwardRef<HTMLButtonElement, ItemProps>(
  ({ className, variant, ...props }, ref) => (
    <button ref={ref} type="button" className={cn(itemVariants({ variant }), className)} {...props} />
  ),
);
Item.displayName = 'Item';

export { Item, itemVariants };

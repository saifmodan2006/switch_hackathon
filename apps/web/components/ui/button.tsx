import * as React from 'react';
import { Slot } from '@radix-ui/react-slot';
import { cva, type VariantProps } from 'class-variance-authority';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
export const cn = (...values: Parameters<typeof clsx>) => twMerge(clsx(values));
const variants = cva('btn button-xsm', {variants:{variant:{default:'btn-primary',outline:'btn-outline',ghost:'btn-ghost',destructive:'btn-danger'},size:{default:'',sm:'btn-sm',icon:'btn-icon'}},defaultVariants:{variant:'default',size:'default'}});
export function Button({className,variant,size,asChild=false,...props}:React.ComponentProps<'button'> & VariantProps<typeof variants> & {asChild?:boolean}) {
  const Component = asChild ? Slot : 'button';
  return <Component className={cn(variants({variant,size}),className)} {...props}/>;
}

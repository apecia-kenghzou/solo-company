'use client';

import * as React from 'react';
import * as RadixSelect from '@radix-ui/react-select';
import { ChevronDown, Check } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface SelectOption {
  value: string;
  label: string;
}

export interface SelectProps {
  options: SelectOption[];
  value?: string;
  onValueChange?: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
  error?: string;
  label?: string;
  className?: string;
}

export function Select({
  options,
  value,
  onValueChange,
  placeholder = 'Select...',
  disabled,
  error,
  label,
  className,
}: SelectProps) {
  return (
    <div className="flex flex-col gap-1.5">
      {label && (
        <label className="text-sm font-medium text-[var(--foreground)]">{label}</label>
      )}
      <RadixSelect.Root value={value} onValueChange={onValueChange} disabled={disabled}>
        <RadixSelect.Trigger
          className={cn(
            'flex h-9 w-full items-center justify-between rounded-lg border border-[var(--border)] bg-white dark:bg-surface-dark px-3 py-1 text-sm text-[var(--foreground)] shadow-sm transition-colors',
            'focus:outline-none focus:ring-2 focus:ring-primary-400 focus:border-transparent',
            'disabled:cursor-not-allowed disabled:opacity-50',
            'data-[placeholder]:text-[var(--muted)]',
            error && 'border-red-500',
            className
          )}
        >
          <RadixSelect.Value placeholder={placeholder} />
          <RadixSelect.Icon asChild>
            <ChevronDown className="w-4 h-4 text-[var(--muted)] flex-shrink-0" />
          </RadixSelect.Icon>
        </RadixSelect.Trigger>

        <RadixSelect.Portal>
          <RadixSelect.Content
            className="z-50 min-w-[8rem] overflow-hidden rounded-lg border border-[var(--border)] bg-white dark:bg-surface-dark shadow-lg animate-in fade-in-0 zoom-in-95"
            position="popper"
            sideOffset={4}
          >
            <RadixSelect.Viewport className="p-1">
              {options.map((opt) => (
                <RadixSelect.Item
                  key={opt.value}
                  value={opt.value}
                  className={cn(
                    'relative flex w-full cursor-pointer select-none items-center rounded-md py-1.5 pl-8 pr-3 text-sm text-[var(--foreground)] outline-none',
                    'focus:bg-[var(--muted-bg)] data-[highlighted]:bg-[var(--muted-bg)]',
                    'data-[disabled]:pointer-events-none data-[disabled]:opacity-50'
                  )}
                >
                  <RadixSelect.ItemIndicator className="absolute left-2 flex items-center justify-center">
                    <Check className="w-4 h-4 text-primary-500" />
                  </RadixSelect.ItemIndicator>
                  <RadixSelect.ItemText>{opt.label}</RadixSelect.ItemText>
                </RadixSelect.Item>
              ))}
            </RadixSelect.Viewport>
          </RadixSelect.Content>
        </RadixSelect.Portal>
      </RadixSelect.Root>
      {error && <p className="text-xs text-red-600 dark:text-red-400">{error}</p>}
    </div>
  );
}

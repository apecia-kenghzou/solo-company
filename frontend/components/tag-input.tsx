'use client';

import * as React from 'react';
import { X } from 'lucide-react';
import { cn } from '@/lib/utils';

interface TagInputProps {
  value: string[];
  onChange: (tags: string[]) => void;
  placeholder?: string;
  label?: string;
  disabled?: boolean;
  className?: string;
  suggestions?: string[];
}

export function TagInput({
  value,
  onChange,
  placeholder = 'Type and press Enter...',
  label,
  disabled,
  className,
}: TagInputProps) {
  const [inputValue, setInputValue] = React.useState('');
  const inputRef = React.useRef<HTMLInputElement>(null);

  const addTag = (tag: string) => {
    const trimmed = tag.trim();
    if (trimmed && !value.includes(trimmed)) {
      onChange([...value, trimmed]);
    }
    setInputValue('');
  };

  const removeTag = (index: number) => {
    onChange(value.filter((_, i) => i !== index));
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      addTag(inputValue);
    } else if (e.key === 'Backspace' && !inputValue && value.length > 0) {
      removeTag(value.length - 1);
    }
  };

  const handleBlur = () => {
    if (inputValue.trim()) {
      addTag(inputValue);
    }
  };

  return (
    <div className="flex flex-col gap-1.5">
      {label && (
        <label className="text-sm font-medium text-[var(--foreground)]">{label}</label>
      )}
      <div
        className={cn(
          'flex flex-wrap gap-1.5 min-h-[38px] w-full rounded-lg border border-[var(--border)] bg-white dark:bg-surface-dark px-3 py-2',
          'focus-within:ring-2 focus-within:ring-primary-400 focus-within:border-transparent',
          'cursor-text transition-colors',
          disabled && 'opacity-50 pointer-events-none',
          className
        )}
        onClick={() => inputRef.current?.focus()}
      >
        {value.map((tag, index) => (
          <span
            key={`${tag}-${index}`}
            className="inline-flex items-center gap-1 bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 text-xs font-medium px-2.5 py-1 rounded-md"
          >
            {tag}
            {!disabled && (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  removeTag(index);
                }}
                className="text-primary-500 hover:text-primary-700 dark:hover:text-primary-200 transition-colors"
              >
                <X className="w-3 h-3" />
              </button>
            )}
          </span>
        ))}
        <input
          ref={inputRef}
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={handleBlur}
          placeholder={value.length === 0 ? placeholder : ''}
          disabled={disabled}
          className="flex-1 min-w-[120px] text-sm text-[var(--foreground)] bg-transparent outline-none placeholder:text-[var(--muted)]"
        />
      </div>
      <p className="text-xs text-[var(--muted)]">Press Enter or comma to add</p>
    </div>
  );
}

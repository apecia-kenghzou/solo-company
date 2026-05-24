'use client';

import * as React from 'react';
import * as ToastPrimitive from '@radix-ui/react-toast';
import { CheckCircle, XCircle, Info, X } from 'lucide-react';
import { cn } from '@/lib/utils';

// ─── Types ───────────────────────────────────────────────────────────────────

type ToastType = 'success' | 'error' | 'info';

interface ToastItem {
  id: string;
  type: ToastType;
  message: string;
}

interface ToastContextValue {
  toast: {
    success: (message: string) => void;
    error: (message: string) => void;
    info: (message: string) => void;
  };
}

// ─── Context ─────────────────────────────────────────────────────────────────

const ToastContext = React.createContext<ToastContextValue | null>(null);

export function useToast() {
  const ctx = React.useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used inside ToastProvider');
  return ctx;
}

// ─── Provider ────────────────────────────────────────────────────────────────

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = React.useState<ToastItem[]>([]);

  const addToast = React.useCallback((type: ToastType, message: string) => {
    const id = Math.random().toString(36).slice(2);
    setToasts((prev) => [...prev, { id, type, message }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 5000);
  }, []);

  const contextValue = React.useMemo(
    () => ({
      toast: {
        success: (msg: string) => addToast('success', msg),
        error: (msg: string) => addToast('error', msg),
        info: (msg: string) => addToast('info', msg),
      },
    }),
    [addToast]
  );

  return (
    <ToastContext.Provider value={contextValue}>
      <ToastPrimitive.Provider swipeDirection="right">
        {children}
        {toasts.map((t) => (
          <ToastItem key={t.id} toast={t} onRemove={() => setToasts((prev) => prev.filter((x) => x.id !== t.id))} />
        ))}
        <ToastPrimitive.Viewport className="fixed bottom-4 right-4 z-[200] flex flex-col gap-2 w-[380px] max-w-[100vw-32px]" />
      </ToastPrimitive.Provider>
    </ToastContext.Provider>
  );
}

// ─── Toast Item ───────────────────────────────────────────────────────────────

function ToastItem({ toast, onRemove }: { toast: ToastItem; onRemove: () => void }) {
  const icons: Record<ToastType, React.ReactNode> = {
    success: <CheckCircle className="w-5 h-5 text-green-500 flex-shrink-0" />,
    error: <XCircle className="w-5 h-5 text-red-500 flex-shrink-0" />,
    info: <Info className="w-5 h-5 text-blue-500 flex-shrink-0" />,
  };

  const borderColors: Record<ToastType, string> = {
    success: 'border-l-green-500',
    error: 'border-l-red-500',
    info: 'border-l-blue-500',
  };

  return (
    <ToastPrimitive.Root
      open={true}
      onOpenChange={(open) => {
        if (!open) onRemove();
      }}
      className={cn(
        'flex items-start gap-3 p-4 bg-white dark:bg-surface-dark border border-[var(--border)] border-l-4 rounded-xl shadow-lg',
        'data-[state=open]:animate-in data-[state=closed]:animate-out',
        'data-[swipe=end]:animate-out data-[state=closed]:fade-out-80 data-[state=closed]:slide-out-to-right-full',
        'data-[state=open]:slide-in-from-bottom-full data-[state=open]:fade-in-0',
        borderColors[toast.type]
      )}
    >
      {icons[toast.type]}
      <ToastPrimitive.Description className="flex-1 text-sm text-[var(--foreground)] pt-0.5">
        {toast.message}
      </ToastPrimitive.Description>
      <ToastPrimitive.Close asChild>
        <button
          className="text-[var(--muted)] hover:text-[var(--foreground)] transition-colors flex-shrink-0"
          onClick={onRemove}
        >
          <X className="w-4 h-4" />
        </button>
      </ToastPrimitive.Close>
    </ToastPrimitive.Root>
  );
}

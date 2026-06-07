"use client";

import React, { createContext, useCallback, useContext, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { IconCheck, IconAlertCircle, IconInfoCircle, IconX } from "@tabler/icons-react";
import { cn } from "@/lib/utils";

export type ToastVariant = "success" | "error" | "info";

interface ToastItem {
  id: string;
  message: string;
  variant: ToastVariant;
}

interface ToastContextValue {
  toast: (message: string, variant?: ToastVariant) => void;
}

const ToastCtx = createContext<ToastContextValue | null>(null);

const VARIANT_STYLES: Record<ToastVariant, string> = {
  success: "bg-emerald-950/95 border-emerald-700/50 text-emerald-100 shadow-emerald-900/30",
  error: "bg-red-950/95 border-red-700/50 text-red-100 shadow-red-900/30",
  info: "bg-surface-panel border-border text-text-primary shadow-black/40",
};

const ICONS: Record<ToastVariant, React.ReactNode> = {
  success: <IconCheck className="size-4 text-emerald-400 shrink-0 mt-0.5" />,
  error: <IconAlertCircle className="size-4 text-red-400 shrink-0 mt-0.5" />,
  info: <IconInfoCircle className="size-4 text-yellow shrink-0 mt-0.5" />,
};

export function ToastProvider({ children }: Readonly<{ children: React.ReactNode }>) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const push = useCallback(
    (message: string, variant: ToastVariant = "info") => {
      const id = Math.random().toString(36).slice(2, 10);
      setToasts((prev) => [...prev, { id, message, variant }]);
      setTimeout(() => dismiss(id), 4000);
    },
    [dismiss],
  );

  return (
    <ToastCtx.Provider value={{ toast: push }}>
      {children}
      <div
        aria-live="polite"
        aria-atomic="false"
        className="fixed bottom-5 right-5 z-[200] flex flex-col gap-2 items-end pointer-events-none"
      >
        <AnimatePresence>
          {toasts.map((t) => (
            <motion.div
              key={t.id}
              layout
              initial={{ opacity: 0, x: 64, scale: 0.95 }}
              animate={{ opacity: 1, x: 0, scale: 1 }}
              exit={{ opacity: 0, x: 64, scale: 0.95 }}
              transition={{ type: "spring", stiffness: 380, damping: 28 }}
              className={cn(
                "pointer-events-auto flex items-start gap-3 min-w-[260px] max-w-sm",
                "px-4 py-3 rounded-xl border shadow-xl text-sm font-medium backdrop-blur-md",
                VARIANT_STYLES[t.variant],
              )}
            >
              {ICONS[t.variant]}
              <span className="flex-1 leading-snug">{t.message}</span>
              <button
                type="button"
                onClick={() => dismiss(t.id)}
                aria-label="Dismiss notification"
                className="shrink-0 mt-0.5 opacity-50 hover:opacity-100 transition-opacity"
              >
                <IconX className="size-3.5" />
              </button>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastCtx.Provider>
  );
}

export function useToast(): (message: string, variant?: ToastVariant) => void {
  const ctx = useContext(ToastCtx);
  if (!ctx) throw new Error("useToast must be used within <ToastProvider>");
  return ctx.toast;
}

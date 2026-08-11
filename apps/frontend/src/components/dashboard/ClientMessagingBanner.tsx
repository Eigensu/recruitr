"use client";

import { useEffect, useMemo, useState } from "react";
import {
  IconInfoCircle,
  IconAlertTriangle,
  IconSpeakerphone,
  IconChartBar,
  IconX,
  IconChevronLeft,
  IconChevronRight,
} from "@tabler/icons-react";
import { motion, AnimatePresence } from "motion/react";
import Link from "next/link";

export type ClientMessageType = "seasonal" | "action" | "announcement" | "benchmark";

export interface ClientMessage {
  _id: string;
  message_text: string;
  type: ClientMessageType;
  cta_url?: string;
}

interface BannerProps {
  messages: ClientMessage[];
  userId: string;
}

const TYPE_CONFIG: Record<ClientMessageType, { icon: React.ElementType; tone: string }> = {
  seasonal: { icon: IconInfoCircle, tone: "bg-blue-500/10 text-blue-500 border-blue-500/20" },
  action: { icon: IconAlertTriangle, tone: "bg-red-500/10 text-red-500 border-red-500/20" },
  announcement: {
    icon: IconSpeakerphone,
    tone: "bg-green-500/10 text-green-500 border-green-500/20",
  },
  benchmark: { icon: IconChartBar, tone: "bg-purple-500/10 text-purple-500 border-purple-500/20" },
};

export function ClientMessagingBanner({ messages, userId }: BannerProps) {
  // null = "haven't checked sessionStorage yet" (always true during SSR).
  // Keeps the banner hidden rather than briefly showing an already-dismissed
  // message before the effect below corrects it.
  const [dismissedIds, setDismissedIds] = useState<string[] | null>(null);
  const [currentIndex, setCurrentIndex] = useState(0);

  useEffect(() => {
    // One-time sync from an external system (sessionStorage) into React state —
    // not a derived value, so this is exactly what an effect is for.
    const storageKey = `dismissed_banners_${userId}`;
    const dismissed = JSON.parse(sessionStorage.getItem(storageKey) || "[]");
    setDismissedIds(dismissed);
  }, [userId]);

  const activeMessages = useMemo(
    () => (dismissedIds === null ? [] : messages.filter((m) => !dismissedIds.includes(m._id))),
    [messages, dismissedIds],
  );

  // Derived at render time instead of clamped via setState-in-effect, so
  // currentIndex never has to be "corrected" out-of-band when the list shrinks.
  const safeIndex = activeMessages.length > 0 ? Math.min(currentIndex, activeMessages.length - 1) : 0;

  if (activeMessages.length === 0) return null;

  const msg = activeMessages[safeIndex];
  const config = TYPE_CONFIG[msg.type] || TYPE_CONFIG.announcement;
  const Icon = config.icon;

  const handleDismiss = () => {
    const storageKey = `dismissed_banners_${userId}`;
    const updated = [...(dismissedIds ?? []), msg._id];
    setDismissedIds(updated);
    sessionStorage.setItem(storageKey, JSON.stringify(updated));
  };

  const nextMsg = () => setCurrentIndex((safeIndex + 1) % activeMessages.length);
  const prevMsg = () => setCurrentIndex((safeIndex - 1 + activeMessages.length) % activeMessages.length);

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={msg._id}
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95 }}
        className={`relative flex items-center justify-between p-4 rounded-lg border shadow-sm ${config.tone}`}
      >
        <div className="flex items-center gap-3 pr-8">
          <Icon className="size-5 shrink-0" />
          <p className="text-sm font-medium">{msg.message_text}</p>
          {msg.cta_url && (
            <Link
              href={msg.cta_url}
              className="text-sm font-bold underline underline-offset-2 ml-2 hover:opacity-80 transition-opacity"
            >
              View details
            </Link>
          )}
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {activeMessages.length > 1 && (
            <div className="flex items-center gap-1 mr-4 bg-black/5 dark:bg-white/5 rounded-full px-2 py-1">
              <button
                onClick={prevMsg}
                className="p-0.5 hover:bg-black/10 dark:hover:bg-white/10 rounded-full transition-colors"
                aria-label="Previous message"
              >
                <IconChevronLeft className="size-4" />
              </button>
              <span className="text-xs font-medium px-1">
                {safeIndex + 1} / {activeMessages.length}
              </span>
              <button
                onClick={nextMsg}
                className="p-0.5 hover:bg-black/10 dark:hover:bg-white/10 rounded-full transition-colors"
                aria-label="Next message"
              >
                <IconChevronRight className="size-4" />
              </button>
            </div>
          )}

          <button
            onClick={handleDismiss}
            className="p-1.5 rounded-md hover:bg-black/10 dark:hover:bg-white/10 transition-colors"
            aria-label="Dismiss message"
          >
            <IconX className="size-4" />
          </button>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { IconBell } from "@tabler/icons-react";
import {
  clientFetchNotifications,
  clientMarkNotificationRead,
} from "@/lib/api/notifications.client";
import type { PipelineNotification } from "@/types";

const POLL_MS = 60_000;

export default function NotificationBell() {
  const [notifications, setNotifications] = useState<PipelineNotification[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const load = useCallback(() => {
    clientFetchNotifications()
      .then(setNotifications)
      .catch(() => {
        // Silent: a failed poll shouldn't interrupt the dashboard. It'll retry next tick.
      });
  }, []);

  useEffect(() => {
    load();
    const interval = setInterval(load, POLL_MS);
    return () => clearInterval(interval);
  }, [load]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const router = useRouter();

  async function handleMarkRead(n: PipelineNotification) {
    if (!n.read_at) {
      setNotifications((prev) =>
        prev.map((prevN) =>
          prevN.id === n.id ? { ...prevN, read_at: new Date().toISOString() } : prevN,
        ),
      );
      try {
        await clientMarkNotificationRead(n.id);
      } catch {
        load(); // resync on failure
      }
    }

    setIsOpen(false);
    if (n.kind === "client_message") {
      router.push("/client-messaging");
    }
  }

  const unreadCount = notifications.filter((n) => !n.read_at).length;

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setIsOpen((v) => !v)}
        aria-label="Notifications"
        className="relative flex size-9 items-center justify-center rounded-lg transition-colors"
        style={{ background: "var(--color-toggle-bg)", color: "var(--color-toggle-icon)" }}
      >
        <IconBell className="size-4.5" />
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 flex size-4 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {isOpen && (
        <div
          className="absolute right-0 z-50 mt-2 w-80 max-w-[90vw] overflow-hidden rounded-lg border shadow-xl"
          style={{
            background: "var(--color-surface-val)",
            borderColor: "var(--color-border-val)",
          }}
        >
          <div
            className="border-b px-4 py-3 text-xs font-bold uppercase tracking-wide text-text-secondary"
            style={{ borderColor: "var(--color-border-val)" }}
          >
            Notifications
          </div>
          <div className="max-h-80 overflow-y-auto">
            {notifications.length === 0 ? (
              <p className="px-4 py-6 text-center text-sm text-text-muted">
                Nothing needs your attention right now.
              </p>
            ) : (
              notifications.map((n) => (
                <button
                  key={n.id}
                  type="button"
                  onClick={() => handleMarkRead(n)}
                  className="block w-full border-b px-4 py-3 text-left text-sm transition-colors last:border-b-0 hover:bg-surface-2"
                  style={{
                    borderColor: "var(--color-border-val)",
                    opacity: n.read_at ? 0.5 : 1,
                  }}
                >
                  <p className="text-text-primary">{n.message}</p>
                  <p className="mt-1 text-xs text-text-muted">
                    {new Date(n.created_at).toLocaleString("en-GB")}
                  </p>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}

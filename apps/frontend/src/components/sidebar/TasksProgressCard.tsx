"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "motion/react";
import { useSidebar } from "@/components/ui/sidebar";
import { useApiFetch } from "@/lib/api";
import { listTasks, type TaskResponse } from "@/lib/api/tasks";

export function TasksProgressCard() {
  const { open } = useSidebar();
  const apiFetch = useApiFetch();

  const [tasks, setTasks] = useState<TaskResponse[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const data = await listTasks(apiFetch);
        setTasks(data);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    load();

    // Auto-refresh tasks periodically to update sidebar
    const interval = setInterval(load, 30000);
    return () => clearInterval(interval);
  }, [apiFetch]);

  if (loading) return null; // Wait for load to avoid flashing

  const totalTasks = tasks.length;

  // Aggregate completed_count and target_count
  const totalCompleted = tasks.reduce(
    (acc, t) => acc + Math.min(t.completed_count, t.target_count),
    0,
  );
  const totalTarget = tasks.reduce((acc, t) => acc + t.target_count, 0);

  const displayProgress = totalTarget > 0 ? Math.round((totalCompleted / totalTarget) * 100) : 0;

  // Closed state: show only percentage badge (compact)
  if (!open) {
    if (totalTasks === 0) return null; // Don't show badge if no tasks
    return (
      <div className="flex items-center justify-center px-3 py-1.5">
        <motion.div
          initial={{ scale: 0.95, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ duration: 0.18 }}
          className="size-8 flex shrink-0 items-center justify-center rounded-full font-bold text-[10px] tracking-tighter"
          style={{
            background: "var(--color-surface-2-val)",
            color: "var(--color-text-primary)",
            border: "1px solid rgba(255,255,255,0.08)",
          }}
        >
          {displayProgress}%
        </motion.div>
      </div>
    );
  }

  // Open state: full card
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, ease: "easeOut" }}
      className="px-3 py-2"
    >
      <Link href="/settings" className="no-underline block">
        <div
          className="rounded-2xl p-4 cursor-pointer overflow-hidden transition-opacity hover:opacity-90"
          style={{
            background: "var(--color-surface-2-val)",
            color: "var(--color-text-primary)",
          }}
        >
          <div className="flex flex-col">
            <span className="text-sm font-semibold" style={{ color: "var(--color-text-primary)" }}>
              TASKS
            </span>

            {totalTasks === 0 ? (
              <span className="mt-2 text-xs" style={{ color: "var(--color-text-secondary)" }}>
                No active tasks
              </span>
            ) : (
              <>
                <div
                  className="mt-3 relative w-full h-2 rounded-full overflow-hidden"
                  style={{ background: "var(--color-surface-val)" }}
                >
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${displayProgress}%` }}
                    transition={{ duration: 0.8, ease: "easeOut" }}
                    className="h-full rounded-full"
                    style={{
                      background: "linear-gradient(90deg, #F3FF54 0%, #F97316 100%)",
                    }}
                  />
                </div>
                <span className="mt-2 text-xs" style={{ color: "var(--color-text-secondary)" }}>
                  {`${totalCompleted} of ${totalTarget} completed`}
                </span>
              </>
            )}
          </div>
        </div>
      </Link>
    </motion.div>
  );
}

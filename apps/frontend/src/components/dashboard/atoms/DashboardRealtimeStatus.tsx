"use client";

import { useEffect, useState } from "react";

export default function DashboardRealtimeStatus() {
  const [updatedAt, setUpdatedAt] = useState("");

  useEffect(() => {
    const update = () => {
      setUpdatedAt(
        new Intl.DateTimeFormat("en-IN", {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        }).format(new Date()),
      );
    };

    update();
    const interval = window.setInterval(update, 30000);

    return () => window.clearInterval(interval);
  }, []);

  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-yellow/30 bg-yellow/10 px-3 py-1.5 text-xs font-semibold text-yellow">
      <span className="size-2 animate-pulse rounded-full bg-yellow" />
      Live sync{updatedAt ? ` at ${updatedAt}` : ""}
    </span>
  );
}

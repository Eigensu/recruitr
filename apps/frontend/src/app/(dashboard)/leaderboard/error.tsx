"use client";

import { motion } from "motion/react";

interface ErrorProps {
  error: Error;
  reset: () => void;
}

export default function LeaderboardError({ error, reset }: ErrorProps) {
  console.error(error);

  return (
    <div className="min-h-full bg-black px-4 py-5 text-white flex items-center justify-center">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        className="max-w-md w-full rounded-lg border border-red-400/20 bg-red-400/5 p-8 text-center"
      >
        <p className="text-4xl mb-3">⚠️</p>
        <h2 className="font-heading text-2xl text-white mb-2">Leaderboard Unavailable</h2>
        <p className="text-sm text-white/50 mb-6">Something went wrong loading the leaderboard.</p>
        <button
          onClick={reset}
          className="rounded-lg bg-yellow px-5 py-2.5 text-sm font-bold text-navy hover:bg-yellow/90 transition-colors"
        >
          Try Again
        </button>
      </motion.div>
    </div>
  );
}

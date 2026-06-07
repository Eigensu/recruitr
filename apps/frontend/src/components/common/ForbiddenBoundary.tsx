"use client";

import React from "react";
import { ForbiddenError } from "@/lib/api";

interface State {
  isForbidden: boolean;
}

export default class ForbiddenBoundary extends React.Component<
  { readonly children: React.ReactNode },
  State
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { isForbidden: false };
  }

  static getDerivedStateFromError(error: unknown): State | null {
    if (error instanceof ForbiddenError) return { isForbidden: true };
    return null;
  }

  componentDidCatch(error: unknown) {
    // Re-throw non-403 errors so Next.js default error handling takes over
    if (!(error instanceof ForbiddenError)) throw error;
  }

  render() {
    if (this.state.isForbidden) return <NoAccessScreen />;
    return this.props.children;
  }
}

function NoAccessScreen() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-6 bg-canvas px-6 text-center">
      {/* Lock icon */}
      <div className="relative flex items-center justify-center">
        <div className="absolute size-28 rounded-full bg-yellow/10 blur-2xl" />
        <div className="relative size-20 rounded-2xl bg-surface border border-border flex items-center justify-center shadow-lg">
          <svg
            className="size-10 text-yellow"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={1.5}
          >
            <rect x="3" y="11" width="18" height="11" rx="2" />
            <path d="M7 11V7a5 5 0 0 1 10 0v4" />
          </svg>
        </div>
      </div>

      {/* Text */}
      <div className="space-y-2 max-w-sm">
        <h1 className="text-2xl font-bold font-heading text-text-primary">Access Restricted</h1>
        <p className="text-sm text-text-secondary leading-relaxed">
          Your account has not been assigned to a workspace yet. Please contact your administrator
          to get access.
        </p>
      </div>

      {/* Error code badge */}
      <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-surface border border-border text-xs font-mono text-text-muted">
        <span className="size-1.5 rounded-full bg-yellow/60 inline-block" />
        HTTP 403 — Forbidden
      </span>
    </div>
  );
}

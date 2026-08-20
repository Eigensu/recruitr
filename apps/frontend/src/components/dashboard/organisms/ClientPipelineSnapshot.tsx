"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "motion/react";
import { IconAlertCircle, IconArrowRight, IconLayoutKanban } from "@tabler/icons-react";
import { DASHBOARD_PANEL_CLASS } from "@/components/common/constants/dashboard-constants";
import { cn } from "@/lib/utils";
import { clientFetchPipelineBoard } from "@/lib/api/pipeline-actions.client";
import PipelineActionRow, {
  actionGateFor,
} from "@/components/dashboard/molecules/PipelineActionRow";
import type { ClientStage } from "@/lib/constants/client-pipeline";
import type { PipelineCard } from "@/types";

interface StageCount {
  stage: ClientStage;
  label: string;
  count: number;
}

interface ClientPipelineSnapshotProps {
  stages: StageCount[];
  /** True when the stage-count fetch itself failed — kept distinct from "genuinely no candidates". */
  failed?: boolean;
}

const MAX_ACTION_ROWS = 5;

export default function ClientPipelineSnapshot({
  stages,
  failed = false,
}: ClientPipelineSnapshotProps) {
  const total = stages.reduce((sum, stage) => sum + stage.count, 0);
  const [actionable, setActionable] = useState<PipelineCard[] | null>(null);
  const [boardFailed, setBoardFailed] = useState(false);

  const loadActionable = useCallback(() => {
    clientFetchPipelineBoard()
      .then((board) => {
        const cards = board.stages.flatMap((col) => col.mappings).filter((c) => actionGateFor(c));
        setActionable(cards);
        setBoardFailed(false);
      })
      .catch(() => setBoardFailed(true));
  }, []);

  useEffect(() => {
    loadActionable();
  }, [loadActionable]);

  const showAggregate = actionable === null || actionable.length === 0;

  return (
    <motion.section
      initial={{ opacity: 0, y: 18 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.18 }}
      transition={{ duration: 0.45, ease: "easeOut", delay: 0.05 }}
      className={cn(DASHBOARD_PANEL_CLASS, "flex h-full flex-col p-5")}
      style={{ color: "var(--color-text-primary)" }}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="font-heading text-xl">Where Your Candidates Stand</h2>
          <p className="mt-1 text-sm" style={{ opacity: 0.6 }}>
            {failed
              ? "Live counts unavailable"
              : total > 0
                ? `${total} candidate${total === 1 ? "" : "s"} moving through your roles`
                : "No active candidates right now"}
          </p>
        </div>
        <Link
          href="/pipeline"
          className="flex shrink-0 items-center gap-1 text-xs font-bold text-yellow transition-opacity hover:opacity-80"
        >
          Open board <IconArrowRight className="size-3.5" />
        </Link>
      </div>

      {failed ? (
        <div
          className="flex flex-1 flex-col items-center justify-center gap-2 py-10 text-center"
          style={{ opacity: 0.5 }}
        >
          <IconAlertCircle className="size-8" style={{ opacity: 0.4 }} />
          <p className="max-w-60 text-sm">Couldn&apos;t load your pipeline right now.</p>
        </div>
      ) : total === 0 ? (
        <div
          className="flex flex-1 flex-col items-center justify-center gap-2 py-10 text-center"
          style={{ opacity: 0.5 }}
        >
          <IconLayoutKanban className="size-8" style={{ opacity: 0.4 }} />
          <p className="max-w-60 text-sm">
            Once candidates are sourced for your roles, they&apos;ll show up here.
          </p>
        </div>
      ) : !showAggregate ? (
        <div className="mt-5 flex-1 space-y-2.5 overflow-y-auto">
          {actionable!.slice(0, MAX_ACTION_ROWS).map((card) => {
            const gate = actionGateFor(card);
            if (!gate) return null;
            return (
              <PipelineActionRow
                key={card.mapping_id}
                card={card}
                gate={gate}
                onUpdated={loadActionable}
              />
            );
          })}
          {actionable!.length > MAX_ACTION_ROWS && (
            <Link
              href="/pipeline"
              className="block pt-1 text-center text-xs font-medium text-text-secondary hover:text-yellow"
            >
              +{actionable!.length - MAX_ACTION_ROWS} more awaiting action — view the full board
            </Link>
          )}
        </div>
      ) : (
        <div className="mt-5 flex-1 space-y-3.5">
          {boardFailed && (
            <p className="text-xs" style={{ opacity: 0.5 }}>
              Couldn&apos;t check for candidates awaiting your action.
            </p>
          )}
          {stages.map((stage) => (
            <div key={stage.stage}>
              <div className="flex items-center justify-between text-xs">
                <span className="font-medium" style={{ opacity: 0.8 }}>
                  {stage.label}
                </span>
                <span className="font-bold">{stage.count}</span>
              </div>
              <div
                className="mt-1 h-1.5 overflow-hidden rounded-full"
                style={{ background: "var(--color-border-val)" }}
              >
                <motion.div
                  className="h-full rounded-full bg-yellow"
                  initial={{ width: 0 }}
                  whileInView={{
                    width: `${(stage.count / Math.max(...stages.map((s) => s.count), 1)) * 100}%`,
                  }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.5, ease: "easeOut" }}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </motion.section>
  );
}

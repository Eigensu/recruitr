"use client";

import { motion } from "motion/react";
import { IconChartDots3, IconPercentage, IconRoute, IconTargetArrow } from "@tabler/icons-react";
import AnimatedNumber from "@/components/dashboard/AnimatedNumber";
import { DASHBOARD_PANEL_CLASS, TONE_CLASSES } from "@/lib/dashboard-constants";
import { cn } from "@/lib/utils";
import type { DashboardAnalyticsWidget } from "@/types/dashboard";

const iconMap = {
  fill_rate: IconPercentage,
  pipeline_depth: IconRoute,
  join_conversion: IconTargetArrow,
  seat_gap: IconChartDots3,
};

const valueClass = {
  yellow: "text-yellow",
  navy: "text-white",
  green: "text-emerald-200",
  red: "text-red-200",
  neutral: "text-white",
};

const parseAnimatedValue = (value: string) => {
  const suffix = value.endsWith("%") ? "%" : "";
  const numericValue = Number(value.replace("%", ""));

  return {
    value: Number.isFinite(numericValue) ? numericValue : 0,
    decimals: value.includes(".") ? 1 : 0,
    suffix,
  };
};

interface AnalyticsWidgetsProps {
  widgets: DashboardAnalyticsWidget[];
}

export default function AnalyticsWidgets({ widgets }: AnalyticsWidgetsProps) {
  return (
    <section className={cn(DASHBOARD_PANEL_CLASS, "p-5")}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="font-heading text-xl text-white">Analytics Widgets</h2>
          <p className="mt-1 text-sm text-white/50">Derived from synced client activity</p>
        </div>
        <IconChartDots3 className="size-6 text-yellow" />
      </div>

      <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {widgets.map((widget, index) => {
          const tone = TONE_CLASSES[widget.tone];
          const Icon = iconMap[widget.id as keyof typeof iconMap] ?? IconChartDots3;
          const animatedValue = parseAnimatedValue(widget.value);

          return (
            <motion.article
              key={widget.id}
              initial={{ opacity: 0, y: 10 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.35 }}
              transition={{ duration: 0.35, delay: index * 0.04, ease: "easeOut" }}
              whileHover={{ y: -2 }}
              className="rounded-lg border border-white/10 bg-white/[0.035] p-4"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-normal text-white/45">
                    {widget.label}
                  </p>
                  <p className={cn("mt-2 font-heading text-3xl", valueClass[widget.tone])}>
                    <AnimatedNumber
                      value={animatedValue.value}
                      decimals={animatedValue.decimals}
                      suffix={animatedValue.suffix}
                    />
                  </p>
                </div>
                <div
                  className={cn("flex size-9 items-center justify-center rounded-lg", tone.chip)}
                >
                  <Icon className="size-5" />
                </div>
              </div>
              <p className="mt-4 text-sm text-white/55">{widget.helper}</p>
            </motion.article>
          );
        })}
      </div>
    </section>
  );
}

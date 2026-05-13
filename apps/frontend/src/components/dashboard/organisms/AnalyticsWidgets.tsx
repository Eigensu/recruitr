"use client";

import { motion } from "motion/react";
import { IconChartDots3, IconPercentage, IconRoute, IconTargetArrow } from "@tabler/icons-react";
import DashboardKpiCard from "@/components/dashboard/molecules/DashboardKpiCard";
import AnimatedNumber from "@/components/dashboard/atoms/AnimatedNumber";
import {
  DASHBOARD_PANEL_CLASS,
  DASHBOARD_WIDGET_CLASS,
  TONE_CLASSES,
  ANALYTICS_ICON_MAP,
} from "@/components/common/constants/dashboard-constants";
import { cn } from "@/lib/utils";
import type { DashboardAnalyticsWidget } from "@/types/dashboard";

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
          <p className="mt-1 text-sm text-white">Derived from synced client activity</p>
        </div>
        <IconChartDots3 className="size-6 text-yellow" />
      </div>

      <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2">
        {widgets.map((widget, index) => {
          const tone = TONE_CLASSES[widget.tone];
          const Icon =
            ANALYTICS_ICON_MAP[widget.id as keyof typeof ANALYTICS_ICON_MAP] ?? IconChartDots3;
          const animatedValue = parseAnimatedValue(widget.value);

          return (
            <motion.article
              key={widget.id}
              initial={{ opacity: 0, y: 10 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.35 }}
              transition={{ duration: 0.35, delay: index * 0.04, ease: "easeOut" }}
              whileHover={{ y: -2 }}
              className={cn(DASHBOARD_WIDGET_CLASS, "transition-transform")}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-normal text-white">
                    {widget.label}
                  </p>
                  <p className={cn("mt-2 font-heading text-3xl", tone.value)}>
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
              <p className="mt-4 text-sm text-white">{widget.helper}</p>
            </motion.article>
          );
        })}
      </div>
    </section>
  );
}

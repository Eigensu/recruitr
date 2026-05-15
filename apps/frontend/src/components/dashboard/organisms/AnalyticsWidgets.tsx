"use client";

import { motion } from "motion/react";
import { IconChartDots3 } from "@tabler/icons-react";
import AnimatedNumber from "@/components/dashboard/atoms/AnimatedNumber";
import {
  DASHBOARD_PANEL_CLASS,
  DASHBOARD_WIDGET_CLASS,
  TONE_STYLES,
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

export default function AnalyticsWidgets({ widgets }: Readonly<AnalyticsWidgetsProps>) {
  return (
    <section className={cn(DASHBOARD_PANEL_CLASS, "p-5")}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="font-heading text-xl" style={{ color: "var(--color-text-primary)" }}>
            Analytics Widgets
          </h2>
          <p className="mt-1 text-sm" style={{ color: "var(--color-text-secondary)" }}>
            Derived from synced client activity
          </p>
        </div>
        <IconChartDots3 className="size-6 text-yellow" />
      </div>

      <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2">
        {widgets.map((widget, index) => {
          const tone = TONE_STYLES[widget.tone];
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
              style={{ background: tone.cardBg, color: tone.cardText }}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p
                    className="text-xs font-semibold uppercase tracking-normal"
                    style={{ opacity: 0.6 }}
                  >
                    {widget.label}
                  </p>
                  <p className="mt-2 font-heading text-3xl">
                    <AnimatedNumber
                      value={animatedValue.value}
                      decimals={animatedValue.decimals}
                      suffix={animatedValue.suffix}
                    />
                  </p>
                </div>
                <div
                  className="flex size-9 items-center justify-center rounded-lg"
                  style={{ background: tone.chipBg, color: tone.chipText }}
                >
                  <Icon className="size-5" />
                </div>
              </div>
              <p className="mt-4 text-sm" style={{ opacity: 0.7 }}>
                {widget.helper}
              </p>
            </motion.article>
          );
        })}
      </div>
    </section>
  );
}

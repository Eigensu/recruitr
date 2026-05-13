"use client";

import { useEffect, useRef, useState } from "react";
import { useInView } from "motion/react";

interface AnimatedNumberProps {
  value: number;
  decimals?: number;
  duration?: number;
  suffix?: string;
  prefix?: string;
  locale?: string;
}

export default function AnimatedNumber({
  value,
  decimals = 0,
  duration = 900,
  suffix = "",
  prefix = "",
  locale = "en-IN",
}: AnimatedNumberProps) {
  const ref = useRef<HTMLSpanElement>(null);
  const isInView = useInView(ref, { once: true, amount: 0.6 });
  const [displayValue, setDisplayValue] = useState(0);
  const startValueRef = useRef(0);

  useEffect(() => {
    if (!isInView) return;

    let frame = 0;
    let startTime = 0;
    const startValue = startValueRef.current;
    const diff = value - startValue;

    if (diff === 0) {
      setDisplayValue(value);
      return;
    }

    const tick = (timestamp: number) => {
      if (!startTime) startTime = timestamp;

      const progress = Math.min((timestamp - startTime) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);

      setDisplayValue(startValue + diff * eased);

      if (progress < 1) {
        frame = window.requestAnimationFrame(tick);
      } else {
        startValueRef.current = value;
      }
    };

    frame = window.requestAnimationFrame(tick);

    return () => window.cancelAnimationFrame(frame);
  }, [duration, isInView, value]);

  return (
    <span ref={ref}>
      {prefix}
      {displayValue.toLocaleString(locale, {
        maximumFractionDigits: decimals,
        minimumFractionDigits: decimals,
      })}
      {suffix}
    </span>
  );
}

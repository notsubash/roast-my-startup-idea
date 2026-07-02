"use client";

import { useEffect, useRef, useState } from "react";

function prefersReducedMotion(): boolean {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** ponytail: rAF lerp; upgrade path is spring lib if we need choreography. */
export function useAnimatedNumber(
  target: number | null | undefined,
  duration = 250,
  animateFrom?: number | null,
): number | null {
  const initial = animateFrom ?? target ?? null;
  const [display, setDisplay] = useState<number | null>(initial);
  const fromRef = useRef<number | null>(initial);

  useEffect(() => {
    if (target == null) {
      setDisplay(null);
      fromRef.current = null;
      return;
    }

    if (prefersReducedMotion()) {
      setDisplay(target);
      fromRef.current = target;
      return;
    }

    const from = animateFrom ?? fromRef.current ?? target;
    const start = performance.now();
    let frame = 0;

    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - (1 - t) ** 3;
      const next = Math.round((from + (target - from) * eased) * 10) / 10;
      setDisplay(next);
      if (t < 1) {
        frame = requestAnimationFrame(tick);
      } else {
        fromRef.current = target;
      }
    };

    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [target, duration, animateFrom]);

  return display;
}

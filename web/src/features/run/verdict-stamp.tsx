"use client";

import { AlertTriangle, CheckCircle, HelpCircle } from "lucide-react";

import type { VerdictLabel } from "@/lib/sse/types";
import { cn } from "@/lib/utils";

export type { VerdictLabel };

const STAMP_CONFIG: Record<
  VerdictLabel,
  { Icon: typeof CheckCircle; className: string; label: string }
> = {
  PASS: {
    Icon: CheckCircle,
    className: "border-pass text-pass",
    label: "PASS",
  },
  FAIL: {
    Icon: AlertTriangle,
    className: "border-fail text-fail",
    label: "FAIL",
  },
  CONDITIONAL: {
    Icon: HelpCircle,
    className: "border-conditional text-conditional",
    label: "CONDITIONAL",
  },
};

export function VerdictStamp({
  verdict,
  animate = false,
  className,
}: {
  verdict: VerdictLabel;
  animate?: boolean;
  className?: string;
}) {
  const { Icon, className: verdictClass, label } = STAMP_CONFIG[verdict];

  return (
    <div
      className={cn(
        "inline-flex items-center gap-2 border-2 bg-card px-4 py-2 font-sans text-sm font-extrabold uppercase tracking-widest shadow-hard -rotate-3",
        verdictClass,
        animate && "animate-stamp-slam",
        className,
      )}
      role="img"
      aria-label={`Verdict: ${label}`}
    >
      <Icon className="size-5 shrink-0" aria-hidden />
      {label}
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";

import { apiClient, type HealthResponse } from "@/lib/api/client";

type HealthState = "loading" | "ok" | "down";

export function HealthStatus() {
  const [state, setState] = useState<HealthState>("loading");

  useEffect(() => {
    let cancelled = false;

    async function check() {
      try {
        const data = await apiClient<HealthResponse>("/health", {
          cache: "no-store",
        });
        if (cancelled) return;
        setState(data.status === "ok" ? "ok" : "down");
      } catch {
        if (!cancelled) setState("down");
      }
    }

    void check();
    const id = window.setInterval(check, 60_000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  const label =
    state === "loading"
      ? "Checking API status"
      : state === "ok"
        ? "API online"
        : "API offline";

  const dotClass =
    state === "loading"
      ? "bg-ink-subtle animate-pulse"
      : state === "ok"
        ? "bg-pass"
        : "bg-fail";

  return (
    <span className="inline-flex items-center gap-2 font-sans text-xs text-ink-subtle">
      <span aria-hidden="true" className={`size-2 shrink-0 rounded-full ${dotClass}`} />
      <span>{label}</span>
    </span>
  );
}

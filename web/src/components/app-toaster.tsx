"use client";

import { Toaster } from "sonner";

export function AppToaster() {
  return (
    <Toaster
      position="bottom-right"
      toastOptions={{
        classNames: {
          toast:
            "font-sans rounded-ui border border-rule-soft bg-card text-ink shadow-soft",
          title: "font-semibold",
          description: "text-ink-muted",
        },
      }}
    />
  );
}

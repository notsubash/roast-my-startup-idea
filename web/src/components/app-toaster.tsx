"use client";

import { Toaster } from "sonner";

export function AppToaster() {
  return (
    <Toaster
      position="bottom-right"
      toastOptions={{
        classNames: {
          toast:
            "font-sans border-2 border-ink bg-card text-ink shadow-hard rounded-ui",
          title: "font-semibold",
          description: "text-ink-muted",
        },
      }}
    />
  );
}

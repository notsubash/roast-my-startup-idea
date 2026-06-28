"use client";

import Link from "next/link";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { OctagonX, Share2 } from "lucide-react";

import { ApiError } from "@/lib/api/client";
import { cancelRun } from "@/lib/api/runs";
import { parseApiDetail } from "@/lib/api/types-helpers";
import { secondaryCtaClass, heatCtaClass } from "@/lib/cta-classes";
import type { RunStatus } from "@/lib/sse/types";
import { Button } from "@/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/ui/dialog";

export function RunControls({
  runId,
  status,
  onCancelSettled,
}: {
  runId: string;
  status: RunStatus;
  /** Refetch run status after cancel succeeds or run already finished (409). */
  onCancelSettled?: () => void;
}) {
  const [confirmOpen, setConfirmOpen] = useState(false);
  const canStop = status === "running" || status === "created" || status === "connecting";
  const isTerminal = status === "completed" || status === "failed" || status === "cancelled";

  const cancelMutation = useMutation({
    mutationFn: () => cancelRun(runId),
    onSuccess: () => {
      setConfirmOpen(false);
      onCancelSettled?.();
    },
    onError: (error) => {
      if (error instanceof ApiError) {
        if (error.status === 409) {
          toast.info("This run already finished.");
          setConfirmOpen(false);
          onCancelSettled?.();
          return;
        }
        const detail = parseApiDetail(error.body);
        toast.error(detail ?? "Could not cancel the run.");
        return;
      }
      toast.error("Could not cancel the run. Check your connection.");
    },
  });

  const share = async () => {
    const url = window.location.href;
    try {
      await navigator.clipboard.writeText(url);
      toast.success("Link copied — share the verdict.");
    } catch {
      toast.error("Could not copy the link.");
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-3">
      {canStop && (
        <>
          <Button
            type="button"
            variant="outline"
            className="gap-2"
            onClick={() => setConfirmOpen(true)}
            disabled={cancelMutation.isPending}
          >
            <OctagonX className="size-4" aria-hidden />
            Stop
          </Button>
          <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Stop this roast?</DialogTitle>
                <DialogDescription>
                  The judges will halt between turns. You can always submit a new idea.
                </DialogDescription>
              </DialogHeader>
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setConfirmOpen(false)}>
                  Keep going
                </Button>
                <Button
                  type="button"
                  variant="destructive"
                  disabled={cancelMutation.isPending}
                  onClick={() => cancelMutation.mutate()}
                >
                  {cancelMutation.isPending ? "Stopping…" : "Stop the run"}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </>
      )}

      {isTerminal && (
        <button type="button" className={`inline-flex items-center gap-2 ${secondaryCtaClass}`} onClick={share}>
          <Share2 className="size-4" aria-hidden />
          Share link
        </button>
      )}

      {isTerminal && (
        <Link href="/" className={heatCtaClass}>
          Roast another idea
        </Link>
      )}
    </div>
  );
}

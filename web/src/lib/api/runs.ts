import { apiClient } from "./client";
import type { CreateRunRequest, RunCreatedResponse, RunStatusResponse } from "./types-helpers";

export async function createRun(body: CreateRunRequest): Promise<RunCreatedResponse> {
  return apiClient<RunCreatedResponse>("/api/runs", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getRunStatus(runId: string): Promise<RunStatusResponse> {
  return apiClient<RunStatusResponse>(`/api/runs/${runId}`);
}

export async function cancelRun(runId: string): Promise<RunStatusResponse> {
  return apiClient<RunStatusResponse>(`/api/runs/${runId}/cancel`, {
    method: "POST",
  });
}

import { apiClient } from "./client";
import type {
  AppealRequest,
  AppealResponse,
  CreateRunRequest,
  RunCreatedResponse,
  RunListResponse,
  RunPanelResponse,
  RunStatusResponse,
  SimilarRunsResponse,
} from "./types-helpers";

export async function createRun(body: CreateRunRequest): Promise<RunCreatedResponse> {
  return apiClient<RunCreatedResponse>("/api/runs", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function listRuns(params?: {
  limit?: number;
  offset?: number;
}): Promise<RunListResponse> {
  const search = new URLSearchParams();
  if (params?.limit != null) search.set("limit", String(params.limit));
  if (params?.offset != null) search.set("offset", String(params.offset));
  const qs = search.toString();
  return apiClient<RunListResponse>(`/api/runs${qs ? `?${qs}` : ""}`);
}

export async function getRunStatus(runId: string): Promise<RunStatusResponse> {
  return apiClient<RunStatusResponse>(`/api/runs/${runId}`);
}

export async function cancelRun(runId: string): Promise<RunStatusResponse> {
  return apiClient<RunStatusResponse>(`/api/runs/${runId}/cancel`, {
    method: "POST",
  });
}

export async function submitAppeal(
  runId: string,
  body: AppealRequest,
): Promise<AppealResponse> {
  return apiClient<AppealResponse>(`/api/runs/${runId}/appeal`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getRunPanel(runId: string): Promise<RunPanelResponse> {
  return apiClient<RunPanelResponse>(`/api/runs/${runId}/panel`);
}

export async function getSimilarRuns(
  runId: string,
  params?: { limit?: number },
): Promise<SimilarRunsResponse> {
  const search = new URLSearchParams();
  if (params?.limit != null) search.set("limit", String(params.limit));
  const qs = search.toString();
  return apiClient<SimilarRunsResponse>(
    `/api/runs/${runId}/similar${qs ? `?${qs}` : ""}`,
  );
}

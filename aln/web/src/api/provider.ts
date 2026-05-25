/* Provider check API. */

import axios from "axios";

import type { StandardResponse } from "@/types";
import { apiClient } from "./client";

export interface ProviderCheckResult {
  available: boolean;
  provider: string;
  version: string | null;
  executable_path: string | null;
  error: string | null;
}

function isStandardResponse(
  data: StandardResponse<ProviderCheckResult> | ProviderCheckResult,
): data is StandardResponse<ProviderCheckResult> {
  return typeof data === "object" && data !== null && "data" in data;
}

export async function checkProvider(
  provider: string,
): Promise<ProviderCheckResult> {
  const { data } = await apiClient.post<
    StandardResponse<ProviderCheckResult> | ProviderCheckResult
  >(
    "/providers/check",
    { provider },
  );
  if (isStandardResponse(data)) {
    if (data.data) {
      return data.data;
    }
    throw new Error(data.message || "Provider check returned empty data");
  }
  return data;
}

export function getProviderCheckErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string" && detail) {
      return detail;
    }
    if (typeof error.message === "string" && error.message) {
      return error.message;
    }
  }

  if (error instanceof Error && error.message) {
    return error.message;
  }

  return "Failed to check";
}

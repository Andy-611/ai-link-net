/* Host topology API helpers for discover page. */

import axios from "axios";

import type { HostWellKnown, StandardResponse } from "@/types";

import { apiClient, unwrap } from "./client";

const REQUEST_TIMEOUT_MS = 8000;

export function normalizeHostUrl(hostUrl: string): string {
  const trimmed = hostUrl.trim().replace(/\/$/, "");
  if (!trimmed) return "";

  try {
    const parsed = new URL(trimmed);
    const isHttpProtocol = parsed.protocol === "http:" || parsed.protocol === "https:";
    if (!isHttpProtocol || parsed.port === "0") {
      return "";
    }
    return `${parsed.protocol}//${parsed.host}`;
  } catch {
    return "";
  }
}

export async function fetchHostEndpoint<T>(hostUrl: string, path: string): Promise<T> {
  const normalizedHostUrl = normalizeHostUrl(hostUrl);
  if (!normalizedHostUrl) {
    throw new Error(`Invalid host URL: ${hostUrl}`);
  }
  const url = `${normalizedHostUrl}${path}`;
  const { data } = await axios.get<StandardResponse<T>>(url, {
    timeout: REQUEST_TIMEOUT_MS,
  });
  return unwrap(data);
}

export async function getParentHost(): Promise<HostWellKnown | null> {
  try {
    const { data } = await apiClient.get<StandardResponse<HostWellKnown | null>>("/parent");
    return unwrap(data);
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 404) {
      return null;
    }
    throw error;
  }
}

export async function listChildHosts(): Promise<HostWellKnown[]> {
  const { data } = await apiClient.get<StandardResponse<HostWellKnown[]>>("/children");
  return data.data ?? [];
}

export async function fetchHostWellKnown(hostUrl: string): Promise<HostWellKnown> {
  return fetchHostEndpoint(hostUrl, "/.well-known");
}

export async function fetchHostParent(hostUrl: string): Promise<HostWellKnown | null> {
  try {
    return await fetchHostEndpoint<HostWellKnown | null>(hostUrl, "/api/v1/parent");
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 404) {
      return null;
    }
    return null;
  }
}

export async function fetchHostChildren(hostUrl: string): Promise<HostWellKnown[]> {
  try {
    return await fetchHostEndpoint(hostUrl, "/api/v1/children");
  } catch {
    return [];
  }
}

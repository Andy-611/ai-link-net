/* Entity API. */

import type { Contact, EntityCard, StandardResponse } from "@/types";
import { apiClient, apiUrl, unwrap } from "./client";

export async function listEntities(): Promise<Contact[]> {
  const { data } = await apiClient.get<StandardResponse<Contact[]>>("/entities");
  return data.data ?? [];
}

export async function getEntity(uid: string): Promise<Contact> {
  const { data } = await apiClient.get<StandardResponse<Contact>>(
    `/entities/${uid}`,
  );
  return unwrap(data);
}

export async function discoverEntities(): Promise<Contact[]> {
  const { data } = await apiClient.get<StandardResponse<Contact[]>>(
    "/entities/discover",
  );
  return data.data ?? [];
}

export async function updateEntity(
  uid: string,
  payload: { name?: string; description?: string; is_public?: boolean },
): Promise<Contact> {
  const { data } = await apiClient.post<StandardResponse<Contact>>(
    `/entities/${uid}`,
    payload,
  );
  return unwrap(data);
}

export async function deleteEntity(uid: string): Promise<void> {
  await apiClient.delete(`/entities/${uid}`);
}

export async function getEntityCard(address: string): Promise<EntityCard> {
  const { data } = await apiClient.get<StandardResponse<EntityCard>>(
    `/entities/card/${address}`,
  );
  return unwrap(data);
}

export async function fetchAvatarAsDataUrl(uid: string): Promise<string | null> {
  try {
    const url = apiUrl(`/entities/${uid}/avatar`);
    const res = await fetch(url);
    if (!res.ok) return null;
    const blob = await res.blob();
    return await new Promise<string>((resolve) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(reader.result as string);
      reader.readAsDataURL(blob);
    });
  } catch {
    return null;
  }
}

export async function uploadAvatar(uid: string, file: File): Promise<void> {
  const form = new FormData();
  form.append("file", file);
  await apiClient.post(`/entities/${uid}/avatar`, form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
}

export async function deleteAvatar(uid: string): Promise<void> {
  await apiClient.delete(`/entities/${uid}/avatar`);
}

export async function listFriends(uid: string): Promise<Contact[]> {
  const { data } = await apiClient.get<StandardResponse<Contact[]>>(
    `/entities/${uid}/friends`,
  );
  return data.data ?? [];
}

export async function getFriendsStatus(
  uid: string,
): Promise<Record<string, string>> {
  const { data } = await apiClient.get<StandardResponse<Record<string, string>>>(
    `/entities/${uid}/friends/status`,
  );
  return data.data ?? {};
}

export interface BatchMember {
  name: string;
  kind: string;
  provider?: string;
  description?: string;
  is_public?: boolean;
  trust_level?: string;
  model?: string;
  workdir?: string;
}

export async function registerBatch(payload: {
  organization_name: string;
  members: BatchMember[];
  auto_friend?: boolean;
}): Promise<Contact[]> {
  const { data } = await apiClient.post<StandardResponse<Contact[]>>(
    "/entities/batch",
    payload,
  );
  return data.data ?? [];
}

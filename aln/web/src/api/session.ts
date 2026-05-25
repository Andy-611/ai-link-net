/* Session API. */

import type { StandardResponse } from "@/types";
import { apiClient, unwrap } from "./client";

export interface SessionInfo {
  session_id: string;
  name: string | null;
  participants: string[];
  created_at: number;
  updated_at: number;
  message_count: number;
}

export async function listSessions(
  entityUid: string,
  contactUid?: string,
): Promise<SessionInfo[]> {
  const { data } = await apiClient.get<StandardResponse<SessionInfo[]>>(
    `/entities/${entityUid}/sessions`,
    { params: contactUid ? { contact_uid: contactUid } : undefined },
  );
  return data.data ?? [];
}

export async function createSession(
  entityUid: string,
  contactUid: string,
  name?: string,
): Promise<SessionInfo> {
  const { data } = await apiClient.post<StandardResponse<SessionInfo>>(
    `/entities/${entityUid}/sessions`,
    { contact_uid: contactUid, name },
  );
  return unwrap(data);
}

export async function renameSession(
  entityUid: string,
  sessionId: string,
  name: string,
): Promise<SessionInfo> {
  const { data } = await apiClient.post<StandardResponse<SessionInfo>>(
    `/entities/${entityUid}/sessions/${sessionId}/rename`,
    { name },
  );
  return unwrap(data);
}

export async function deleteSession(
  entityUid: string,
  sessionId: string,
): Promise<void> {
  await apiClient.delete(`/entities/${entityUid}/sessions/${sessionId}`);
}

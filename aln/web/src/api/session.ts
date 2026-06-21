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
  session_type?: "direct" | "group" | string;
  created_by?: string | null;
  members?: GroupMemberInfo[];
}

export interface GroupMemberInfo {
  address: string;
  entity_uid: string;
  host_uid: string;
  name: string;
  kind: string;
  role: "owner" | "admin" | "member" | "observer" | string;
  status: "active" | "removed" | string;
  can_send: boolean;
  can_invite: boolean;
  can_remove: boolean;
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

export async function listGroupSessions(
  entityUid: string,
): Promise<SessionInfo[]> {
  const { data } = await apiClient.get<StandardResponse<SessionInfo[]>>(
    `/entities/${entityUid}/sessions/groups`,
  );
  return data.data ?? [];
}

export async function createGroupSession(
  entityUid: string,
  name: string,
  members: string[],
  memberRoles: Record<string, string> = {},
): Promise<SessionInfo> {
  const { data } = await apiClient.post<StandardResponse<SessionInfo>>(
    `/entities/${entityUid}/sessions/groups`,
    { name, members, member_roles: memberRoles },
  );
  return unwrap(data);
}

export async function addGroupMembers(
  entityUid: string,
  sessionId: string,
  members: string[],
  memberRoles: Record<string, string> = {},
): Promise<SessionInfo> {
  const { data } = await apiClient.post<StandardResponse<SessionInfo>>(
    `/entities/${entityUid}/sessions/groups/${sessionId}/members`,
    { members, member_roles: memberRoles },
  );
  return unwrap(data);
}

export async function removeGroupMember(
  entityUid: string,
  sessionId: string,
  member: string,
): Promise<SessionInfo> {
  const { data } = await apiClient.post<StandardResponse<SessionInfo>>(
    `/entities/${entityUid}/sessions/groups/${sessionId}/members/remove`,
    { member },
  );
  return unwrap(data);
}

export async function deleteGroupSession(
  entityUid: string,
  sessionId: string,
): Promise<void> {
  const { data } = await apiClient.delete<StandardResponse<Record<string, never>>>(
    `/entities/${entityUid}/sessions/groups/${sessionId}`,
  );
  unwrap(data);
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

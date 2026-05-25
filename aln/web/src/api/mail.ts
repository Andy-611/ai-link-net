/* Message send & history API. */

import type { StandardResponse } from "@/types";
import { apiClient, unwrap } from "./client";

export interface SendMessageResponse {
  message_id: string;
  mail_id: string;
  from_entity_uid: string;
  to_address: string;
  session_id: string | null;
  delivery_status: "sent" | "offline" | "unreachable";
  warning: string | null;
  status: string;
}

export interface MailboxMessage {
  message_id: string;
  mail_id: string;
  kind?: string;
  sender: string;
  recipient: string[];
  payload: Record<string, unknown>;
  timestamp: string;
  direction: "inbound" | "outbound";
  is_read: boolean;
  status: string;
}

export async function sendMessage(
  fromEntity: string,
  toAddress: string,
  payload: { text: string; metadata?: Record<string, unknown> },
  sessionId?: string,
): Promise<SendMessageResponse> {
  const { data } = await apiClient.post<StandardResponse<SendMessageResponse>>(
    "/messages/send",
    {
      from_entity: fromEntity,
      to_address: toAddress,
      text: payload.text,
      session_id: sessionId,
    },
  );
  return unwrap(data);
}

export async function getMessages(
  entityUid: string,
  limit = 100,
): Promise<MailboxMessage[]> {
  const { data } = await apiClient.get<StandardResponse<MailboxMessage[]>>(
    `/messages/${entityUid}`,
    { params: { limit } },
  );
  return data.data ?? [];
}

export async function markMessagesRead(
  entityUid: string,
  messageIds: string[],
): Promise<void> {
  await apiClient.post(`/messages/${entityUid}/mark_read`, {
    message_ids: messageIds,
  });
}

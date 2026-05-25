/* Friend API. */

import type { StandardResponse } from "@/types";
import { apiClient } from "./client";

export async function addFriend(
  fromEntity: string,
  toAddress: string,
  text?: string,
): Promise<void> {
  await apiClient.post<StandardResponse>("/friends/add", {
    from_entity: fromEntity,
    to_address: toAddress,
    text: text ?? "Hi, let's connect!",
  });
}

export async function deleteFriend(
  fromEntity: string,
  friendUid: string,
): Promise<void> {
  await apiClient.post<StandardResponse>("/friends/delete", {
    from_entity: fromEntity,
    friend_uid: friendUid,
  });
}

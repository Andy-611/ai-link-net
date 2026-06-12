/* Group collaboration room: member roster + virtual meeting room + history. */

import {
  type CSSProperties,
  type PointerEvent as ReactPointerEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { motion } from "framer-motion";
import {
  Activity,
  ArrowLeft,
  Bot,
  Check,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Gauge,
  GripHorizontal,
  GripVertical,
  History,
  Loader2,
  Plus,
  Radio,
  RefreshCw,
  Send,
  Shield,
  Trash2,
  UserMinus,
  UserPlus,
  UserRound,
  Users,
  Zap,
} from "lucide-react";

import {
  addGroupMembers,
  createGroupSession,
  deleteGroupSession,
  getMessages,
  markMessagesRead,
  removeGroupMember,
  sendGroupMessage,
} from "@/api";
import type { MailboxMessage, SessionInfo, GroupMemberInfo } from "@/api";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useWsListener } from "@/providers/websocket-provider";
import { useAppStore } from "@/stores/app";
import type { Contact, Message, MessagePayload } from "@/types";
import { cn, extractEntityUid, kindAvatarClass, normalizeTimestamp } from "@/lib/utils";
import type { WsEvent } from "@/hooks/use-websocket";

interface GroupRoomListProps {
  rooms: SessionInfo[];
  selectedRoomId?: string | null;
  loading?: boolean;
  onSelect: (room: SessionInfo) => void;
  onCreate: () => void;
  onRefresh: () => void;
}

interface CreateGroupDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: (room: SessionInfo) => void;
}

interface AddGroupMembersDialogProps {
  open: boolean;
  room: SessionInfo;
  activeMemberIds: Set<string>;
  onOpenChange: (open: boolean) => void;
  onUpdated: (room: SessionInfo) => void;
}

interface GroupRoomProps {
  room: SessionInfo;
  onBack?: () => void;
  onRefreshRooms?: () => void;
  onRoomUpdated?: (room: SessionInfo) => void;
  onRoomDeleted?: (roomId: string) => void;
}

interface ContactPickerProps {
  contacts: Contact[];
  selectedMemberIds: Set<string>;
  emptyText: string;
  onToggle: (uid: string) => void;
}

const ROLE_STYLES: Record<string, string> = {
  owner: "border-accent/30 bg-accent/10 text-accent",
  admin: "border-success/30 bg-success/10 text-success",
  member: "border-border bg-surface text-muted-foreground",
  observer: "border-warning/30 bg-warning/10 text-warning",
};

const KIND_ICONS: Record<string, typeof Bot> = {
  agent: Bot,
  human: UserRound,
  tool: Zap,
  service: Radio,
  resource: Shield,
};

function memberIcon(kind: string) {
  return KIND_ICONS[kind] ?? Users;
}

function estimateTokens(text: string): number {
  return Math.max(1, Math.ceil(text.length / 4));
}

function memberDisplayInitials(name: string): string {
  return name.trim().slice(0, 2).toUpperCase() || "FP";
}

function roomTimeLabel(timestamp?: string): string {
  if (!timestamp) return "";
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function groupIdFromMailbox(m: MailboxMessage): string | null {
  const payload = m.payload as Record<string, unknown>;
  const metadata = m.metadata ?? {};
  const raw =
    m.group_id ??
    metadata.group_id ??
    payload.session_id ??
    null;
  return typeof raw === "string" ? raw : null;
}

function mailboxToGroupMessage(m: MailboxMessage, roomId: string): Message | null {
  if (groupIdFromMailbox(m) !== roomId) return null;
  const payload = m.payload as Record<string, unknown>;
  const text = String(payload.text ?? "");

  return {
    message_id: m.message_id,
    mail_id: m.mail_id,
    kind: m.kind,
    sender: m.sender,
    recipient: m.recipient,
    payload: {
      ...payload,
      text,
    } as MessagePayload,
    metadata: m.metadata,
    conversation_type: m.conversation_type,
    group_id: m.group_id ?? roomId,
    timestamp: normalizeTimestamp(m.timestamp),
    status: m.status as Message["status"],
    session_id: typeof payload.session_id === "string" ? payload.session_id : roomId,
  };
}

function isRoomWsMessage(message: Message, roomId: string): boolean {
  const metadata = message.metadata ?? {};
  return (
    message.group_id === roomId ||
    message.session_id === roomId ||
    metadata.group_id === roomId
  );
}

function memberAddress(member: GroupMemberInfo): string {
  return member.address || `${member.host_uid}:${member.entity_uid}`;
}

function memberByUid(
  members: GroupMemberInfo[],
  uidOrAddress: string,
): GroupMemberInfo | undefined {
  const uid = extractEntityUid(uidOrAddress);
  return members.find(
    (member) =>
      member.entity_uid === uid ||
      member.address === uidOrAddress,
  );
}

function mergeRoomMembers(room: SessionInfo): GroupMemberInfo[] {
  return (room.members ?? [])
    .filter((member) => member.status !== "removed")
    .sort((a, b) => {
      const roleOrder: Record<string, number> = { owner: 0, admin: 1, member: 2, observer: 3 };
      return (roleOrder[a.role] ?? 9) - (roleOrder[b.role] ?? 9) || a.name.localeCompare(b.name);
    });
}

function canRemoveMember(
  currentMember: GroupMemberInfo | undefined,
  member: GroupMemberInfo,
): boolean {
  return Boolean(
    currentMember?.can_remove &&
    member.role !== "owner" &&
    member.address !== currentMember.address,
  );
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Request failed";
}

function ContactPicker({
  contacts,
  selectedMemberIds,
  emptyText,
  onToggle,
}: ContactPickerProps) {
  return (
    <div className="max-h-72 overflow-y-auto rounded-lg border border-border">
      {contacts.length === 0 && (
        <div className="p-6 text-center text-sm text-muted-foreground">
          {emptyText}
        </div>
      )}
      {contacts.map((contact) => {
        const selected = selectedMemberIds.has(contact.entity_uid);
        const Icon = memberIcon(contact.kind);
        return (
          <button
            key={contact.entity_uid}
            type="button"
            onClick={() => onToggle(contact.entity_uid)}
            className={cn(
              "flex w-full items-center gap-3 border-b border-border px-3 py-2.5 text-left last:border-b-0 hover:bg-surface",
              selected && "bg-primary/5",
            )}
          >
            <div className="relative flex h-5 w-5 shrink-0 items-center justify-center rounded border border-border">
              {selected && <Check className="h-3.5 w-3.5 text-primary" />}
            </div>
            <Avatar className="h-8 w-8 border border-border">
              <AvatarFallback className={cn("text-xs", kindAvatarClass(contact.kind))}>
                {memberDisplayInitials(contact.name)}
              </AvatarFallback>
            </Avatar>
            <div className="min-w-0 flex-1">
              <div className="flex min-w-0 items-center gap-2">
                <span className="truncate text-sm font-medium">{contact.name}</span>
                <Icon className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
              </div>
              <p className="truncate text-[11px] text-muted-foreground">
                {contact.address?.address ?? contact.entity_uid}
              </p>
            </div>
          </button>
        );
      })}
    </div>
  );
}

export function GroupRoomList({
  rooms,
  selectedRoomId,
  loading,
  onSelect,
  onCreate,
  onRefresh,
}: GroupRoomListProps) {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-center gap-2 px-3 py-2">
        <Button size="sm" className="flex-1" onClick={onCreate}>
          <Plus className="h-4 w-4" />
          Room
        </Button>
        <Button size="icon-sm" variant="ghost" onClick={onRefresh} disabled={loading} title="Refresh rooms">
          <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
        </Button>
      </div>
      <ScrollArea className="min-h-0 flex-1">
        <div className="space-y-1 p-2">
          {loading && rooms.length === 0 && (
            <div className="flex items-center justify-center py-10">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          )}
          {!loading && rooms.length === 0 && (
            <div className="px-3 py-10 text-center">
              <div className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-lg border border-border bg-surface">
                <Users className="h-5 w-5 text-muted-foreground" />
              </div>
              <p className="text-xs font-medium text-foreground/70">No rooms</p>
              <p className="mt-1 text-[11px] text-muted-foreground">Create one with friends</p>
            </div>
          )}
          {rooms.map((room, index) => {
            const active = room.session_id === selectedRoomId;
            const members = mergeRoomMembers(room);
            return (
              <motion.button
                key={room.session_id}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.025, duration: 0.2 }}
                onClick={() => onSelect(room)}
                className={cn(
                  "w-full overflow-hidden rounded-lg border px-3 py-2.5 text-left transition-colors",
                  active
                    ? "border-primary/20 bg-primary/10 text-foreground"
                    : "border-transparent text-muted-foreground hover:bg-surface hover:text-foreground",
                )}
              >
                <div className="flex min-w-0 items-center gap-2">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border bg-background">
                    <Users className="h-4 w-4 text-accent" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold">{room.name ?? "Untitled room"}</p>
                    <p className="text-[11px] text-muted-foreground">
                      {members.length} members
                    </p>
                  </div>
                </div>
                <div className="mt-2 flex -space-x-1 overflow-hidden">
                  {members.slice(0, 5).map((member) => (
                    <Avatar key={member.address} className="h-5 w-5 border border-background">
                      <AvatarFallback className={cn("text-[8px]", kindAvatarClass(member.kind))}>
                        {memberDisplayInitials(member.name)}
                      </AvatarFallback>
                    </Avatar>
                  ))}
                </div>
              </motion.button>
            );
          })}
        </div>
      </ScrollArea>
    </div>
  );
}

export function CreateGroupDialog({
  open,
  onOpenChange,
  onCreated,
}: CreateGroupDialogProps) {
  const currentUser = useAppStore((s) => s.currentUser);
  const contacts = useAppStore((s) => s.contacts);
  const [name, setName] = useState("Research room");
  const [selectedMemberIds, setSelectedMemberIds] = useState<Set<string>>(new Set());
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    if (!open) return;
    setSelectedMemberIds(new Set());
    setName("Research room");
  }, [open]);

  const availableContacts = contacts.filter((contact) => contact.kind !== "arbiter");

  const toggleMember = (uid: string) => {
    setSelectedMemberIds((prev) => {
      const next = new Set(prev);
      if (next.has(uid)) next.delete(uid);
      else next.add(uid);
      return next;
    });
  };

  const handleCreate = async () => {
    if (!currentUser || creating || selectedMemberIds.size === 0 || !name.trim()) return;
    setCreating(true);
    try {
      const room = await createGroupSession(
        currentUser.entity_uid,
        name.trim(),
        Array.from(selectedMemberIds),
      );
      onCreated(room);
      onOpenChange(false);
    } finally {
      setCreating(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl rounded-lg">
        <DialogHeader>
          <DialogTitle>Create room</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">Name</label>
            <Input value={name} onChange={(event) => setName(event.target.value)} />
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground">Members</span>
              <Badge variant="outline" className="rounded-md">
                {selectedMemberIds.size} selected
              </Badge>
            </div>
            <ContactPicker
              contacts={availableContacts}
              selectedMemberIds={selectedMemberIds}
              emptyText="No friends available"
              onToggle={toggleMember}
            />
          </div>
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={creating}
          >
            Cancel
          </Button>
          <Button
            onClick={handleCreate}
            disabled={creating || selectedMemberIds.size === 0 || !name.trim()}
          >
            {creating && <Loader2 className="h-4 w-4 animate-spin" />}
            Create
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function AddGroupMembersDialog({
  open,
  room,
  activeMemberIds,
  onOpenChange,
  onUpdated,
}: AddGroupMembersDialogProps) {
  const currentUser = useAppStore((s) => s.currentUser);
  const contacts = useAppStore((s) => s.contacts);
  const [selectedMemberIds, setSelectedMemberIds] = useState<Set<string>>(new Set());
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setSelectedMemberIds(new Set());
  }, [open]);

  const availableContacts = contacts.filter(
    (contact) => contact.kind !== "arbiter" && !activeMemberIds.has(contact.entity_uid),
  );

  const toggleMember = (uid: string) => {
    setSelectedMemberIds((prev) => {
      const next = new Set(prev);
      if (next.has(uid)) next.delete(uid);
      else next.add(uid);
      return next;
    });
  };

  const handleSave = async () => {
    if (!currentUser || saving || selectedMemberIds.size === 0) return;
    setSaving(true);
    try {
      const updated = await addGroupMembers(
        currentUser.entity_uid,
        room.session_id,
        Array.from(selectedMemberIds),
      );
      onUpdated(updated);
      onOpenChange(false);
    } catch (error) {
      alert(`Invite failed: ${errorMessage(error)}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl rounded-lg">
        <DialogHeader>
          <DialogTitle>Invite members</DialogTitle>
        </DialogHeader>

        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-muted-foreground">
              {room.name ?? "Group room"}
            </span>
            <Badge variant="outline" className="rounded-md">
              {selectedMemberIds.size} selected
            </Badge>
          </div>
          <ContactPicker
            contacts={availableContacts}
            selectedMemberIds={selectedMemberIds}
            emptyText="No more friends available"
            onToggle={toggleMember}
          />
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={saving}
          >
            Cancel
          </Button>
          <Button
            onClick={handleSave}
            disabled={saving || selectedMemberIds.size === 0}
          >
            {saving && <Loader2 className="h-4 w-4 animate-spin" />}
            Invite
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function GroupRoom({
  room,
  onBack,
  onRefreshRooms,
  onRoomUpdated,
  onRoomDeleted,
}: GroupRoomProps) {
  const currentUser = useAppStore((s) => s.currentUser);
  const contacts = useAppStore((s) => s.contacts);
  const avatarCache = useAppStore((s) => s.avatarCache);
  const { addListener } = useWsListener();

  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [tokenLimit, setTokenLimit] = useState(8_000);
  const [addMembersOpen, setAddMembersOpen] = useState(false);
  const [deletingRoom, setDeletingRoom] = useState(false);
  const [removingMemberAddress, setRemovingMemberAddress] = useState<string | null>(null);
  const [leftPanelWidth, setLeftPanelWidth] = useState(272);
  const [rightPanelWidth, setRightPanelWidth] = useState(320);
  const [tokenPanelHeight, setTokenPanelHeight] = useState(260);
  const [leftPanelOpen, setLeftPanelOpen] = useState(true);
  const [rightPanelOpen, setRightPanelOpen] = useState(true);
  const scrollAreaRef = useRef<HTMLDivElement>(null);

  const members = useMemo(() => mergeRoomMembers(room), [room]);
  const contactByUid = useMemo(
    () => new Map(contacts.map((contact) => [contact.entity_uid, contact])),
    [contacts],
  );
  const currentMember = currentUser
    ? memberByUid(members, currentUser.entity_uid)
    : undefined;
  const canSend = currentMember?.can_send ?? false;
  const canInvite = currentMember?.can_invite ?? false;
  const canRemove = currentMember?.can_remove ?? false;
  const activeMemberIds = useMemo(
    () => new Set(members.map((member) => member.entity_uid)),
    [members],
  );
  const roomGridStyle = {
    "--room-left-track": leftPanelOpen ? `${leftPanelWidth}px` : "2.75rem",
    "--room-left-resizer-width": leftPanelOpen ? "0.5rem" : "0rem",
    "--room-right-track": rightPanelOpen ? `${rightPanelWidth}px` : "2.75rem",
    "--room-right-resizer-width": rightPanelOpen ? "0.5rem" : "0rem",
    "--token-panel-height": `${tokenPanelHeight}px`,
  } as CSSProperties;

  const loadHistory = useCallback(async () => {
    if (!currentUser) return;
    setLoadingHistory(true);
    try {
      const mailbox = await getMessages(currentUser.entity_uid, 300);
      const roomMessages = mailbox
        .map((entry) => mailboxToGroupMessage(entry, room.session_id))
        .filter((message): message is Message => message !== null);
      setMessages(roomMessages);

      const unreadIds = mailbox
        .filter((entry) => groupIdFromMailbox(entry) === room.session_id)
        .filter((entry) => entry.direction === "inbound" && !entry.is_read)
        .map((entry) => entry.message_id);
      if (unreadIds.length > 0) {
        markMessagesRead(currentUser.entity_uid, unreadIds).catch(() => {});
      }
    } finally {
      setLoadingHistory(false);
    }
  }, [currentUser, room.session_id]);

  useEffect(() => {
    setMessages([]);
    loadHistory();
  }, [loadHistory]);

  useEffect(() => {
    return addListener((event: WsEvent) => {
      if (event.type !== "new_message" || !event.message) return;
      if (!isRoomWsMessage(event.message, room.session_id)) return;
      setMessages((prev) => {
        if (prev.some((message) => message.message_id === event.message?.message_id)) {
          return prev;
        }
        return [...prev, event.message as Message];
      });
    });
  }, [addListener, room.session_id]);

  useEffect(() => {
    const viewport = scrollAreaRef.current?.querySelector<HTMLElement>(
      "[data-slot='scroll-area-viewport']",
    );
    if (!viewport) return;
    viewport.scrollTop = viewport.scrollHeight;
  }, [messages.length]);

  const latestMessage = messages[messages.length - 1];
  const activeSpeakerUid = latestMessage ? extractEntityUid(latestMessage.sender) : "";
  const totalTokens = messages.reduce(
    (sum, message) => sum + estimateTokens(String(message.payload.text ?? "")),
    0,
  );
  const tokenPercent = Math.min(100, Math.round((totalTokens / tokenLimit) * 100));

  const recentByMember = useMemo(() => {
    const map = new Map<string, Message>();
    for (const message of messages.slice(-8)) {
      map.set(extractEntityUid(message.sender), message);
    }
    return map;
  }, [messages]);

  const layout = useMemo(() => {
    const count = Math.max(members.length, 1);
    return members.map((member, index) => {
      const angle = (-90 + (index * 360) / count) * (Math.PI / 180);
      return {
        member,
        left: 50 + Math.cos(angle) * 38,
        top: 50 + Math.sin(angle) * 31,
      };
    });
  }, [members]);

  const handleSend = async () => {
    if (!currentUser || !input.trim() || sending || !canSend) return;
    const text = input.trim();
    setInput("");
    setSending(true);

    const tmpId = `tmp-group-${Date.now()}`;
    const optimistic: Message = {
      message_id: tmpId,
      sender: currentUser.entity_uid,
      recipient: members
        .filter((member) => member.entity_uid !== currentUser.entity_uid)
        .map(memberAddress),
      payload: { text, session_id: room.session_id },
      metadata: { conversation_type: "group", group_id: room.session_id },
      conversation_type: "group",
      group_id: room.session_id,
      timestamp: new Date().toISOString(),
      status: "sent",
      session_id: room.session_id,
    };
    setMessages((prev) => [...prev, optimistic]);

    try {
      const result = await sendGroupMessage(currentUser.entity_uid, room.session_id, text);
      setMessages((prev) =>
        prev.map((message) =>
          message.message_id === tmpId
            ? {
                ...message,
                message_id: result.message_id,
                mail_id: result.mail_id,
                status: "delivering",
              }
            : message,
        ),
      );
      onRefreshRooms?.();
    } catch {
      setMessages((prev) =>
        prev.map((message) =>
          message.message_id === tmpId ? { ...message, status: "failed" } : message,
        ),
      );
    } finally {
      setSending(false);
    }
  };

  const startPanelResize = useCallback(
    (panel: "left" | "right", event: ReactPointerEvent<HTMLButtonElement>) => {
      event.preventDefault();
      const startX = event.clientX;
      const startWidth = panel === "left" ? leftPanelWidth : rightPanelWidth;

      const handlePointerMove = (moveEvent: PointerEvent) => {
        const delta = moveEvent.clientX - startX;
        const nextWidth = panel === "left" ? startWidth + delta : startWidth - delta;
        const clampedWidth = Math.min(460, Math.max(220, nextWidth));
        if (panel === "left") setLeftPanelWidth(clampedWidth);
        else setRightPanelWidth(clampedWidth);
      };

      const handlePointerUp = () => {
        window.removeEventListener("pointermove", handlePointerMove);
      };

      window.addEventListener("pointermove", handlePointerMove);
      window.addEventListener("pointerup", handlePointerUp, { once: true });
    },
    [leftPanelWidth, rightPanelWidth],
  );

  const startTokenPanelResize = useCallback(
    (event: ReactPointerEvent<HTMLButtonElement>) => {
      event.preventDefault();
      const startY = event.clientY;
      const startHeight = tokenPanelHeight;

      const handlePointerMove = (moveEvent: PointerEvent) => {
        const delta = moveEvent.clientY - startY;
        const nextHeight = startHeight - delta;
        setTokenPanelHeight(Math.min(460, Math.max(180, nextHeight)));
      };

      const handlePointerUp = () => {
        window.removeEventListener("pointermove", handlePointerMove);
      };

      window.addEventListener("pointermove", handlePointerMove);
      window.addEventListener("pointerup", handlePointerUp, { once: true });
    },
    [tokenPanelHeight],
  );

  const handleRoomUpdated = (updatedRoom: SessionInfo) => {
    onRoomUpdated?.(updatedRoom);
    onRefreshRooms?.();
  };

  const handleRemoveMember = async (member: GroupMemberInfo) => {
    if (!currentUser || removingMemberAddress) return;
    if (!confirm(`Remove "${member.name}" from this room?`)) return;
    setRemovingMemberAddress(member.address);
    try {
      const updatedRoom = await removeGroupMember(
        currentUser.entity_uid,
        room.session_id,
        member.address,
      );
      handleRoomUpdated(updatedRoom);
    } catch (error) {
      alert(`Remove failed: ${errorMessage(error)}`);
    } finally {
      setRemovingMemberAddress(null);
    }
  };

  const handleDeleteRoom = async () => {
    if (!currentUser || deletingRoom) return;
    if (!confirm(`Delete "${room.name ?? "this room"}"?`)) return;
    setDeletingRoom(true);
    try {
      await deleteGroupSession(currentUser.entity_uid, room.session_id);
      onRoomDeleted?.(room.session_id);
      onRefreshRooms?.();
    } catch (error) {
      alert(`Delete failed: ${errorMessage(error)}`);
    } finally {
      setDeletingRoom(false);
    }
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.nativeEvent.isComposing || event.keyCode === 229) return;
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex h-full min-h-0 w-full flex-col overflow-hidden">
      <header className="flex h-14 shrink-0 items-center gap-3 border-b border-border px-4">
        {onBack && (
          <Button
            size="icon-sm"
            variant="ghost"
            className="md:hidden"
            onClick={onBack}
          >
            <ArrowLeft className="h-4 w-4" />
          </Button>
        )}
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border bg-surface">
          <Users className="h-4 w-4 text-accent" />
        </div>
        <div className="min-w-0 flex-1">
          <h2 className="truncate text-sm font-semibold">{room.name ?? "Group room"}</h2>
          <p className="text-[11px] text-muted-foreground">
            {members.length} members · shared context
          </p>
        </div>
        <Button
          size="icon-sm"
          variant="ghost"
          onClick={handleDeleteRoom}
          disabled={!canRemove || deletingRoom}
          title={canRemove ? "Delete room" : "Only owners and admins can delete"}
        >
          {deletingRoom ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
        </Button>
        <Button size="icon-sm" variant="ghost" onClick={loadHistory} title="Reload history">
          <RefreshCw className={cn("h-4 w-4", loadingHistory && "animate-spin")} />
        </Button>
      </header>

      <div
        className="grid min-h-0 flex-1 grid-cols-1 overflow-hidden lg:grid-cols-[var(--room-left-track)_var(--room-left-resizer-width)_minmax(0,1fr)] xl:grid-cols-[var(--room-left-track)_var(--room-left-resizer-width)_minmax(0,1fr)_var(--room-right-resizer-width)_var(--room-right-track)]"
        style={roomGridStyle}
      >
        <aside className="hidden min-h-0 border-r border-border bg-sidebar/70 lg:col-start-1 lg:flex lg:flex-col">
          {leftPanelOpen ? (
            <>
              <div className="flex h-11 shrink-0 items-center gap-2 border-b border-sidebar-border px-3">
                <Users className="h-4 w-4 text-muted-foreground" />
                <span className="min-w-0 flex-1 truncate text-xs font-semibold">Entities</span>
                <Button
                  size="icon-xs"
                  variant="ghost"
                  onClick={() => setLeftPanelOpen(false)}
                  title="Hide entities panel"
                >
                  <ChevronLeft className="h-3.5 w-3.5" />
                </Button>
              </div>
              <ScrollArea className="min-h-0 flex-1">
                <div className="space-y-1 p-2">
                  {members.map((member) => {
                    const contact = contactByUid.get(member.entity_uid);
                    const Icon = memberIcon(member.kind);
                    const active = member.entity_uid === activeSpeakerUid;
                    const removable = canRemoveMember(currentMember, member);
                    return (
                      <div
                        key={member.address}
                        className={cn(
                          "group flex items-center gap-3 rounded-lg border px-3 py-2 transition-colors",
                          active ? "border-accent/30 bg-accent/10" : "border-transparent bg-transparent",
                        )}
                      >
                        <Avatar className="h-8 w-8 border border-border">
                          {contact?.has_avatar && avatarCache[member.entity_uid] && (
                            <AvatarImage src={avatarCache[member.entity_uid]} />
                          )}
                          <AvatarFallback className={cn("text-xs", kindAvatarClass(member.kind))}>
                            {memberDisplayInitials(member.name)}
                          </AvatarFallback>
                        </Avatar>
                        <div className="min-w-0 flex-1">
                          <div className="flex min-w-0 items-center gap-1.5">
                            <span className="truncate text-sm font-medium">{member.name}</span>
                            <Icon className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                          </div>
                          <Badge
                            variant="outline"
                            className={cn("mt-1 rounded-md px-1.5 py-0 text-[10px]", ROLE_STYLES[member.role])}
                          >
                            {member.role}
                          </Badge>
                        </div>
                        {removable && (
                          <Button
                            size="icon-sm"
                            variant="ghost"
                            onClick={() => handleRemoveMember(member)}
                            disabled={removingMemberAddress === member.address}
                            title={`Remove ${member.name}`}
                            className="shrink-0 opacity-0 transition-opacity group-hover:opacity-100"
                          >
                            {removingMemberAddress === member.address ? (
                              <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            ) : (
                              <UserMinus className="h-3.5 w-3.5" />
                            )}
                          </Button>
                        )}
                      </div>
                    );
                  })}
                  <Button
                    size="sm"
                    onClick={() => setAddMembersOpen(true)}
                    disabled={!canInvite}
                    title={canInvite ? "Invite members" : "Only owners and admins can invite"}
                    className="mt-3 h-10 w-full justify-center rounded-lg bg-neutral-950 px-4 text-sm font-semibold text-white shadow-sm hover:bg-neutral-900 hover:text-white disabled:bg-muted disabled:text-muted-foreground"
                  >
                    <UserPlus className="h-4 w-4" />
                    Invite member
                  </Button>
                </div>
              </ScrollArea>
            </>
          ) : (
            <div className="flex h-full flex-col items-center gap-3 py-3">
              <Button
                size="icon-sm"
                variant="ghost"
                onClick={() => setLeftPanelOpen(true)}
                title="Show entities panel"
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
              <Users className="h-4 w-4 text-muted-foreground" />
            </div>
          )}
        </aside>

        <button
          type="button"
          className={cn(
            "hidden cursor-col-resize items-center justify-center border-r border-border bg-sidebar/50 text-muted-foreground hover:bg-surface hover:text-foreground",
            leftPanelOpen && "lg:col-start-2 lg:flex",
          )}
          onPointerDown={(event) => startPanelResize("left", event)}
          title="Resize entities panel"
        >
          <GripVertical className="h-4 w-4" />
        </button>

        <main className="flex min-h-0 flex-col overflow-hidden bg-background lg:col-start-3">
          <div className="relative min-h-[28rem] flex-1 overflow-hidden border-b border-border bg-[radial-gradient(circle_at_center,color-mix(in_srgb,var(--t-accent)_8%,transparent),transparent_58%)]">
            <div className="absolute inset-0 bg-[linear-gradient(to_right,color-mix(in_srgb,var(--t-border)_45%,transparent)_1px,transparent_1px),linear-gradient(to_bottom,color-mix(in_srgb,var(--t-border)_45%,transparent)_1px,transparent_1px)] bg-[size:44px_44px] opacity-40" />
            <div className="absolute left-1/2 top-1/2 h-[48%] w-[58%] -translate-x-1/2 -translate-y-1/2 rounded-[50%] border border-border bg-surface shadow-inner" />
            <div className="absolute left-1/2 top-1/2 flex h-24 w-44 -translate-x-1/2 -translate-y-1/2 flex-col items-center justify-center rounded-lg border border-border bg-background/80 px-4 text-center shadow-sm glass">
              <Activity className="mb-2 h-5 w-5 text-accent" />
              <p className="text-xs font-semibold">Shared Context</p>
              <p className="mt-1 text-[10px] text-muted-foreground">
                {messages.length} turns · {totalTokens} est. tokens
              </p>
            </div>

            {latestMessage && (
              <div className="absolute left-4 right-4 top-5 z-10 rounded-lg border border-border bg-background/95 px-3 py-2 text-sm shadow-sm sm:hidden">
                <p className="line-clamp-2 text-foreground/80">
                  {String(latestMessage.payload.text ?? "")}
                </p>
              </div>
            )}

            {layout.map(({ member, left, top }) => {
              const active = member.entity_uid === activeSpeakerUid;
              const recent = recentByMember.get(member.entity_uid);
              const contact = contactByUid.get(member.entity_uid);
              const Icon = memberIcon(member.kind);
              return (
                <motion.div
                  key={member.address}
                  className="absolute flex -translate-x-1/2 -translate-y-1/2 flex-col items-center"
                  style={{ left: `${left}%`, top: `${top}%` }}
                  animate={{ y: active ? [0, -5, 0] : 0 }}
                  transition={{ duration: 1.4, repeat: active ? Infinity : 0 }}
                >
                  {recent && (
                    <motion.div
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      className={cn(
                        "mb-2 hidden max-w-48 rounded-lg border px-3 py-2 text-xs shadow-sm sm:block",
                        active ? "border-accent/30 bg-background" : "border-border bg-background/90",
                      )}
                    >
                      <p className="line-clamp-2 text-foreground/80">
                        {String(recent.payload.text ?? "")}
                      </p>
                    </motion.div>
                  )}
                  <div
                    className={cn(
                      "relative flex h-16 w-16 items-center justify-center rounded-full border-2 bg-background shadow-sm transition-colors",
                      active ? "border-accent" : "border-border",
                    )}
                  >
                    <Avatar className="h-12 w-12">
                      {contact?.has_avatar && avatarCache[member.entity_uid] && (
                        <AvatarImage src={avatarCache[member.entity_uid]} />
                      )}
                      <AvatarFallback className={cn("text-sm font-semibold", kindAvatarClass(member.kind))}>
                        {memberDisplayInitials(member.name)}
                      </AvatarFallback>
                    </Avatar>
                    <span className="absolute -right-1 -top-1 flex h-6 w-6 items-center justify-center rounded-full border border-border bg-background">
                      <Icon className="h-3.5 w-3.5 text-muted-foreground" />
                    </span>
                  </div>
                  <div className="mt-2 max-w-20 text-center sm:max-w-28">
                    <p className="truncate text-[11px] font-semibold sm:text-xs">{member.name}</p>
                    <p className="text-[10px] text-muted-foreground">{member.role}</p>
                  </div>
                </motion.div>
              );
            })}
          </div>

          <div className="shrink-0 border-t border-border bg-background p-3">
            <div className="flex items-end gap-2 rounded-lg border border-input bg-surface px-3 py-2 focus-within:border-primary/25">
              <textarea
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={canSend ? "Message the room..." : "Observer role cannot send"}
                disabled={!canSend}
                rows={1}
                className="max-h-28 min-h-8 flex-1 resize-none bg-transparent text-sm outline-none placeholder:text-muted-foreground/50 disabled:cursor-not-allowed"
              />
              <Button
                size="icon-sm"
                disabled={!input.trim() || sending || !canSend}
                onClick={handleSend}
              >
                {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              </Button>
            </div>
          </div>
        </main>

        <button
          type="button"
          className={cn(
            "hidden cursor-col-resize items-center justify-center border-l border-border bg-sidebar/50 text-muted-foreground hover:bg-surface hover:text-foreground",
            rightPanelOpen && "xl:col-start-4 xl:flex",
          )}
          onPointerDown={(event) => startPanelResize("right", event)}
          title="Resize history panel"
        >
          <GripVertical className="h-4 w-4" />
        </button>

        <aside className="hidden min-h-0 border-l border-border bg-sidebar/70 xl:col-start-5 xl:flex xl:flex-col">
          {rightPanelOpen ? (
            <>
              <div className="flex h-11 shrink-0 items-center gap-2 border-b border-sidebar-border px-3">
                <History className="h-4 w-4 text-muted-foreground" />
                <span className="min-w-0 flex-1 truncate text-xs font-semibold">Chat History</span>
                <Button
                  size="icon-xs"
                  variant="ghost"
                  onClick={() => setRightPanelOpen(false)}
                  title="Hide chat history panel"
                >
                  <ChevronRight className="h-3.5 w-3.5" />
                </Button>
              </div>
              <ScrollArea ref={scrollAreaRef} className="min-h-0 flex-1">
                <div className="space-y-2 p-3">
                  {loadingHistory && (
                    <div className="flex justify-center py-8">
                      <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                    </div>
                  )}
                  {!loadingHistory && messages.length === 0 && (
                    <p className="py-8 text-center text-xs text-muted-foreground">No messages yet</p>
                  )}
                  {messages.map((message) => {
                    const sender = memberByUid(members, message.sender);
                    const isSelf = currentUser?.entity_uid === extractEntityUid(message.sender);
                    return (
                      <div
                        key={message.message_id}
                        className={cn(
                          "rounded-lg border px-3 py-2",
                          isSelf ? "border-primary/15 bg-primary/5" : "border-border bg-background",
                        )}
                      >
                        <div className="mb-1 flex items-center justify-between gap-2">
                          <span className="truncate text-xs font-semibold">
                            {sender?.name ?? extractEntityUid(message.sender)}
                          </span>
                          <span className="shrink-0 text-[10px] text-muted-foreground">
                            {roomTimeLabel(message.timestamp)}
                          </span>
                        </div>
                        <p className="text-xs leading-relaxed text-foreground/80">
                          {String(message.payload.text ?? "")}
                        </p>
                      </div>
                    );
                  })}
                </div>
              </ScrollArea>
              <button
                type="button"
                className="flex h-2 shrink-0 cursor-row-resize items-center justify-center border-y border-sidebar-border bg-sidebar/50 text-muted-foreground hover:bg-surface hover:text-foreground"
                onPointerDown={startTokenPanelResize}
                title="Resize token limits panel"
              >
                <GripHorizontal className="h-3.5 w-3.5" />
              </button>
              <div
                className="shrink-0 overflow-y-auto border-t border-sidebar-border p-4"
                style={{ height: "var(--token-panel-height)" }}
              >
                <div className="mb-3 flex items-center gap-2">
                  <Gauge className="h-4 w-4 text-muted-foreground" />
                  <span className="text-xs font-semibold">Token Limits</span>
                </div>
                <div className="space-y-3">
                  <div>
                    <div className="mb-1 flex justify-between text-[11px] text-muted-foreground">
                      <span>Estimated usage</span>
                      <span>{totalTokens} / {tokenLimit}</span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-surface">
                      <div
                        className={cn(
                          "h-full rounded-full transition-all",
                          tokenPercent > 85 ? "bg-destructive" : tokenPercent > 65 ? "bg-warning" : "bg-success",
                        )}
                        style={{ width: `${tokenPercent}%` }}
                      />
                    </div>
                  </div>
                  <input
                    type="range"
                    min={2000}
                    max={32000}
                    step={1000}
                    value={tokenLimit}
                    onChange={(event) => setTokenLimit(Number(event.target.value))}
                    className="w-full accent-current"
                  />
                  <div className="grid grid-cols-3 gap-2 text-center">
                    <div className="rounded-md border border-border bg-background px-2 py-2">
                      <p className="text-sm font-semibold">{messages.length}</p>
                      <p className="text-[10px] text-muted-foreground">turns</p>
                    </div>
                    <div className="rounded-md border border-border bg-background px-2 py-2">
                      <p className="text-sm font-semibold">{members.length}</p>
                      <p className="text-[10px] text-muted-foreground">entities</p>
                    </div>
                    <div className="rounded-md border border-border bg-background px-2 py-2">
                      <p className="text-sm font-semibold">{tokenPercent}%</p>
                      <p className="text-[10px] text-muted-foreground">budget</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-2 rounded-md border border-border bg-background p-2">
                    <Clock3 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                    <p className="text-[11px] leading-relaxed text-muted-foreground">
                      Limit is local for this demo panel.
                    </p>
                  </div>
                </div>
              </div>
            </>
          ) : (
            <div className="flex h-full flex-col items-center gap-3 py-3">
              <Button
                size="icon-sm"
                variant="ghost"
                onClick={() => setRightPanelOpen(true)}
                title="Show chat history panel"
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <History className="h-4 w-4 text-muted-foreground" />
            </div>
          )}
        </aside>
      </div>
      <AddGroupMembersDialog
        open={addMembersOpen}
        room={room}
        activeMemberIds={activeMemberIds}
        onOpenChange={setAddMembersOpen}
        onUpdated={handleRoomUpdated}
      />
    </div>
  );
}

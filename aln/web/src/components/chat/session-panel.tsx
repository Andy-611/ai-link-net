/* Session history dialog — list, create, rename, delete sessions.
   Triggered from the chat header, consistent with shadcn/ui Dialog patterns. */

import { useCallback, useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Plus,
  Trash2,
  Pencil,
  Check,
  X,
  MessageSquare,
  Loader2,
} from "lucide-react";

import { cn } from "@/lib/utils";
import {
  listSessions,
  createSession,
  renameSession,
  deleteSession,
} from "@/api";
import type { SessionInfo } from "@/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface SessionDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  entityUid: string;
  contactUid: string;
  activeSessionId: string | null;
  onSelectSession: (sessionId: string | null) => void;
}

function formatDate(ts: number): string {
  const d = new Date(ts * 1000);
  const now = new Date();
  if (d.toDateString() === now.toDateString()) {
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }
  return d.toLocaleDateString([], { month: "short", day: "numeric" });
}

export function SessionDialog({
  open,
  onOpenChange,
  entityUid,
  contactUid,
  activeSessionId,
  onSelectSession,
}: SessionDialogProps) {
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");

  const fetchSessions = useCallback(async () => {
    try {
      const list = await listSessions(entityUid, contactUid);
      setSessions(list);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, [entityUid, contactUid]);

  useEffect(() => {
    if (open) {
      setLoading(true);
      setEditingId(null);
      fetchSessions();
    }
  }, [open, fetchSessions]);

  async function handleCreate() {
    setCreating(true);
    try {
      const session = await createSession(entityUid, contactUid);
      setSessions((prev) => [session, ...prev]);
      onSelectSession(session.session_id);
      onOpenChange(false);
    } catch {
      /* ignore */
    } finally {
      setCreating(false);
    }
  }

  async function handleDelete(sessionId: string) {
    try {
      await deleteSession(entityUid, sessionId);
      setSessions((prev) => prev.filter((s) => s.session_id !== sessionId));
      if (activeSessionId === sessionId) onSelectSession(null);
    } catch {
      /* ignore */
    }
  }

  async function handleRename(sessionId: string) {
    if (!editName.trim()) {
      setEditingId(null);
      return;
    }
    try {
      const updated = await renameSession(entityUid, sessionId, editName.trim());
      setSessions((prev) =>
        prev.map((s) => (s.session_id === sessionId ? updated : s)),
      );
    } catch {
      /* ignore */
    } finally {
      setEditingId(null);
    }
  }

  function handleSelect(sessionId: string | null) {
    onSelectSession(sessionId);
    onOpenChange(false);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        showCloseButton={false}
        className="sm:max-w-sm bg-card border-border p-0 gap-0 overflow-hidden"
      >
        {/* Header */}
        <DialogHeader className="px-5 pt-5 pb-4">
          <div className="flex items-center justify-between">
            <div>
              <DialogTitle className="font-heading text-base">
                Sessions
              </DialogTitle>
              <DialogDescription className="text-xs mt-1">
                Switch between conversation sessions
              </DialogDescription>
            </div>
            <Button
              size="sm"
              className="h-8 gap-1.5 text-xs bg-primary text-primary-foreground hover:bg-primary/90"
              onClick={handleCreate}
              disabled={creating}
            >
              {creating ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Plus className="h-3.5 w-3.5" />
              )}
              New
            </Button>
          </div>
        </DialogHeader>

        {/* Divider */}
        <div className="border-t border-border" />

        {/* Session list */}
        <ScrollArea className="max-h-80">
          <div className="p-2 space-y-0.5">
            {/* "All messages" option */}
            <button
              onClick={() => handleSelect(null)}
              className={cn(
                "w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm transition-colors",
                activeSessionId === null
                  ? "bg-primary/10 text-foreground border border-primary/15"
                  : "text-muted-foreground hover:text-foreground hover:bg-surface border border-transparent",
              )}
            >
              <MessageSquare className="h-4 w-4 shrink-0" />
              <span className="font-medium">All messages</span>
            </button>

            {/* Loading */}
            {loading && sessions.length === 0 && (
              <div className="flex justify-center py-8">
                <Loader2 className="h-4 w-4 animate-spin text-muted-foreground/40" />
              </div>
            )}

            {/* Sessions */}
            <AnimatePresence>
              {sessions.map((session) => {
                const isActive = session.session_id === activeSessionId;
                const isEditing = session.session_id === editingId;

                return (
                  <motion.div
                    key={session.session_id}
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                  >
                    <div
                      className={cn(
                        "group flex items-center gap-2 px-3 py-2.5 rounded-lg text-sm transition-colors",
                        isActive
                          ? "bg-primary/10 text-foreground border border-primary/15"
                          : "text-muted-foreground hover:text-foreground hover:bg-surface border border-transparent",
                      )}
                    >
                      {isEditing ? (
                        <div className="flex items-center gap-1.5 flex-1 min-w-0">
                          <Input
                            value={editName}
                            onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                              setEditName(e.target.value)
                            }
                            onKeyDown={(e: React.KeyboardEvent) => {
                              if (e.nativeEvent.isComposing || e.keyCode === 229) return;
                              if (e.key === "Enter")
                                handleRename(session.session_id);
                              if (e.key === "Escape") setEditingId(null);
                            }}
                            className="h-7 text-xs px-2 bg-surface border-border"
                            autoFocus
                          />
                          <button
                            onClick={() => handleRename(session.session_id)}
                            className="text-success hover:text-success/80 shrink-0 p-1 rounded-md hover:bg-surface"
                          >
                            <Check className="h-3.5 w-3.5" />
                          </button>
                          <button
                            onClick={() => setEditingId(null)}
                            className="text-muted-foreground hover:text-foreground shrink-0 p-1 rounded-md hover:bg-surface"
                          >
                            <X className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      ) : (
                        <>
                          <button
                            onClick={() => handleSelect(session.session_id)}
                            className="flex-1 min-w-0 text-left"
                          >
                            <p className="truncate font-medium">
                              {session.name ?? session.session_id}
                            </p>
                            <p className="text-[11px] text-muted-foreground/50 mt-0.5">
                              {formatDate(session.updated_at)}
                            </p>
                          </button>
                          <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                            <button
                              onClick={() => {
                                setEditingId(session.session_id);
                                setEditName(session.name ?? "");
                              }}
                              className="p-1 rounded-md text-muted-foreground/60 hover:text-foreground hover:bg-surface"
                            >
                              <Pencil className="h-3 w-3" />
                            </button>
                            <button
                              onClick={() => handleDelete(session.session_id)}
                              className="p-1 rounded-md text-muted-foreground/60 hover:text-destructive hover:bg-destructive/10"
                            >
                              <Trash2 className="h-3 w-3" />
                            </button>
                          </div>
                        </>
                      )}
                    </div>
                  </motion.div>
                );
              })}
            </AnimatePresence>

            {!loading && sessions.length === 0 && (
              <p className="text-center text-xs text-muted-foreground/40 py-8">
                No sessions yet
              </p>
            )}
          </div>
        </ScrollArea>
      </DialogContent>
    </Dialog>
  );
}

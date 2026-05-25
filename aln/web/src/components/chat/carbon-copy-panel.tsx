/* CarbonCopy sidebar panel — displays CC messages from Zustand store (fed by WebSocket). */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowLeft, Inbox, X } from "lucide-react";

import { cn, extractEntityUid } from "@/lib/utils";
import { useAppStore } from "@/stores/app";
import type { CarbonCopyMessage } from "@/types";
import { ScrollArea } from "@/components/ui/scroll-area";
import { CarbonCopyItem } from "./message-item";

const MIN_WIDTH = 260;
const MAX_WIDTH = 600;
const DEFAULT_WIDTH = 320;
const WIDTH_STORAGE_KEY = "fp_cc_panel_width";
const ALL_TAB_ID = "__all__";

interface CarbonCopyPanelProps {
  contactUid: string;
  onClose: () => void;
}

interface CarbonCopyTab {
  id: string;
  label: string;
  count: number;
  lastTimestamp: number;
}

function loadSavedWidth(): number {
  try {
    const v = Number(localStorage.getItem(WIDTH_STORAGE_KEY));
    return v >= MIN_WIDTH && v <= MAX_WIDTH ? v : DEFAULT_WIDTH;
  } catch {
    return DEFAULT_WIDTH;
  }
}

function resolveOtherParticipant(
  cc: CarbonCopyMessage,
  contactUid: string,
): { uid: string; label: string } {
  const senderUid = extractEntityUid(cc.originalSender);
  const recipientUid = extractEntityUid(cc.originalRecipient);

  if (senderUid === contactUid) {
    return {
      uid: recipientUid,
      label: cc.originalRecipientName?.trim() || recipientUid,
    };
  }

  return {
    uid: senderUid,
    label: cc.originalSenderName?.trim() || senderUid,
  };
}

export function CarbonCopyPanel({ contactUid, onClose }: CarbonCopyPanelProps) {
  const carbonCopyMessages = useAppStore((s) => s.carbonCopyMessages);
  const clearCarbonCopies = useAppStore((s) => s.clearCarbonCopies);
  const [width, setWidth] = useState(loadSavedWidth);
  const [activeTab, setActiveTab] = useState(ALL_TAB_ID);
  const dragging = useRef(false);
  const startX = useRef(0);
  const startWidth = useRef(width);
  const bottomRef = useRef<HTMLDivElement>(null);

  const filtered = useMemo(() => {
    const byContact = carbonCopyMessages.filter((cc) => {
      const senderUid = extractEntityUid(cc.originalSender);
      const recipientUid = extractEntityUid(cc.originalRecipient);
      return senderUid === contactUid || recipientUid === contactUid;
    });
    const groups = new Map<string, CarbonCopyMessage>();
    for (const cc of byContact) {
      const key = cc.originalMessageId ?? cc.id;
      const existing = groups.get(key);
      if (!existing) { groups.set(key, cc); continue; }
      const isContactSender = extractEntityUid(cc.originalSender) === contactUid;
      const preferred = isContactSender ? "outbound" : "inbound";
      if (cc.direction === preferred) groups.set(key, cc);
    }
    return Array.from(groups.values()).sort(
      (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime(),
    );
  }, [carbonCopyMessages, contactUid]);

  const tabs = useMemo(() => {
    const groupMap = new Map<string, CarbonCopyTab>();

    for (const cc of filtered) {
      const participant = resolveOtherParticipant(cc, contactUid);
      const timestamp = new Date(cc.timestamp).getTime();
      const existing = groupMap.get(participant.uid);
      if (!existing) {
        groupMap.set(participant.uid, {
          id: participant.uid,
          label: participant.label,
          count: 1,
          lastTimestamp: timestamp,
        });
        continue;
      }
      existing.count += 1;
      existing.lastTimestamp = Math.max(existing.lastTimestamp, timestamp);
      if (existing.label === existing.id && participant.label !== participant.uid) {
        existing.label = participant.label;
      }
    }

    return [
      {
        id: ALL_TAB_ID,
        label: "All",
        count: filtered.length,
        lastTimestamp: filtered.length > 0
          ? new Date(filtered[filtered.length - 1].timestamp).getTime()
          : 0,
      },
      ...Array.from(groupMap.values()).sort((a, b) => b.lastTimestamp - a.lastTimestamp),
    ];
  }, [filtered, contactUid]);

  const visibleMessages = useMemo(() => {
    if (activeTab === ALL_TAB_ID) {
      return filtered;
    }
    return filtered.filter((cc) => resolveOtherParticipant(cc, contactUid).uid === activeTab);
  }, [activeTab, contactUid, filtered]);

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    dragging.current = true;
    startX.current = e.clientX;
    startWidth.current = width;
  }, [width]);

  useEffect(() => {
    const onMouseMove = (e: MouseEvent) => {
      if (!dragging.current) return;
      const delta = startX.current - e.clientX;
      const next = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, startWidth.current + delta));
      setWidth(next);
    };
    const onMouseUp = () => {
      if (!dragging.current) return;
      dragging.current = false;
      localStorage.setItem(WIDTH_STORAGE_KEY, String(document.querySelector<HTMLElement>("[data-cc-panel]")?.offsetWidth ?? DEFAULT_WIDTH));
    };
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
    return () => {
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
    };
  }, []);

  useEffect(() => {
    return () => { localStorage.setItem(WIDTH_STORAGE_KEY, String(width)); };
  }, [width]);

  useEffect(() => {
    setActiveTab(ALL_TAB_ID);
  }, [contactUid]);

  useEffect(() => {
    if (tabs.some((tab) => tab.id === activeTab)) return;
    setActiveTab(ALL_TAB_ID);
  }, [activeTab, tabs]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [visibleMessages]);

  return (
    <div
      data-cc-panel
      className={cn(
        "relative flex h-full shrink-0 flex-col border-l border-border bg-background overflow-hidden",
        "max-md:w-full max-md:border-l-0",
      )}
      style={{ width: undefined }}
    >
      <style>{`@media (min-width:768px){[data-cc-panel]{width:${width}px}}`}</style>
      {/* Resize handle (desktop only) */}
      <div
        onMouseDown={onMouseDown}
        className="absolute left-0 top-0 bottom-0 w-1 cursor-col-resize hover:bg-primary/20 active:bg-primary/30 z-10 max-md:hidden"
      />

      {/* Header */}
      <header className="flex items-center gap-2 px-4 h-14 border-b border-border shrink-0">
        <button
          onClick={onClose}
          className="md:hidden flex items-center justify-center h-8 w-8 -ml-1 rounded-lg text-muted-foreground hover:text-foreground hover:bg-surface-hover transition-colors"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <Inbox className="h-4 w-4 text-muted-foreground shrink-0" />
        <h3 className="text-sm font-semibold flex-1 min-w-0 truncate">
          CarbonCopy
          {filtered.length > 0 && (
            <span className="ml-1.5 text-xs font-normal text-muted-foreground">
              ({filtered.length})
            </span>
          )}
        </h3>
        <button
          onClick={onClose}
          className={cn(
            "h-7 w-7 flex items-center justify-center rounded-lg shrink-0 max-md:hidden",
            "text-muted-foreground hover:text-foreground hover:bg-surface-hover transition-colors",
          )}
        >
          <X className="h-4 w-4" />
        </button>
      </header>

      {tabs.length > 1 && (
        <div className="border-b border-border px-3 pt-2 shrink-0">
          <div className="flex gap-1 overflow-x-auto pb-2">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  "shrink-0 rounded-full px-3 py-1.5 text-xs font-medium transition-colors",
                  activeTab === tab.id
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground hover:text-foreground",
                )}
              >
                {tab.label}
                <span className="ml-1 opacity-70">({tab.count})</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Message list */}
      <ScrollArea className="flex-1 min-h-0">
        <div className="p-3 space-y-2 min-w-0">
          {visibleMessages.length === 0 ? (
            <p className="text-center text-xs text-muted-foreground py-12">
              No carbon copies yet
            </p>
          ) : (
            visibleMessages.map((cc) => (
              <CarbonCopyItem key={cc.id} cc={cc} contactUid={contactUid} />
            ))
          )}
          <div ref={bottomRef} />
        </div>
      </ScrollArea>

      {/* Footer — clear button */}
      {filtered.length > 0 && (
        <div className="px-3 py-2 border-t border-border shrink-0">
          <button
            onClick={clearCarbonCopies}
            className="w-full text-xs text-muted-foreground hover:text-foreground py-1.5 rounded-lg hover:bg-surface-hover transition-colors"
          >
            Clear all
          </button>
        </div>
      )}
    </div>
  );
}

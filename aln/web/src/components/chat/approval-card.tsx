import { useRef, useState } from "react";
import { FileText, ImagePlus, Pencil, ShieldCheck, ShieldX, UserPlus, Coins, X } from "lucide-react";

import { cn } from "@/lib/utils";
import { tradeSend } from "@/api/trade";
import type { Message } from "@/types";

const ACTION_LABELS: Record<string, string> = {
  accept: "验收通过",
  approve: "同意",
  reject: "拒绝",
  rework: "要求返工",
};

const POSITIVE_ACTIONS = new Set(["approve", "accept"]);

const KIND_ICONS: Record<string, typeof UserPlus> = {
  contract_create: FileText,
  contract_status: FileText,
  friend_request: UserPlus,
  pay_collect: Coins,
};

interface SenderCardInfo {
  name: string;
  entity_uid: string;
  kind: string;
  description?: string;
}

function extractSenderCard(payload: Record<string, unknown>): SenderCardInfo | null {
  const op = payload.original_payload as Record<string, unknown> | undefined;
  if (!op) return null;
  const sc = op.sender_card as Record<string, unknown> | undefined;
  if (!sc || typeof sc.name !== "string") return null;
  return {
    name: sc.name as string,
    entity_uid: (sc.entity_uid as string) ?? "",
    kind: (sc.kind as string) ?? "unknown",
    description: (sc.description as string) ?? "",
  };
}

function extractReceiptInfo(payload: Record<string, unknown>): string | null {
  const op = payload.original_payload as Record<string, unknown> | undefined;
  if (!op) return null;
  const receipt = op.receipt_info;
  return typeof receipt === "string" && receipt ? receipt : null;
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function isBase64Image(value: string): boolean {
  return value.startsWith("data:image/");
}

const RECEIPT_STORAGE_KEY = "fp_receipt_info_";

function loadSavedReceipt(entityUid: string): string {
  try {
    return localStorage.getItem(RECEIPT_STORAGE_KEY + entityUid) ?? "";
  } catch {
    return "";
  }
}

function saveReceipt(entityUid: string, value: string): void {
  try {
    localStorage.setItem(RECEIPT_STORAGE_KEY + entityUid, value);
  } catch { /* ignore */ }
}

interface ApprovalCardProps {
  message: Message;
  selfEntityUid: string;
  alreadyRespondedAction?: string;
  alreadyRespondedInputData?: string;
}

export function ApprovalCard({ message, selfEntityUid, alreadyRespondedAction, alreadyRespondedInputData }: ApprovalCardProps) {
  const payload = message.payload as Record<string, unknown>;
  const requestId = String(payload.request_id ?? "");
  const description = String(payload.description ?? "");
  const availableActions = (payload.available_actions as string[]) ?? ["approve", "reject"];
  const originalKind = String(payload.original_kind ?? "");
  const actionType = String(payload.action_type ?? "require_approval");
  const sourceEntityUid = String(payload.source_entity_uid ?? "");
  const senderCard = extractSenderCard(payload);
  const requiresInput = actionType === "require_input";
  const receiptInfo = !requiresInput ? extractReceiptInfo(payload) : null;

  const [busy, setBusy] = useState(false);
  const [responded, setResponded] = useState<string | null>(alreadyRespondedAction ?? null);
  const [error, setError] = useState<string | null>(null);
  const savedReceipt = requiresInput ? loadSavedReceipt(selfEntityUid) : "";
  const initialValue = alreadyRespondedInputData ?? savedReceipt;
  const [inputValue, setInputValue] = useState(initialValue);
  const [imagePreview, setImagePreview] = useState<string | null>(
    initialValue && isBase64Image(initialValue) ? initialValue : null,
  );
  const [editing, setEditing] = useState(!initialValue);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function handleImageUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      setError("请选择图片文件");
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setError("图片不能超过 5MB");
      return;
    }
    setError(null);
    const base64 = await fileToBase64(file);
    setImagePreview(base64);
    setInputValue(base64);
  }

  function clearImage() {
    setImagePreview(null);
    setInputValue("");
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  async function respond(action: string) {
    if (busy || responded) return;
    if (requiresInput && !inputValue.trim()) {
      setError(POSITIVE_ACTIONS.has(action) ? "请输入收款链接或上传收款码" : "请输入拒绝理由");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await tradeSend(
        selfEntityUid,
        "approval_response",
        {
          request_id: requestId,
          action,
          input_data: requiresInput ? inputValue.trim() : undefined,
          original_kind: originalKind || undefined,
          original_payload: (payload.original_payload as Record<string, unknown>) || undefined,
        },
        sourceEntityUid,
      );
      setResponded(action);
      if (requiresInput && POSITIVE_ACTIONS.has(action) && inputValue.trim()) {
        saveReceipt(selfEntityUid, inputValue.trim());
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setBusy(false);
    }
  }

  const Icon = KIND_ICONS[originalKind] ?? ShieldCheck;

  if (responded) {
    const isPositive = POSITIVE_ACTIONS.has(responded);
    return (
      <div className={cn(
        "rounded-2xl border px-4 py-3 shadow-sm max-w-[360px]",
        isPositive
          ? "border-success/30 bg-success/5"
          : "border-destructive/30 bg-destructive/5",
      )}>
        <div className={cn(
          "flex items-center gap-2 text-sm font-medium",
          isPositive ? "text-success" : "text-destructive",
        )}>
          {isPositive ? <ShieldCheck className="h-4 w-4" /> : <ShieldX className="h-4 w-4" />}
          <span>{ACTION_LABELS[responded] ?? responded}</span>
        </div>
        <p className="text-xs text-muted-foreground mt-1">{description}</p>
        {requiresInput && inputValue && !isBase64Image(inputValue) && (
          <p className="text-xs text-muted-foreground/70 mt-1 italic">{inputValue}</p>
        )}
        {requiresInput && inputValue && isBase64Image(inputValue) && (
          <img src={inputValue} alt="收款码" className="mt-2 rounded-lg max-h-32 object-contain" />
        )}
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-border bg-card px-4 py-3 shadow-sm max-w-[360px]">
      <div className="flex items-center gap-2 text-sm font-medium mb-2">
        <Icon className="h-4 w-4 text-primary" />
        <span>需要您的确认</span>
      </div>

      <p className="text-sm text-foreground mb-2 whitespace-pre-line">{description}</p>

      {receiptInfo && (
        <div className="mb-3">
          {isBase64Image(receiptInfo) ? (
            <div className="flex flex-col items-center gap-1 py-1">
              <img src={receiptInfo} alt="收款码" className="rounded-lg max-h-40 object-contain border border-border" />
              <div className="text-[10px] text-muted-foreground">扫码付款</div>
            </div>
          ) : (
            <a
              href={receiptInfo}
              target="_blank"
              rel="noopener noreferrer"
              className="block rounded-lg bg-accent/30 px-3 py-2 text-sm text-accent-foreground hover:bg-accent/50 break-all"
            >
              {receiptInfo}
            </a>
          )}
        </div>
      )}

      {senderCard && (
        <div className="rounded-lg bg-muted/40 border border-border/50 px-3 py-2 mb-3">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary">
              {senderCard.name.slice(0, 2).toUpperCase()}
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium truncate">{senderCard.name}</p>
              <p className="text-[10px] text-muted-foreground truncate">
                {senderCard.kind}{senderCard.entity_uid ? ` · ${senderCard.entity_uid}` : ""}
              </p>
            </div>
          </div>
          {senderCard.description && (
            <p className="text-xs text-muted-foreground mt-1.5 line-clamp-2">{senderCard.description}</p>
          )}
        </div>
      )}

      {requiresInput && (
        <div className="mb-2 space-y-2">
          {!editing && inputValue ? (
            <div className="relative">
              {isBase64Image(inputValue) ? (
                <img src={inputValue} alt="收款码" className="rounded-lg max-h-40 object-contain border border-border" />
              ) : (
                <div className="rounded-lg bg-muted/50 px-3 py-2 text-sm break-all">{inputValue}</div>
              )}
              <button
                type="button"
                onClick={() => setEditing(true)}
                className="absolute -top-1.5 -right-1.5 rounded-full bg-primary text-primary-foreground p-1"
              >
                <Pencil className="h-3 w-3" />
              </button>
            </div>
          ) : (
            <>
              {imagePreview ? (
                <div className="relative inline-block">
                  <img src={imagePreview} alt="预览" className="rounded-lg max-h-40 object-contain border border-border" />
                  <button
                    type="button"
                    onClick={clearImage}
                    className="absolute -top-1.5 -right-1.5 rounded-full bg-destructive text-destructive-foreground p-0.5"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </div>
              ) : (
                <textarea
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  placeholder="输入收款链接或拒绝理由..."
                  rows={2}
                  className={cn(
                    "w-full rounded-lg border border-border bg-background px-3 py-2 text-sm",
                    "focus:outline-none focus:ring-1 focus:ring-primary resize-none",
                  )}
                />
              )}
              {!imagePreview && (
                <label className={cn(
                  "inline-flex items-center gap-1.5 rounded-lg border border-dashed border-border",
                  "px-3 py-1.5 text-xs text-muted-foreground cursor-pointer",
                  "hover:bg-muted/50 transition-colors",
                )}>
                  <ImagePlus className="h-3.5 w-3.5" />
                  <span>上传收款码</span>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/*"
                    className="hidden"
                    onChange={handleImageUpload}
                  />
                </label>
              )}
            </>
          )}
        </div>
      )}

      {error && <div className="text-xs text-destructive mb-2">{error}</div>}

      <div className="flex gap-2">
        {availableActions.map((action) => (
          <button
            key={action}
            type="button"
            onClick={() => respond(action)}
            disabled={busy}
            className={cn(
              "flex-1 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
              POSITIVE_ACTIONS.has(action)
                ? "bg-success text-success-foreground hover:bg-success/90"
                : "bg-destructive text-destructive-foreground hover:bg-destructive/90",
              busy && "opacity-50 cursor-not-allowed",
            )}
          >
            {busy ? "处理中..." : ACTION_LABELS[action] ?? action}
          </button>
        ))}
      </div>
    </div>
  );
}

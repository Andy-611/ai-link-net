/* Publish market order dialog — category-first flow. */

import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import type { TradeApiClient } from "@/api/trade";
import type { Contact, OrderCategory, OrderType, TradeMode } from "@/types";

const CATEGORY_OPTIONS: { value: OrderCategory; label: string; desc: string }[] = [
  { value: "task", label: "Task", desc: "Full trade lifecycle" },
  { value: "matchmaking", label: "Matchmaking", desc: "Find and meet people" },
  { value: "job", label: "Job", desc: "Recruiting opportunities" },
  { value: "secondhand", label: "Secondhand", desc: "Used goods" },
  { value: "service", label: "Service", desc: "Skills & consulting" },
];

function inferTradeMode(category: OrderCategory): TradeMode {
  return category === "task" ? "autonomous" : "facilitation";
}

interface PublishOrderDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  entities: Contact[];
  currentUserUid: string;
  tradeClient: TradeApiClient;
  onPublished: () => void;
  defaultCategory?: OrderCategory;
}

export function PublishOrderDialog({
  open,
  onOpenChange,
  entities,
  currentUserUid,
  tradeClient,
  onPublished,
  defaultCategory,
}: PublishOrderDialogProps) {
  const [publisher, setPublisher] = useState(currentUserUid);
  const [category, setCategory] = useState<OrderCategory | "">(defaultCategory ?? "");
  const [orderType, setOrderType] = useState<OrderType>("demand");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [budget, setBudget] = useState("");
  const [tags, setTags] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (open) {
      setCategory(defaultCategory ?? "");
      setOrderType("demand");
      setTitle("");
      setDescription("");
      setBudget("");
      setTags("");
    }
  }, [open, defaultCategory]);

  const showOrderType = category !== "" && category !== "matchmaking";
  const tradeMode: TradeMode | null = category ? inferTradeMode(category) : null;

  const handleSubmit = async () => {
    if (!publisher || !title.trim() || !category) return;
    setSubmitting(true);
    try {
      const effectiveOrderType: OrderType = category === "matchmaking" ? "demand" : orderType;
      const entity = entities.find((e) => e.entity_uid === publisher);
      const address = entity ? `${entity.host_uid}:${entity.entity_uid}` : "";
      await tradeClient.publishOrder(
        publisher,
        effectiveOrderType,
        title.trim(),
        description.trim(),
        budget ? parseFloat(budget) : null,
        tags
          ? tags.split(",").map((t) => t.trim()).filter(Boolean)
          : [],
        category as OrderCategory,
        tradeMode!,
        address,
      );
      onOpenChange(false);
      onPublished();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="text-sm">Publish Order</DialogTitle>
          <DialogDescription>
            {tradeMode === "autonomous"
              ? "Entity completes the full trade lifecycle."
              : tradeMode === "facilitation"
                ? "Agent will negotiate on your behalf."
                : "Select a category to get started."}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div>
            <label className="text-xs text-muted-foreground mb-1 block">
              Publisher
            </label>
            <select
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={publisher}
              onChange={(e) => setPublisher(e.target.value)}
            >
              {entities.map((e) => (
                <option key={e.entity_uid} value={e.entity_uid}>
                  {e.name} ({e.entity_uid.slice(0, 8)})
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs text-muted-foreground mb-1 block">
              Category
            </label>
            <select
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={category}
              onChange={(e) => setCategory(e.target.value as OrderCategory | "")}
            >
              <option value="">Select category...</option>
              {CATEGORY_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label} — {opt.desc}
                </option>
              ))}
            </select>
          </div>
          {showOrderType && (
            <div>
              <label className="text-xs text-muted-foreground mb-1 block">
                Order Type
              </label>
              <select
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={orderType}
                onChange={(e) => setOrderType(e.target.value as OrderType)}
              >
                <option value="demand">Demand</option>
                <option value="supply">Supply</option>
              </select>
            </div>
          )}
          <div>
            <label className="text-xs text-muted-foreground mb-1 block">
              Title
            </label>
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder={
                category === "matchmaking"
                  ? "e.g. Looking for tech friends in Shanghai"
                  : category === "task"
                    ? "e.g. Need market research report"
                    : "Describe what you need or offer"
              }
            />
          </div>
          <div>
            <label className="text-xs text-muted-foreground mb-1 block">
              Description
            </label>
            <textarea
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm min-h-[60px] resize-none"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Detailed description..."
            />
          </div>
          <div className="flex gap-3">
            <div className="flex-1">
              <label className="text-xs text-muted-foreground mb-1 block">
                Budget (optional)
              </label>
              <Input
                type="number"
                value={budget}
                onChange={(e) => setBudget(e.target.value)}
                placeholder="0"
              />
            </div>
            <div className="flex-1">
              <label className="text-xs text-muted-foreground mb-1 block">
                Tags (comma-separated)
              </label>
              <Input
                value={tags}
                onChange={(e) => setTags(e.target.value)}
                placeholder="research, report"
              />
            </div>
          </div>
          <Button
            className="w-full"
            size="sm"
            disabled={!title.trim() || !publisher || !category || submitting}
            onClick={handleSubmit}
          >
            {submitting && <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />}
            Publish
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

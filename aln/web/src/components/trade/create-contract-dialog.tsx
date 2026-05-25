/* Create contract dialog — form for creating a new contract. */

import { useState } from "react";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import type { TradeApiClient } from "@/api/trade";
import type { Contact } from "@/types";

interface CreateContractDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  entities: Contact[];
  currentUserUid: string;
  tradeClient: TradeApiClient;
  onCreated: () => void;
}

export function CreateContractDialog({
  open,
  onOpenChange,
  entities,
  tradeClient,
  onCreated,
}: CreateContractDialogProps) {
  const [loading, setLoading] = useState(false);
  const [partyA, setPartyA] = useState("");
  const [partyB, setPartyB] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [amount, setAmount] = useState("");
  const [fundingMode, setFundingMode] = useState<"escrow" | "direct">("direct");

  function resetForm() {
    setPartyA("");
    setPartyB("");
    setTitle("");
    setDescription("");
    setAmount("");
    setFundingMode("direct");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!partyA || !partyB || !title || !amount) return;

    const entityA = entities.find((en) => en.entity_uid === partyA);
    const entityB = entities.find((en) => en.entity_uid === partyB);
    if (!entityA || !entityB) return;

    setLoading(true);
    try {
      await tradeClient.tradeSend(partyA, "contract_create", {
        party_a: { address: entityA.address.address },
        party_b: { address: entityB.address.address },
        title,
        description,
        amount: parseFloat(amount),
        funding_mode: fundingMode,
      });
      resetForm();
      onOpenChange(false);
      onCreated();
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }

  const canSubmit = partyA && partyB && partyA !== partyB && title && amount;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="text-sm font-heading">
            New Contract
          </DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          {/* Party A */}
          <label className="text-xs text-muted-foreground">
            Party A (Payer)
          </label>
          <select
            value={partyA}
            onChange={(e) => setPartyA(e.target.value)}
            className="h-9 rounded-md border border-border bg-background px-3 text-sm"
          >
            <option value="">Select entity...</option>
            {entities.map((en) => (
              <option key={en.entity_uid} value={en.entity_uid}>
                {en.name} ({en.kind})
              </option>
            ))}
          </select>

          {/* Party B */}
          <label className="text-xs text-muted-foreground">
            Party B (Provider)
          </label>
          <select
            value={partyB}
            onChange={(e) => setPartyB(e.target.value)}
            className="h-9 rounded-md border border-border bg-background px-3 text-sm"
          >
            <option value="">Select entity...</option>
            {entities.map((en) => (
              <option key={en.entity_uid} value={en.entity_uid}>
                {en.name} ({en.kind})
              </option>
            ))}
          </select>

          {/* Title */}
          <label className="text-xs text-muted-foreground">Title</label>
          <Input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Contract title"
          />

          {/* Description */}
          <label className="text-xs text-muted-foreground">Description</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Task description..."
            rows={3}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm resize-none"
          />

          {/* Amount + Mode */}
          <div className="flex gap-3">
            <div className="flex-1">
              <label className="text-xs text-muted-foreground">Amount</label>
              <Input
                type="number"
                min="0"
                step="0.01"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                placeholder="0.00"
              />
            </div>
            <div className="flex-1">
              <label className="text-xs text-muted-foreground">
                Funding Mode
              </label>
              <select
                value={fundingMode}
                onChange={(e) =>
                  setFundingMode(e.target.value as "escrow" | "direct")
                }
                className="h-9 w-full rounded-md border border-border bg-background px-3 text-sm"
              >
                <option value="direct">Direct</option>
                <option value="escrow">Escrow</option>
              </select>
            </div>
          </div>

          <Button type="submit" disabled={!canSubmit || loading} className="mt-2">
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin mr-2" />
            ) : null}
            Create Contract
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}

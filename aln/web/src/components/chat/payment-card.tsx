import { useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { CheckCircle2, Wallet, Copy } from "lucide-react";

import type { Message } from "@/types";

function shortUid(address: string): string {
  const uid = address.split(":").pop() ?? address;
  return uid.slice(0, 8);
}

interface PaymentCardProps {
  message: Message;
  selfEntityUid: string;
  state: "pending" | "claimed" | "completed";
  isSelf?: boolean;
}

export function PaymentCard({ message, selfEntityUid, state, isSelf }: PaymentCardProps) {
  const kind = message.kind ?? "";
  const payload = message.payload as Record<string, unknown>;

  if (kind === "pay_collect" || kind === "pay_request") {
    return <PayCollectCard message={message} selfEntityUid={selfEntityUid} state={state} />;
  }
  if (kind === "pay_claim_completed") {
    return <PayClaimCard message={message} selfEntityUid={selfEntityUid} state={state} isSelf={isSelf} />;
  }
  if (kind === "pay_completed") {
    const paymentData = payload.payment as Record<string, unknown> | undefined;
    return <PayDoneBadge amount={Number(paymentData?.amount ?? payload.amount ?? 0)} />;
  }
  return null;
}

function PaymentMeta({ payerAddr, payeeAddr, contractId, paymentId }: {
  payerAddr?: string;
  payeeAddr?: string;
  contractId?: string;
  paymentId?: string;
}) {
  const parts: string[] = [];
  if (payerAddr) parts.push(`付款方: ${shortUid(payerAddr)}`);
  if (payeeAddr) parts.push(`收款方: ${shortUid(payeeAddr)}`);
  if (contractId) parts.push(`合同: ${contractId.slice(0, 12)}`);
  if (paymentId) parts.push(`支付单: ${paymentId.slice(0, 12)}`);
  if (parts.length === 0) return null;

  return (
    <div className="text-[10px] text-muted-foreground font-mono leading-relaxed mb-2">
      {parts.map((p, i) => <div key={i}>{p}</div>)}
    </div>
  );
}

function PayCollectCard({ message, state }: PaymentCardProps) {
  const payload = message.payload as Record<string, unknown>;
  const amount = Number(payload.amount ?? 0);
  const method = String(payload.method ?? "pay_link");
  const receiptInfo = String(payload.receipt_info ?? "");
  const paymentId = String(payload.payment_id ?? "");
  const contractId = (payload.contract_id as string | undefined) ?? "";
  const payerRaw = payload.payer as { address?: string } | undefined;
  const payeeRaw = payload.payee as { address?: string } | undefined;
  const payer = { address: payerRaw?.address ?? "" };
  const payee = { address: payeeRaw?.address ?? message.sender };

  if (state === "completed") {
    return <PayDoneBadge amount={amount} />;
  }

  const statusText = state === "claimed" ? "已付款，等待确认" : "等待付款中";

  return (
    <div className="rounded-2xl border border-border bg-card px-4 py-3 shadow-sm max-w-[360px]">
      <div className="flex items-center gap-2 text-sm font-medium mb-2">
        <Wallet className="h-4 w-4 text-primary" />
        <span>收款请求</span>
        <span className="ml-auto text-xs text-muted-foreground">{statusText}</span>
      </div>

      <div className="text-2xl font-semibold mb-3">¥ {amount.toFixed(2)}</div>

      <PayMethodRender method={method} receiptInfo={receiptInfo} />
      <PaymentMeta
        payerAddr={payer.address}
        payeeAddr={payee.address}
        contractId={contractId}
        paymentId={paymentId}
      />
    </div>
  );
}

function PayClaimCard({ message, state, isSelf }: PaymentCardProps) {
  const payload = message.payload as Record<string, unknown>;
  const paymentId = String(payload.payment_id ?? "");
  const contractId = (payload.contract_id as string | undefined) ?? "";
  const paymentData = payload.payment as Record<string, unknown> | undefined;
  const payerAddr = (paymentData?.payer as { address?: string } | undefined)?.address ?? "";
  const payeeAddr = (paymentData?.payee as { address?: string } | undefined)?.address ?? "";
  const amount = Number(paymentData?.amount ?? 0);
  const effectiveContractId = contractId || String(paymentData?.contract_id ?? "");

  if (state === "completed") {
    return <PayDoneBadge amount={amount} />;
  }

  return (
    <div className="rounded-2xl border border-border bg-card px-4 py-3 shadow-sm max-w-[360px]">
      <div className="flex items-center gap-2 text-sm font-medium mb-2">
        <Wallet className="h-4 w-4 text-primary" />
        <span>{isSelf ? "已标记付款，等待对方确认" : "对方已标记付款，等待确认中"}</span>
      </div>
      <div className="text-2xl font-semibold mb-2">¥ {amount.toFixed(2)}</div>
      <PaymentMeta
        payerAddr={payerAddr}
        payeeAddr={payeeAddr}
        contractId={effectiveContractId}
        paymentId={paymentId || String(paymentData?.payment_id ?? "")}
      />
    </div>
  );
}

function PayDoneBadge({ amount }: { amount: number }) {
  return (
    <div className="rounded-2xl border border-success/30 bg-success/5 px-4 py-3 shadow-sm max-w-[360px]">
      <div className="flex items-center gap-2 text-sm font-medium text-success">
        <CheckCircle2 className="h-4 w-4" />
        <span>交易完成</span>
      </div>
      <div className="text-lg font-semibold mt-1">¥ {amount.toFixed(2)}</div>
    </div>
  );
}

function PayMethodRender({ method, receiptInfo }: { method: string; receiptInfo: string }) {
  const [copied, setCopied] = useState(false);
  const isBase64Image = receiptInfo.startsWith("data:image/");

  async function copy() {
    try {
      await navigator.clipboard.writeText(receiptInfo);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* ignore */
    }
  }

  if (isBase64Image) {
    return (
      <div className="flex flex-col items-center gap-2 py-2">
        <img src={receiptInfo} alt="收款码" className="rounded-lg max-h-48 object-contain" />
        <div className="text-[10px] text-muted-foreground">扫码付款</div>
      </div>
    );
  }

  if (method === "qr_code") {
    return (
      <div className="flex flex-col items-center gap-2 py-2">
        <div className="rounded-lg bg-white p-3">
          <QRCodeSVG value={receiptInfo || " "} size={160} />
        </div>
        <div className="text-[10px] text-muted-foreground">扫码付款</div>
      </div>
    );
  }

  if (method === "pay_link") {
    return (
      <a
        href={receiptInfo}
        target="_blank"
        rel="noopener noreferrer"
        className="block rounded-lg bg-accent/30 px-3 py-2 text-sm text-accent-foreground hover:bg-accent/50 break-all"
      >
        {receiptInfo}
      </a>
    );
  }

  return (
    <div className="rounded-lg bg-muted px-3 py-2 flex items-start gap-2">
      <div className="flex-1 text-xs font-mono break-all">{receiptInfo}</div>
      <button
        type="button"
        onClick={copy}
        className="shrink-0 inline-flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground"
      >
        <Copy className="h-3 w-3" />
        {copied ? "已复制" : "复制"}
      </button>
    </div>
  );
}

/* Trade & Trust API. */

import axios from "axios";

import type {
  BalanceInfo,
  ContractReputationContribution,
  Contract,
  ContractWorkMessageResponse,
  MarketOrder,
  OrderCategory,
  OrderType,
  Payment,
  ReputationProfile,
  StandardResponse,
  TradeMode,
  TradeSendResponse,
} from "@/types";
import { apiClient, unwrap } from "./client";
import { fetchHostEndpoint, getParentHost, normalizeHostUrl } from "./host";

/* ── Standalone helpers (unchanged, target current host) ── */

export async function tradeSend(
  fromEntity: string,
  kind: string,
  payload: Record<string, unknown> = {},
  toEntity?: string,
): Promise<TradeSendResponse> {
  const body: Record<string, unknown> = { from_entity: fromEntity, kind, payload };
  if (toEntity) body.to_entity = toEntity;
  const { data } = await apiClient.post<StandardResponse<TradeSendResponse>>(
    "/trade/send",
    body,
  );
  return unwrap(data);
}

export async function listContracts(): Promise<Contract[]> {
  const { data } =
    await apiClient.get<StandardResponse<Contract[]>>("/trade/contracts");
  return data.data ?? [];
}

export async function getContract(contractId: string): Promise<Contract> {
  const { data } = await apiClient.get<StandardResponse<Contract>>(
    `/trade/contracts/${contractId}`,
  );
  return unwrap(data);
}

export async function listVendorReputation(): Promise<ReputationProfile[]> {
  const { data } =
    await apiClient.get<StandardResponse<ReputationProfile[]>>("/trade/reputation/vendors");
  return data.data ?? [];
}

export async function listContractReputation(): Promise<ContractReputationContribution[]> {
  const { data } =
    await apiClient.get<StandardResponse<ContractReputationContribution[]>>("/trade/reputation/contracts");
  return data.data ?? [];
}

export async function sendContractMessage(
  contractId: string,
  fromEntity: string,
  text: string,
): Promise<ContractWorkMessageResponse> {
  const { data } = await apiClient.post<StandardResponse<ContractWorkMessageResponse>>(
    `/trade/contracts/${contractId}/messages`,
    { from_entity: fromEntity, text },
  );
  return unwrap(data);
}

export async function listPayments(): Promise<Payment[]> {
  const { data } =
    await apiClient.get<StandardResponse<Payment[]>>("/trade/payments");
  return data.data ?? [];
}

export async function getBalance(entitySpec: string): Promise<BalanceInfo> {
  const { data } = await apiClient.get<StandardResponse<BalanceInfo>>(
    `/trade/balance/${entitySpec}`,
  );
  return unwrap(data);
}

/* ── Market Orders ── */

export async function listOrders(
  type?: OrderType,
  status?: string,
  category?: OrderCategory,
  tradeMode?: TradeMode,
): Promise<MarketOrder[]> {
  const params = new URLSearchParams();
  if (type) params.set("type", type);
  if (status) params.set("status", status);
  if (category) params.set("category", category);
  if (tradeMode) params.set("trade_mode", tradeMode);
  const qs = params.toString();
  const { data } = await apiClient.get<StandardResponse<MarketOrder[]>>(
    `/trade/orders${qs ? `?${qs}` : ""}`,
  );
  return data.data ?? [];
}

export async function publishOrder(
  publisher: string,
  orderType: OrderType,
  title: string,
  description: string,
  budget: number | null,
  tags: string[],
  category?: OrderCategory | null,
  tradeMode?: TradeMode,
  publisherAddress?: string,
): Promise<MarketOrder> {
  const { data } = await apiClient.post<StandardResponse<MarketOrder>>(
    "/trade/orders",
    {
      order_type: orderType,
      publisher,
      publisher_address: publisherAddress ?? "",
      title,
      description,
      budget,
      tags,
      category: category ?? undefined,
      trade_mode: tradeMode ?? "facilitation",
    },
  );
  return unwrap(data);
}

export async function archiveOrder(
  orderId: string,
  requester: string,
): Promise<MarketOrder> {
  const { data } = await apiClient.post<StandardResponse<MarketOrder>>(
    `/trade/orders/${orderId}/archive?requester=${requester}`,
  );
  return unwrap(data);
}

export async function deleteOrder(
  orderId: string,
  requester: string,
): Promise<void> {
  await apiClient.delete(
    `/trade/orders/${orderId}?requester=${requester}`,
  );
}

/* ── TradeApiClient: auto-discovers Arbiter host (current or parent) ── */

function getCurrentHostUrl(): string {
  try {
    const raw = localStorage.getItem("fp_current_user");
    if (raw) {
      const user = JSON.parse(raw) as { host_url?: string };
      if (user.host_url) return user.host_url.replace(/\/$/, "");
    }
  } catch { /* ignore */ }
  return "http://localhost:7001";
}

async function probeArbiter(hostUrl: string): Promise<boolean> {
  try {
    const url = `${normalizeHostUrl(hostUrl)}/api/v1/entities`;
    const { data } = await axios.get<StandardResponse<Array<{ kind: string }>>>(url, { timeout: 5000 });
    if (!data.success || !Array.isArray(data.data)) return false;
    return data.data.some((e) => e.kind === "arbiter");
  } catch {
    return false;
  }
}

export class TradeApiClient {
  private _arbiterUrl: string | null = null;
  private _isLocal = false;
  private _resolved = false;

  get available(): boolean { return this._resolved && this._arbiterUrl !== null; }
  get hostUrl(): string | null { return this._arbiterUrl; }

  async resolve(): Promise<boolean> {
    const currentUrl = getCurrentHostUrl();

    if (await probeArbiter(currentUrl)) {
      this._arbiterUrl = currentUrl;
      this._isLocal = true;
      this._resolved = true;
      return true;
    }

    try {
      const parent = await getParentHost();
      if (parent?.url && await probeArbiter(parent.url)) {
        this._arbiterUrl = normalizeHostUrl(parent.url);
        this._isLocal = false;
        this._resolved = true;
        return true;
      }
    } catch { /* parent unreachable */ }

    this._resolved = true;
    return false;
  }

  /* ── GET helpers ── */

  async listContracts(): Promise<Contract[]> {
    if (!this._arbiterUrl) return [];
    if (this._isLocal) return listContracts();
    return fetchHostEndpoint<Contract[]>(this._arbiterUrl, "/api/v1/trade/contracts")
      .catch(() => []);
  }

  async listPayments(): Promise<Payment[]> {
    if (!this._arbiterUrl) return [];
    if (this._isLocal) return listPayments();
    return fetchHostEndpoint<Payment[]>(this._arbiterUrl, "/api/v1/trade/payments")
      .catch(() => []);
  }

  async listVendorReputation(): Promise<ReputationProfile[]> {
    if (!this._arbiterUrl) return [];
    if (this._isLocal) return listVendorReputation();
    return fetchHostEndpoint<ReputationProfile[]>(
      this._arbiterUrl,
      "/api/v1/trade/reputation/vendors",
    ).catch(() => []);
  }

  async listContractReputation(): Promise<ContractReputationContribution[]> {
    if (!this._arbiterUrl) return [];
    if (this._isLocal) return listContractReputation();
    return fetchHostEndpoint<ContractReputationContribution[]>(
      this._arbiterUrl,
      "/api/v1/trade/reputation/contracts",
    ).catch(() => []);
  }

  async listOrders(
    type?: OrderType,
    status?: string,
    category?: OrderCategory,
    tradeMode?: TradeMode,
  ): Promise<MarketOrder[]> {
    return listOrders(type, status, category, tradeMode);
  }

  async getBalance(entitySpec: string): Promise<BalanceInfo> {
    if (!this._arbiterUrl) throw new Error("No Arbiter available");
    if (this._isLocal) return getBalance(entitySpec);
    return fetchHostEndpoint<BalanceInfo>(this._arbiterUrl, `/api/v1/trade/balance/${entitySpec}`);
  }

  async getContract(contractId: string): Promise<Contract> {
    if (!this._arbiterUrl) throw new Error("No Arbiter available");
    if (this._isLocal) return getContract(contractId);
    return fetchHostEndpoint<Contract>(this._arbiterUrl, `/api/v1/trade/contracts/${contractId}`);
  }

  async sendContractMessage(
    contractId: string,
    fromEntity: string,
    text: string,
  ): Promise<ContractWorkMessageResponse> {
    return this.postToCurrentHost<ContractWorkMessageResponse>(
      `/trade/contracts/${contractId}/messages`,
      { from_entity: fromEntity, text },
    );
  }

  /* ── POST/DELETE helpers ── */

  private async postToCurrentHost<T>(path: string, body?: unknown): Promise<T> {
    const currentUrl = getCurrentHostUrl();
    if (this._isLocal) {
      const { data } = await apiClient.post<StandardResponse<T>>(path, body);
      return unwrap(data);
    }
    const url = `${currentUrl}/api/v1${path}`;
    const { data } = await axios.post<StandardResponse<T>>(url, body, { timeout: 10000 });
    return unwrap(data);
  }

  async tradeSend(
    fromEntity: string,
    kind: string,
    payload: Record<string, unknown> = {},
  ): Promise<TradeSendResponse> {
    return this.postToCurrentHost<TradeSendResponse>("/trade/send", {
      from_entity: fromEntity, kind, payload,
    });
  }

  async publishOrder(
    publisher: string,
    orderType: OrderType,
    title: string,
    description: string,
    budget: number | null,
    tags: string[],
    category?: OrderCategory | null,
    tradeMode?: TradeMode,
    publisherAddress?: string,
  ): Promise<MarketOrder> {
    return publishOrder(publisher, orderType, title, description, budget, tags, category, tradeMode, publisherAddress);
  }

  async archiveOrder(orderId: string, requester: string): Promise<MarketOrder> {
    return archiveOrder(orderId, requester);
  }

  async deleteOrder(orderId: string, requester: string): Promise<void> {
    return deleteOrder(orderId, requester);
  }
}

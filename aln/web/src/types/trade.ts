/* Trade & Trust type definitions — mirrors fp/trade models and enums. */

export type ContractStatus =
  | "draft"
  | "pending"
  | "active"
  | "completing"
  | "settling"
  | "settled"
  | "cancelled"
  | "disputed";

export type FundingMode = "escrow" | "direct";

export type PaymentStatus =
  | "requested"
  | "approving"
  | "approved"
  | "rejected"
  | "executing"
  | "confirming"
  | "completed"
  | "disputed";

export type PaymentMethod =
  | "escrow"
  | "qr_code"
  | "pay_link"
  | "bank"
  | "crypto"
  | "gateway";

export type PayMode = "entity_pay" | "owner_pay";

export interface FPAddressRef {
  address: string;
  host_uid?: string;
  entity_uid?: string;
}

export interface ParticipantSnapshot {
  address: FPAddressRef;
  role: string;
  host_uid: string;
  entity_uid: string;
  sign_public_key: string;
  encrypt_public_key: string;
  display_name: string;
}

export interface ContractApproval {
  party_role: string;
  approved_revision: number;
  approved_terms_hash: string;
  approved_at: number;
  approved_by: FPAddressRef;
  source_mail_id?: string | null;
}

export interface ContractReceipt {
  recipient: FPAddressRef;
  status_message_id: string;
  snapshot_hash: string;
  acked_at: number;
  recipient_signature?: string | null;
}

export interface ArbiterAttestation {
  snapshot_hash: string;
  prev_snapshot_hash?: string | null;
  signed_at: number;
  signer: FPAddressRef;
  signature_alg: string;
  signature: string;
}

export interface ContractRating {
  rating: number;
  review?: string | null;
  rated_by: FPAddressRef;
  rated_at: number;
}

export interface DeliveryArtifact {
  kind: string;
  uri: string;
  label?: string | null;
  digest?: string | null;
  size_bytes?: number | null;
}

export interface DeliveryEvidence {
  delivery_id: string;
  version: string;
  summary: string;
  artifacts: DeliveryArtifact[];
  source_session_id?: string | null;
  source_message_id?: string | null;
  produced_by: FPAddressRef;
  produced_at: number;
}

export interface ExecutionCostReport {
  report_id?: string | null;
  actor: FPAddressRef;
  phase?: string | null;
  provider?: string | null;
  model?: string | null;
  input_tokens?: number | null;
  output_tokens?: number | null;
  cost_usd?: number | null;
  runtime_ms?: number | null;
  notes?: string | null;
  recorded_at: number;
}

export type ReputationRole = "party_a" | "party_b" | "arbiter";
export type ReputationOutcome = "accepted" | "settled" | "cancelled" | "disputed";

export interface ReputationEvent {
  event_id: string;
  contract_id: string;
  subject: FPAddressRef;
  role: ReputationRole;
  counterparty?: FPAddressRef | null;
  arbiter?: FPAddressRef | null;
  outcome: ReputationOutcome;
  rating?: number | null;
  review?: string | null;
  delivery_count: number;
  rework_count: number;
  dispute_count: number;
  cancel_count: number;
  total_cost_usd?: number | null;
  total_input_tokens?: number | null;
  total_output_tokens?: number | null;
  evidence_complete: boolean;
  signed_snapshot_count: number;
  created_at: number;
  source_snapshot_hash: string;
}

export interface ReputationFeatureVector {
  quality_score: number;
  reliability_score: number;
  collaboration_score: number;
  efficiency_score: number;
  integrity_score: number;
  confidence_weight: number;
  recency_weight: number;
}

export interface ReputationProfile {
  subject: FPAddressRef;
  role: ReputationRole;
  overall_score: number;
  confidence: number;
  sample_size: number;
  quality_score: number;
  reliability_score: number;
  collaboration_score: number;
  efficiency_score: number;
  integrity_score: number;
  recent_events: ReputationEvent[];
  updated_at: number;
}

export interface ContractReputationContribution {
  contract_id: string;
  title: string;
  status: ContractStatus;
  subject: FPAddressRef;
  counterparty: FPAddressRef;
  arbiter: FPAddressRef;
  contributes: boolean;
  reason: string;
  contract_score?: number | null;
  event?: ReputationEvent | null;
  feature?: ReputationFeatureVector | null;
  created_at: number;
  last_action?: string | null;
  last_action_at?: number | null;
}

export interface ContractSnapshot {
  contract_id: string;
  protocol_version: string;
  status: ContractStatus;
  participants: ParticipantSnapshot[];
  terms: {
    revision: number;
    title: string;
    description: string;
    amount: number;
    funding_mode: FundingMode;
    terms_hash: string;
  };
  approvals: ContractApproval[];
  rating?: ContractRating | null;
  receipts: ContractReceipt[];
  delivery?: DeliveryEvidence | null;
  execution_costs: ExecutionCostReport[];
  last_action?: string | null;
  last_actor?: FPAddressRef | null;
  last_reason?: string | null;
  last_action_at?: number | null;
  attestation?: ArbiterAttestation | null;
}

export interface Contract {
  contract_id: string;
  party_a: FPAddressRef;
  party_b: FPAddressRef;
  creator: FPAddressRef;
  arbiter: FPAddressRef;
  title: string;
  description: string;
  amount: number;
  funding_mode: FundingMode;
  status: ContractStatus;
  draft_version: number;
  terms_hash?: string;
  current_snapshot_hash?: string | null;
  prev_snapshot_hash?: string | null;
  work_session_id?: string | null;
  work_session_name?: string | null;
  participant_snapshots?: ParticipantSnapshot[];
  approvals?: ContractApproval[];
  receipts?: ContractReceipt[];
  snapshot_history?: ContractSnapshot[];
  current_delivery?: DeliveryEvidence | null;
  delivery_history?: DeliveryEvidence[];
  current_execution_costs?: ExecutionCostReport[];
  cost_history?: ExecutionCostReport[];
  rework_count: number;
  max_rework_count: number;
  rating: number | null;
  review: string | null;
  rated_by?: FPAddressRef | null;
  rated_at?: number | null;
  last_action?: string | null;
  last_actor?: FPAddressRef | null;
  last_reason?: string | null;
  last_action_at?: number | null;
  created_at: number;
  approved_at: number | null;
  activated_at: number | null;
  completed_at: number | null;
  settling_at: number | null;
  settled_at: number | null;
  cancelled_at: number | null;
  arbiter_signature: string | null;
  arbiter_signature_alg?: string;
  attestation?: ArbiterAttestation | null;
}

export interface Payment {
  payment_id: string;
  contract_id: string | null;
  payer: FPAddressRef;
  payee: FPAddressRef;
  amount: number;
  method: PaymentMethod;
  pay_mode: PayMode;
  status: PaymentStatus;
  receipt_info: string;
  requested_at: number;
  approved_at: number | null;
  executed_at: number | null;
  completed_at: number | null;
}

export interface BalanceInfo {
  entity_uid: string;
  entity_name: string;
  balance: number;
  available: number;
  frozen: number;
}

export interface TradeSendResponse {
  kind: string;
  from_entity: string;
  contracts: Record<string, Contract>;
  payments: Record<string, Payment>;
}

export interface ContractWorkMessageResponse {
  contract_id: string;
  session_id: string;
  session_name: string;
  message_id: string;
  mail_id: string;
  from_entity: string;
  to_address: string;
}

/* ── Market (app-layer) ── */

export type OrderType = "demand" | "supply";
export type OrderStatus = "active" | "archived";
export type OrderCategory = "task" | "matchmaking" | "job" | "secondhand" | "service";
export type TradeMode = "facilitation" | "autonomous";

export interface MarketOrder {
  order_id: string;
  order_type: OrderType;
  publisher: string;
  publisher_address: string;
  title: string;
  description: string;
  budget: number | null;
  tags: string[];
  category: OrderCategory | null;
  trade_mode: TradeMode;
  status: OrderStatus;
  created_at: number;
  archived_at: number | null;
}

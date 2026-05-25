import type {
  ArbiterAttestation,
  ContractApproval,
  ContractSnapshot,
  ContractStatus,
  FPAddressRef,
  FundingMode,
  ParticipantSnapshot,
  ReputationProfile,
} from "@/types";

export interface VendorParty {
  label: string;
  name: string;
  address: string;
  address_ref: FPAddressRef;
}

export interface VendorContractRecord {
  contract_id: string;
  title: string;
  description: string;
  status: ContractStatus;
  amount_usd: number;
  summary: string;
  payment_terms: string;
  start_date: string;
  renewal_date: string;
  funding_mode: FundingMode;
  draft_version: number;
  terms_hash: string;
  current_snapshot_hash: string;
  prev_snapshot_hash?: string | null;
  party_a: VendorParty;
  party_b: VendorParty;
  arbiter: VendorParty;
  participant_snapshots: ParticipantSnapshot[];
  approvals: ContractApproval[];
  snapshot_history: ContractSnapshot[];
  attestation?: ArbiterAttestation | null;
  rework_count?: number;
  max_rework_count?: number;
  created_at?: number | null;
  last_action?: string | null;
  last_action_at?: number | null;
}

export interface VendorRecord {
  vendor_id: string;
  name: string;
  legal_name: string;
  category: string;
  tier: string;
  region: string;
  primary_contact: string;
  contact_email: string;
  active_contracts: number;
  last_activity: string;
  health: "healthy" | "attention" | "pending";
  reputation?: ReputationProfile | null;
  contract: VendorContractRecord;
}

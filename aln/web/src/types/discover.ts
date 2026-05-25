import type { Contact } from "./api";

export type HostRelation = "self" | "parent" | "child" | "remote";

export interface DiscoverHost {
  uid: string;
  name: string;
  url: string;
  relation: HostRelation;
}

export interface HostTopologyEdge {
  parentUid: string;
  childUid: string;
}

export interface HostTopologySnapshot {
  hosts: Omit<DiscoverHost, "relation">[];
  edges: HostTopologyEdge[];
  selfUid: string | null;
  directParentUid: string | null;
  directChildUids: string[];
}

export interface HostEntityGroup {
  host: DiscoverHost;
  entities: Contact[];
}

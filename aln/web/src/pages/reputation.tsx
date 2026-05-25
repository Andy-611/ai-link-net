import { useEffect, useMemo, useState } from "react";
import { BarChart3, FileStack, Loader2, Star } from "lucide-react";

import { listEntities } from "@/api";
import { TradeApiClient } from "@/api/trade";
import { StatusBadge } from "@/components/trade/contract-detail";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type {
  Contact,
  ContractReputationContribution,
  FPAddressRef,
  ReputationProfile,
} from "@/types";

function shortAddress(value: string, head = 8, tail = 6): string {
  if (value.length <= head + tail + 1) return value;
  return `${value.slice(0, head)}…${value.slice(-tail)}`;
}

function formatPercent(value: number | null | undefined): string {
  if (value == null) return "-";
  return `${value.toFixed(1)}/100`;
}

function resolveName(
  address: FPAddressRef,
  entitiesByUid: Map<string, Contact>,
): string {
  const entityUid = address.entity_uid ?? address.address.split(":").at(-1) ?? address.address;
  return entitiesByUid.get(entityUid)?.name ?? entityUid;
}

function formatTime(value: number | null | undefined): string {
  if (!value) return "-";
  return new Date(value * 1000).toLocaleString();
}

interface SubjectSummary {
  address: string;
  subject: FPAddressRef;
  name: string;
  profile: ReputationProfile | null;
  contractCount: number;
  scoredCount: number;
}

export function ReputationPage() {
  const [tradeClient] = useState(() => new TradeApiClient());
  const [profiles, setProfiles] = useState<ReputationProfile[]>([]);
  const [contributions, setContributions] = useState<ContractReputationContribution[]>([]);
  const [entities, setEntities] = useState<Contact[]>([]);
  const [selectedSubject, setSelectedSubject] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function load() {
      setLoading(true);
      setError(null);

      const available = await tradeClient.resolve();
      if (!active) return;

      if (!available) {
        setError("No Arbiter-backed host is available for reputation data.");
        setProfiles([]);
        setContributions([]);
        setLoading(false);
        return;
      }

      try {
        const [nextProfiles, nextContributions, nextEntities] = await Promise.all([
          tradeClient.listVendorReputation(),
          tradeClient.listContractReputation(),
          listEntities(),
        ]);
        if (!active) return;
        setProfiles(nextProfiles);
        setContributions(nextContributions);
        setEntities(nextEntities);
      } catch {
        if (!active) return;
        setProfiles([]);
        setContributions([]);
        setError("Failed to load reputation data.");
      } finally {
        if (active) setLoading(false);
      }
    }

    void load();
    return () => {
      active = false;
    };
  }, [tradeClient]);

  const entitiesByUid = useMemo(
    () => new Map(entities.map((entity) => [entity.entity_uid, entity])),
    [entities],
  );

  const subjectSummaries = useMemo<SubjectSummary[]>(() => {
    const profileByAddress = new Map(profiles.map((profile) => [profile.subject.address, profile]));
    const grouped = new Map<string, ContractReputationContribution[]>();
    contributions.forEach((row) => {
      const key = row.subject.address;
      const existing = grouped.get(key) ?? [];
      existing.push(row);
      grouped.set(key, existing);
    });

    return [...grouped.entries()]
      .map(([address, rows]) => {
        const subject = rows[0]?.subject ?? profileByAddress.get(address)?.subject;
        if (!subject) return null;
        const profile = profileByAddress.get(address) ?? null;
        return {
          address,
          subject,
          name: resolveName(subject, entitiesByUid),
          profile,
          contractCount: rows.length,
          scoredCount: rows.filter((row) => row.contributes).length,
        };
      })
      .filter((item): item is SubjectSummary => item !== null)
      .sort((left, right) => {
        const scoreGap = (right.profile?.overall_score ?? -1) - (left.profile?.overall_score ?? -1);
        if (scoreGap !== 0) return scoreGap;
        return left.name.localeCompare(right.name);
      });
  }, [contributions, entitiesByUid, profiles]);

  useEffect(() => {
    if (subjectSummaries.length === 0) {
      setSelectedSubject("");
      return;
    }
    if (!subjectSummaries.some((item) => item.address === selectedSubject)) {
      setSelectedSubject(subjectSummaries[0]?.address ?? "");
    }
  }, [selectedSubject, subjectSummaries]);

  const selectedSummary =
    subjectSummaries.find((item) => item.address === selectedSubject) ?? subjectSummaries[0] ?? null;
  const selectedProfile = selectedSummary?.profile ?? null;
  const selectedRows = useMemo(
    () => contributions.filter((row) => row.subject.address === selectedSummary?.address),
    [contributions, selectedSummary?.address],
  );

  const scoredContracts = contributions.filter((row) => row.contributes).length;
  const pendingContracts = contributions.length - scoredContracts;

  return (
    <div className="min-h-full bg-[radial-gradient(circle_at_top_left,_rgba(15,123,108,0.08),_transparent_38%),linear-gradient(180deg,rgba(255,255,255,0.98),rgba(247,247,245,0.96))] p-4 md:p-6">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
        <section className="overflow-hidden rounded-[2rem] border border-border bg-card/95 shadow-sm">
          <div className="grid gap-6 px-5 py-6 md:grid-cols-[minmax(0,1.4fr)_minmax(18rem,0.6fr)] md:px-7">
            <div>
              <div className="flex flex-wrap items-center gap-3">
                <Badge variant="secondary" className="rounded-full px-3 py-1 text-[11px]">
                  Reputation v1
                </Badge>
                <Badge variant="secondary" className="rounded-full px-3 py-1 text-[11px]">
                  Contract contribution view
                </Badge>
              </div>
              <h1 className="mt-4 max-w-3xl font-heading text-3xl font-semibold tracking-tight text-foreground md:text-4xl">
                Contract reputation is shown as an explainable derived view over signed Trade & Trust evidence.
              </h1>
              <p className="mt-4 max-w-3xl text-sm leading-7 text-muted-foreground md:text-base">
                Closed-loop contracts contribute score. Draft, active, and under-review contracts stay visible here too,
                but they are explicitly marked as not yet contributing so in-flight work does not look broken.
              </p>
            </div>

            <div className="grid gap-3 sm:grid-cols-3 md:grid-cols-1">
              <MetricCard icon={BarChart3} label="Tracked vendors" value={String(subjectSummaries.length)} detail="Vendor reputation profiles derived from signed contracts" />
              <MetricCard icon={Star} label="Scored contracts" value={String(scoredContracts)} detail="Contracts already contributing to vendor reputation" />
              <MetricCard icon={FileStack} label="Pending contracts" value={String(pendingContracts)} detail="Visible contracts that are not yet counted because they are still in flight" />
            </div>
          </div>
        </section>

        {loading ? (
          <section className="flex min-h-[20rem] items-center justify-center rounded-3xl border border-border bg-card/90 p-6 text-sm text-muted-foreground">
            <div className="flex items-center gap-3">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading reputation data.
            </div>
          </section>
        ) : error ? (
          <section className="flex min-h-[20rem] items-center justify-center rounded-3xl border border-dashed border-border bg-card/90 p-6 text-center text-sm text-muted-foreground">
            {error}
          </section>
        ) : (
          <div className="grid gap-6 xl:grid-cols-[minmax(21rem,0.8fr)_minmax(0,1.2fr)]">
            <section className="rounded-3xl border border-border bg-card/95 shadow-sm">
              <div className="border-b border-border px-5 py-4">
                <p className="text-xs font-medium uppercase tracking-[0.24em] text-muted-foreground">
                  Vendor Profiles
                </p>
                <h2 className="mt-1 font-heading text-xl font-semibold text-foreground">
                  Aggregate vendor reputation
                </h2>
              </div>
              <div className="divide-y divide-border">
                {subjectSummaries.length === 0 ? (
                  <div className="px-5 py-8 text-sm text-muted-foreground">
                    No reputation-relevant contracts exist yet.
                  </div>
                ) : (
                  subjectSummaries.map((item) => {
                    const active = item.address === selectedSummary?.address;
                    return (
                      <button
                        key={item.address}
                        type="button"
                        onClick={() => setSelectedSubject(item.address)}
                        className={cn(
                          "flex w-full items-start justify-between gap-4 px-5 py-4 text-left transition-colors",
                          active ? "bg-accent/6" : "hover:bg-muted/60",
                        )}
                      >
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <p className="truncate text-sm font-semibold text-foreground">{item.name}</p>
                            {item.profile ? (
                              <Badge variant="secondary" className="rounded-full px-2 py-0.5 text-[10px]">
                                {item.profile.overall_score.toFixed(1)}/100
                              </Badge>
                            ) : (
                              <Badge variant="secondary" className="rounded-full px-2 py-0.5 text-[10px]">
                                Pending
                              </Badge>
                            )}
                          </div>
                          <p className="mt-1 font-mono text-[11px] text-muted-foreground">
                            {shortAddress(item.address)}
                          </p>
                          <p className="mt-2 text-[11px] text-muted-foreground">
                            {item.scoredCount}/{item.contractCount} contracts contributing
                          </p>
                        </div>
                      </button>
                    );
                  })
                )}
              </div>
            </section>

            <div className="space-y-6">
              <section className="rounded-3xl border border-border bg-card/95 shadow-sm">
                <div className="border-b border-border px-5 py-4">
                  <p className="text-xs font-medium uppercase tracking-[0.24em] text-muted-foreground">
                    Selected Vendor
                  </p>
                  <h2 className="mt-1 font-heading text-xl font-semibold text-foreground">
                    {selectedSummary ? selectedSummary.name : "No vendor selected"}
                  </h2>
                </div>
                <div className="p-5">
                  {selectedSummary ? (
                    selectedProfile ? (
                      <div className="space-y-4">
                        <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/5 p-4">
                          <div className="flex items-end justify-between gap-3">
                            <div>
                              <p className="text-3xl font-semibold text-foreground">
                                {selectedProfile.overall_score.toFixed(1)}
                              </p>
                              <p className="text-sm text-muted-foreground">
                                Confidence {(selectedProfile.confidence * 100).toFixed(0)}% · {selectedProfile.sample_size} scored contract
                                {selectedProfile.sample_size === 1 ? "" : "s"}
                              </p>
                            </div>
                            <Badge variant="secondary" className="bg-emerald-500/15 text-emerald-700 dark:text-emerald-300">
                              Derived from signed facts
                            </Badge>
                          </div>
                        </div>
                        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
                          <MetricTile label="Quality" value={formatPercent(selectedProfile.quality_score)} />
                          <MetricTile label="Reliability" value={formatPercent(selectedProfile.reliability_score)} />
                          <MetricTile label="Collaboration" value={formatPercent(selectedProfile.collaboration_score)} />
                          <MetricTile label="Efficiency" value={formatPercent(selectedProfile.efficiency_score)} />
                          <MetricTile label="Integrity" value={formatPercent(selectedProfile.integrity_score)} />
                        </div>
                      </div>
                    ) : (
                      <div className="rounded-2xl border border-dashed border-border bg-muted/35 p-4 text-sm text-muted-foreground">
                        This vendor has visible contracts, but none of them have reached a signed closed-loop status yet.
                      </div>
                    )
                  ) : (
                    <div className="text-sm text-muted-foreground">
                      Select a vendor to inspect reputation details.
                    </div>
                  )}
                </div>
              </section>

              <section className="rounded-3xl border border-border bg-card/95 shadow-sm">
                <div className="border-b border-border px-5 py-4">
                  <p className="text-xs font-medium uppercase tracking-[0.24em] text-muted-foreground">
                    Contract Contributions
                  </p>
                  <h2 className="mt-1 font-heading text-xl font-semibold text-foreground">
                    How each contract affects reputation
                  </h2>
                </div>
                <div className="space-y-4 p-5">
                  {selectedRows.length === 0 ? (
                    <p className="text-sm text-muted-foreground">
                      No contracts found for this vendor.
                    </p>
                  ) : (
                    selectedRows.map((row) => (
                      <article key={row.contract_id} className="rounded-2xl border border-border bg-muted/25 p-4">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div>
                            <div className="flex flex-wrap items-center gap-2">
                              <p className="font-semibold text-foreground">{row.title}</p>
                              <StatusBadge status={row.status} />
                              <Badge
                                variant="secondary"
                                className={cn(
                                  "rounded-full px-2 py-0.5 text-[10px]",
                                  row.contributes
                                    ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300"
                                    : "bg-muted text-muted-foreground",
                                )}
                              >
                                {row.contributes ? "Contributes" : "Not scored yet"}
                              </Badge>
                            </div>
                            <p className="mt-2 text-sm text-muted-foreground">{row.reason}</p>
                          </div>
                          <div className="text-right">
                            <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                              Contract score
                            </p>
                            <p className="mt-1 text-lg font-semibold text-foreground">
                              {row.contract_score != null ? `${row.contract_score.toFixed(1)}/100` : "-"}
                            </p>
                          </div>
                        </div>

                        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                          <MetricTile label="Updated" value={formatTime(row.last_action_at ?? row.created_at)} />
                          <MetricTile label="Last action" value={row.last_action ?? "-"} />
                          <MetricTile label="Outcome" value={row.event?.outcome ?? "-"} />
                          <MetricTile label="Rating" value={row.event?.rating != null ? `${row.event.rating}/5` : "-"} />
                        </div>

                        {row.feature ? (
                          <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
                            <MetricTile label="Quality" value={formatPercent(row.feature.quality_score * 100)} />
                            <MetricTile label="Reliability" value={formatPercent(row.feature.reliability_score * 100)} />
                            <MetricTile label="Collaboration" value={formatPercent(row.feature.collaboration_score * 100)} />
                            <MetricTile label="Efficiency" value={formatPercent(row.feature.efficiency_score * 100)} />
                            <MetricTile label="Integrity" value={formatPercent(row.feature.integrity_score * 100)} />
                          </div>
                        ) : null}

                        {row.event ? (
                          <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                            <MetricTile label="Deliveries" value={String(row.event.delivery_count)} />
                            <MetricTile label="Rework count" value={String(row.event.rework_count)} />
                            <MetricTile label="Signed snapshots" value={String(row.event.signed_snapshot_count)} />
                            <MetricTile label="Execution cost" value={row.event.total_cost_usd != null ? `$${row.event.total_cost_usd.toFixed(2)}` : "-"} />
                          </div>
                        ) : null}
                      </article>
                    ))
                  )}
                </div>
              </section>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function MetricCard({
  detail,
  icon: Icon,
  label,
  value,
}: {
  detail: string;
  icon: typeof BarChart3;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-3xl border border-border bg-muted/45 p-4">
      <div className="flex items-center justify-between">
        <p className="text-[11px] font-medium uppercase tracking-[0.22em] text-muted-foreground">
          {label}
        </p>
        <div className="flex h-9 w-9 items-center justify-center rounded-2xl bg-background/90 text-foreground">
          <Icon className="h-4 w-4" />
        </div>
      </div>
      <p className="mt-4 text-lg font-semibold text-foreground">{value}</p>
      <p className="mt-2 text-xs leading-5 text-muted-foreground">{detail}</p>
    </div>
  );
}

function MetricTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-border bg-background/90 p-3">
      <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-muted-foreground">
        {label}
      </p>
      <p className="mt-2 text-sm font-semibold text-foreground">{value}</p>
    </div>
  );
}

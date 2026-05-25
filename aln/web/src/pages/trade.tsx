/* Trade page — My Trade / Market tabs. */

import { useCallback, useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Archive,
  Banknote,
  Briefcase,
  ClipboardList,
  Eye,
  FileText,
  Handshake,
  Heart,
  LayoutGrid,
  Loader2,
  Megaphone,
  Package,
  Plus,
  RefreshCw,
  Search,
  Store,
  Wallet,
  Wrench,
} from "lucide-react";

import { cn, EASE_SMOOTH } from "@/lib/utils";
import { listEntities } from "@/api";
import { TradeApiClient } from "@/api/trade";
import { useAppStore } from "@/stores/app";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { SpotlightCard } from "@/components/effects/spotlight-card";
import { CreateContractDialog } from "@/components/trade/create-contract-dialog";
import {
  ContractDetail,
  StatusBadge,
} from "@/components/trade/contract-detail";
import { ObserverView } from "@/components/trade/observer-view";
import { PublishOrderDialog } from "@/components/trade/publish-order-dialog";
import type {
  BalanceInfo,
  Contact,
  Contract,
  MarketOrder,
  OrderCategory,
  OrderType,
  Payment,
  PaymentStatus,
} from "@/types";

/* ──────────── Constants ──────────── */

type TabId = "my-trade" | "market";
type SortOption = "recent" | "budget-high" | "budget-low";

const TABS: { id: TabId; label: string; icon: typeof Wallet }[] = [
  { id: "my-trade", label: "My Trade", icon: Wallet },
  { id: "market", label: "Market", icon: Store },
];

const CATEGORIES: { id: OrderCategory; label: string; icon: typeof Wallet }[] = [
  { id: "task", label: "Task", icon: ClipboardList },
  { id: "matchmaking", label: "Matchmaking", icon: Heart },
  { id: "job", label: "Job", icon: Briefcase },
  { id: "secondhand", label: "Secondhand", icon: Package },
  { id: "service", label: "Service", icon: Wrench },
];

const CATEGORY_COLORS: Record<OrderCategory, string> = {
  task: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
  matchmaking: "bg-pink-500/15 text-pink-600 dark:text-pink-400",
  job: "bg-blue-500/15 text-blue-600 dark:text-blue-400",
  secondhand: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
  service: "bg-violet-500/15 text-violet-600 dark:text-violet-400",
};

const PAY_STATUS_COLORS: Record<PaymentStatus, string> = {
  requested: "bg-muted text-muted-foreground",
  approving: "bg-yellow-500/15 text-yellow-600 dark:text-yellow-400",
  approved: "bg-blue-500/15 text-blue-600 dark:text-blue-400",
  rejected: "bg-red-500/15 text-red-600 dark:text-red-400",
  executing: "bg-orange-500/15 text-orange-600 dark:text-orange-400",
  confirming: "bg-blue-500/15 text-blue-600 dark:text-blue-400",
  completed: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
  disputed: "bg-purple-500/15 text-purple-600 dark:text-purple-400",
};

const cardVariants = {
  hidden: { opacity: 0, y: 12, scale: 0.97 },
  show: (i: number) => ({
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { delay: i * 0.05, duration: 0.3, ease: EASE_SMOOTH },
  }),
};

/* ──────────── Trade Page ──────────── */

export function TradePage() {
  const currentUser = useAppStore((s) => s.currentUser);
  const currentUserUid = currentUser?.entity_uid ?? "";

  const [tradeClient] = useState(() => new TradeApiClient());
  const [tab, setTab] = useState<TabId>("my-trade");
  const [loading, setLoading] = useState(false);
  const [arbiterReady, setArbiterReady] = useState(false);
  const [allEntities, setAllEntities] = useState<Contact[]>([]);

  // My Trade state
  const [contracts, setContracts] = useState<Contract[]>([]);
  const [payments, setPayments] = useState<Payment[]>([]);
  const [balances, setBalances] = useState<BalanceInfo[]>([]);
  const [expandedContract, setExpandedContract] = useState<string | null>(null);
  const [createContractOpen, setCreateContractOpen] = useState(false);

  // Market state
  const [marketOrders, setMarketOrders] = useState<MarketOrder[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<OrderCategory | null>(null);
  const [orderTypeFilter, setOrderTypeFilter] = useState<OrderType | null>(null);
  const [sortBy, setSortBy] = useState<SortOption>("recent");
  const [searchQuery, setSearchQuery] = useState("");
  const [publishOpen, setPublishOpen] = useState(false);

  const [observingContractId, setObservingContractId] = useState<string | null>(null);

  useEffect(() => {
    void tradeClient.resolve().then(() => setArbiterReady(true));
  }, [tradeClient]);

  const fetchEntities = useCallback(async () => {
    try {
      setAllEntities(await listEntities());
    } catch { /* ignore */ }
  }, []);

  const fetchMyTrade = useCallback(async () => {
    const [, , entityList] = await Promise.allSettled([
      tradeClient.listContracts().then(setContracts).catch(() => {}),
      tradeClient.listPayments().then(setPayments).catch(() => {}),
      listEntities(),
    ]);
    if (entityList.status === "fulfilled") {
      const results: BalanceInfo[] = [];
      for (const entity of entityList.value) {
        try {
          results.push(await tradeClient.getBalance(entity.entity_uid));
        } catch { /* entity may not have balance */ }
      }
      setBalances(results.filter((b) => b.balance > 0 || b.frozen > 0));
    }
  }, [tradeClient]);

  const fetchMarketOrders = useCallback(async () => {
    try {
      setMarketOrders(await tradeClient.listOrders(undefined, "active"));
    } catch { /* ignore */ }
  }, [tradeClient]);

  const refresh = useCallback(async () => {
    if (!arbiterReady) return;
    setLoading(true);
    try {
      await fetchEntities();
      if (tab === "my-trade") await fetchMyTrade();
      else await fetchMarketOrders();
    } finally {
      setLoading(false);
    }
  }, [tab, arbiterReady, fetchEntities, fetchMyTrade, fetchMarketOrders]);

  useEffect(() => {
    const timer = window.setTimeout(() => void refresh(), 0);
    return () => window.clearTimeout(timer);
  }, [refresh]);

  const handleArchive = async (order: MarketOrder) => {
    try {
      await tradeClient.archiveOrder(order.order_id, order.publisher);
      await fetchMarketOrders();
    } catch { /* ignore */ }
  };

  if (observingContractId) {
    return (
      <ObserverView
        contractId={observingContractId}
        onBack={() => setObservingContractId(null)}
      />
    );
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <header className="px-4 md:px-6 h-14 flex items-center justify-between border-b border-border shrink-0">
        <div className="flex items-center gap-2">
          <div className="h-7 w-7 rounded-lg bg-muted flex items-center justify-center">
            <Handshake className="h-4 w-4 text-muted-foreground" />
          </div>
          <h1 className="font-heading text-sm font-semibold">Trade</h1>
        </div>
        <div className="flex items-center gap-2">
          {tab === "my-trade" && (
            <Button
              variant="outline"
              size="sm"
              className="h-8 text-xs"
              onClick={() => setCreateContractOpen(true)}
            >
              <Plus className="h-3.5 w-3.5 mr-1" />
              Contract
            </Button>
          )}
          {tab === "market" && (
            <Button
              variant="outline"
              size="sm"
              className="h-8 text-xs"
              onClick={() => setPublishOpen(true)}
            >
              <Plus className="h-3.5 w-3.5 mr-1" />
              Publish
            </Button>
          )}
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={refresh}
            disabled={loading}
          >
            <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
          </Button>
        </div>
      </header>

      {/* Tabs */}
      <div className="px-4 md:px-6 border-b border-border flex gap-1 pt-1">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={cn(
              "relative flex items-center gap-1.5 px-3 py-2 text-xs font-medium transition-colors",
              tab === t.id
                ? "text-foreground"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            <t.icon className="h-3.5 w-3.5" />
            {t.label}
            {tab === t.id && (
              <motion.div
                layoutId="trade-tab-indicator"
                className="absolute bottom-0 left-0 right-0 h-[2px] bg-primary rounded-t-full"
                transition={{ type: "spring", stiffness: 400, damping: 30 }}
              />
            )}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto">
        {loading && contracts.length === 0 && marketOrders.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <div className="p-4 md:p-6">
            <AnimatePresence mode="wait">
              {tab === "my-trade" && (
                <MyTradeTab
                  key="my-trade"
                  contracts={contracts}
                  payments={payments}
                  balances={balances}
                  entities={allEntities}
                  currentUserUid={currentUserUid}
                  expandedContract={expandedContract}
                  tradeClient={tradeClient}
                  onToggle={(id) =>
                    setExpandedContract(expandedContract === id ? null : id)
                  }
                  onAction={async () => {
                    await tradeClient.listContracts().then(setContracts).catch(() => {});
                  }}
                  onObserve={setObservingContractId}
                />
              )}
              {tab === "market" && (
                <MarketTab
                  key="market"
                  orders={marketOrders}
                  selectedCategory={selectedCategory}
                  onCategoryChange={setSelectedCategory}
                  orderTypeFilter={orderTypeFilter}
                  onOrderTypeChange={setOrderTypeFilter}
                  sortBy={sortBy}
                  onSortChange={setSortBy}
                  searchQuery={searchQuery}
                  onSearchChange={setSearchQuery}
                  currentUserUid={currentUserUid}
                  onArchive={handleArchive}
                />
              )}
            </AnimatePresence>
          </div>
        )}
      </div>

      {/* Dialogs */}
      <CreateContractDialog
        open={createContractOpen}
        onOpenChange={setCreateContractOpen}
        entities={allEntities}
        currentUserUid={currentUserUid}
        tradeClient={tradeClient}
        onCreated={() => {
          setTab("my-trade");
          tradeClient.listContracts().then(setContracts).catch(() => {});
        }}
      />
      <PublishOrderDialog
        open={publishOpen}
        onOpenChange={setPublishOpen}
        entities={allEntities}
        currentUserUid={currentUserUid}
        tradeClient={tradeClient}
        defaultCategory={selectedCategory ?? undefined}
        onPublished={() => void fetchMarketOrders()}
      />
    </div>
  );
}

/* ──────────── Helpers ──────────── */

function resolvePartyName(contract: Contract, role: "party_a" | "party_b", entities: Contact[]): string {
  const snapshot = contract.participant_snapshots?.find((p) => p.role === role);
  if (snapshot?.display_name) return snapshot.display_name;
  const ref = role === "party_a" ? contract.party_a : contract.party_b;
  const uid = ref.entity_uid ?? ref.address?.split(":").pop() ?? "";
  const entity = entities.find((e) => e.entity_uid === uid);
  if (entity) return entity.name;
  return uid.slice(0, 8) || "?";
}

function formatCardTime(ts: number | null | undefined): string {
  if (!ts) return "";
  return new Date(ts * 1000).toLocaleString(undefined, {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

function applyMarketFilters(
  orders: MarketOrder[],
  category: OrderCategory | null,
  orderType: OrderType | null,
  search: string,
  sort: SortOption,
): MarketOrder[] {
  let filtered = orders;
  if (category) filtered = filtered.filter((o) => o.category === category);
  if (orderType) filtered = filtered.filter((o) => o.order_type === orderType);
  if (search.trim()) {
    const q = search.toLowerCase();
    filtered = filtered.filter(
      (o) => o.title.toLowerCase().includes(q) || o.description.toLowerCase().includes(q),
    );
  }
  return [...filtered].sort((a, b) => {
    if (sort === "budget-high") return (b.budget ?? 0) - (a.budget ?? 0);
    if (sort === "budget-low") return (a.budget ?? 0) - (b.budget ?? 0);
    return b.created_at - a.created_at;
  });
}

/* ──────────── My Trade Tab ──────────── */

function MyTradeTab({
  contracts,
  payments,
  balances,
  entities,
  currentUserUid,
  expandedContract,
  tradeClient,
  onToggle,
  onAction,
  onObserve,
}: {
  contracts: Contract[];
  payments: Payment[];
  balances: BalanceInfo[];
  entities: Contact[];
  currentUserUid: string;
  expandedContract: string | null;
  tradeClient: TradeApiClient;
  onToggle: (id: string) => void;
  onAction: () => void;
  onObserve: (contractId: string) => void;
}) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="space-y-6"
    >
      {balances.length > 0 && (
        <Section icon={Banknote} title="Ledger Balances">
          <div className="grid gap-3 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
            {balances.map((b, i) => (
              <motion.div
                key={b.entity_uid}
                custom={i}
                variants={cardVariants}
                initial="hidden"
                animate="show"
              >
                <SpotlightCard className="p-4">
                  <p className="text-sm font-medium">{b.entity_name}</p>
                  <div className="flex items-baseline gap-2 mt-1">
                    <span className="text-lg font-semibold tabular-nums">
                      {b.available}
                    </span>
                    <span className="text-xs text-muted-foreground/50">
                      available
                    </span>
                  </div>
                  {b.frozen > 0 && (
                    <p className="text-xs text-orange-500/70 mt-0.5">
                      {b.frozen} frozen
                    </p>
                  )}
                </SpotlightCard>
              </motion.div>
            ))}
          </div>
        </Section>
      )}

      <Section icon={FileText} title="Contracts">
        {contracts.length === 0 ? (
          <EmptyState icon={FileText} text="No contracts yet" />
        ) : (
          <div className="flex flex-col gap-3">
            {contracts.map((contract, i) => (
              <motion.div
                key={contract.contract_id}
                custom={i}
                variants={cardVariants}
                initial="hidden"
                animate="show"
              >
                <SpotlightCard className="p-4">
                  <div className="flex items-center gap-3">
                    <button
                      onClick={() => onToggle(contract.contract_id)}
                      className="flex-1 min-w-0 text-left"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <p className="text-sm font-medium truncate">
                              {contract.title}
                            </p>
                            <StatusBadge status={contract.status} />
                          </div>
                          <div className="flex items-center gap-3 mt-1.5 text-xs text-muted-foreground/60">
                            <span className="truncate">
                              {resolvePartyName(contract, "party_a", entities)} → {resolvePartyName(contract, "party_b", entities)}
                            </span>
                            <span className="shrink-0">{formatCardTime(contract.created_at)}</span>
                          </div>
                        </div>
                        <div className="text-right shrink-0">
                          <p className="text-sm font-semibold tabular-nums">
                            {contract.amount}
                          </p>
                          <p className="text-[10px] text-muted-foreground/50 uppercase">
                            {contract.funding_mode}
                          </p>
                        </div>
                      </div>
                    </button>
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-7 text-xs px-3 shrink-0"
                      onClick={() => onObserve(contract.contract_id)}
                    >
                      <Eye className="h-3 w-3 mr-1" />
                      Observer
                    </Button>
                  </div>
                  <AnimatePresence>
                    {expandedContract === contract.contract_id && (
                      <ContractDetail
                        contract={contract}
                        currentUserUid={currentUserUid}
                        tradeClient={tradeClient}
                        onAction={onAction}
                        onObserve={() => onObserve(contract.contract_id)}
                      />
                    )}
                  </AnimatePresence>
                </SpotlightCard>
              </motion.div>
            ))}
          </div>
        )}
      </Section>

      <Section icon={Wallet} title="Payment Records">
        {payments.length === 0 ? (
          <EmptyState icon={Wallet} text="No payments yet" />
        ) : (
          <div className="flex flex-col gap-2">
            {payments.map((payment, i) => (
              <motion.div
                key={payment.payment_id}
                custom={i}
                variants={cardVariants}
                initial="hidden"
                animate="show"
              >
                <SpotlightCard className="p-3 flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="text-xs font-medium">
                        {payment.payment_id}
                      </p>
                      <Badge
                        variant="secondary"
                        className={cn(
                          "text-[10px] h-4 px-1.5 border-0",
                          PAY_STATUS_COLORS[payment.status],
                        )}
                      >
                        {payment.status.toUpperCase()}
                      </Badge>
                    </div>
                    <p className="text-[11px] text-muted-foreground/60 mt-0.5">
                      {payment.payer.entity_uid?.slice(0, 8)} →{" "}
                      {payment.payee.entity_uid?.slice(0, 8)} |{" "}
                      {payment.method}
                    </p>
                  </div>
                  <p className="text-sm font-semibold tabular-nums shrink-0">
                    {payment.amount}
                  </p>
                </SpotlightCard>
              </motion.div>
            ))}
          </div>
        )}
      </Section>
    </motion.div>
  );
}

/* ──────────── Market Tab ──────────── */

function MarketTab({
  orders,
  selectedCategory,
  onCategoryChange,
  orderTypeFilter,
  onOrderTypeChange,
  sortBy,
  onSortChange,
  searchQuery,
  onSearchChange,
  currentUserUid,
  onArchive,
}: {
  orders: MarketOrder[];
  selectedCategory: OrderCategory | null;
  onCategoryChange: (cat: OrderCategory | null) => void;
  orderTypeFilter: OrderType | null;
  onOrderTypeChange: (type: OrderType | null) => void;
  sortBy: SortOption;
  onSortChange: (sort: SortOption) => void;
  searchQuery: string;
  onSearchChange: (q: string) => void;
  currentUserUid: string;
  onArchive: (order: MarketOrder) => void;
}) {
  const filtered = applyMarketFilters(orders, selectedCategory, orderTypeFilter, searchQuery, sortBy);
  const hideOrderType = selectedCategory === "matchmaking";

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
    >
      <div className="flex gap-6">
        {/* Sidebar — desktop */}
        <nav className="hidden md:flex flex-col w-36 shrink-0 space-y-1">
          <SidebarButton
            active={!selectedCategory}
            icon={LayoutGrid}
            label="All"
            onClick={() => onCategoryChange(null)}
          />
          {CATEGORIES.map((cat) => (
            <SidebarButton
              key={cat.id}
              active={selectedCategory === cat.id}
              icon={cat.icon}
              label={cat.label}
              onClick={() => onCategoryChange(selectedCategory === cat.id ? null : cat.id)}
            />
          ))}
        </nav>

        {/* Main content */}
        <div className="flex-1 min-w-0 space-y-4">
          {/* Mobile category chips */}
          <div className="md:hidden flex gap-1.5 flex-wrap">
            <ChipButton active={!selectedCategory} label="All" onClick={() => onCategoryChange(null)} />
            {CATEGORIES.map((cat) => (
              <ChipButton
                key={cat.id}
                active={selectedCategory === cat.id}
                label={cat.label}
                onClick={() => onCategoryChange(selectedCategory === cat.id ? null : cat.id)}
              />
            ))}
          </div>

          {/* Filter bar */}
          <div className="flex items-center gap-2 flex-wrap">
            {!hideOrderType && (
              <div className="flex gap-1">
                {([null, "demand", "supply"] as const).map((t) => (
                  <ChipButton
                    key={t ?? "all"}
                    active={orderTypeFilter === t}
                    label={t ? t.charAt(0).toUpperCase() + t.slice(1) : "All Types"}
                    onClick={() => onOrderTypeChange(t)}
                  />
                ))}
              </div>
            )}
            <select
              className="h-7 rounded-md border border-input bg-background px-2 text-xs text-muted-foreground"
              value={sortBy}
              onChange={(e) => onSortChange(e.target.value as SortOption)}
            >
              <option value="recent">Recent</option>
              <option value="budget-high">Budget ↓</option>
              <option value="budget-low">Budget ↑</option>
            </select>
            <div className="relative flex-1 min-w-[120px] max-w-[240px]">
              <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3 w-3 text-muted-foreground/50" />
              <Input
                className="h-7 pl-7 text-xs"
                placeholder="Search..."
                value={searchQuery}
                onChange={(e) => onSearchChange(e.target.value)}
              />
            </div>
          </div>

          {/* Order cards */}
          {filtered.length === 0 ? (
            <EmptyState icon={Store} text="No orders yet" />
          ) : (
            <OrderCardGrid
              orders={filtered}
              currentUserUid={currentUserUid}
              onArchive={onArchive}
              showCategory={!selectedCategory}
            />
          )}
        </div>
      </div>
    </motion.div>
  );
}

/* ──────────── Order Card Grid ──────────── */

function OrderCardGrid({
  orders,
  currentUserUid,
  onArchive,
  showCategory = false,
}: {
  orders: MarketOrder[];
  currentUserUid: string;
  onArchive: (order: MarketOrder) => void;
  showCategory?: boolean;
}) {
  return (
    <div className="grid gap-3 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
      {orders.map((order, i) => (
        <motion.div
          key={order.order_id}
          custom={i}
          variants={cardVariants}
          initial="hidden"
          animate="show"
          whileHover={{ y: -2, transition: { duration: 0.2 } }}
        >
          <SpotlightCard className="p-4">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <Megaphone className="h-3.5 w-3.5 text-muted-foreground/50 shrink-0" />
                  <p className="text-sm font-medium truncate">{order.title}</p>
                </div>
                {order.description && (
                  <p className="text-xs text-muted-foreground/70 mt-1.5 leading-relaxed line-clamp-3">
                    {order.description}
                  </p>
                )}
              </div>
              <div className="flex items-center gap-1.5 shrink-0">
                {showCategory && order.category && (
                  <Badge
                    variant="secondary"
                    className={cn(
                      "text-[10px] h-5 px-1.5 border-0 capitalize",
                      CATEGORY_COLORS[order.category],
                    )}
                  >
                    {order.category}
                  </Badge>
                )}
                {order.budget != null && (
                  <Badge
                    variant="secondary"
                    className="text-[10px] h-5 px-1.5 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-0"
                  >
                    {order.budget}
                  </Badge>
                )}
              </div>
            </div>
            <div className="flex items-center justify-between mt-3 pt-2 border-t border-border/50">
              <div className="flex items-center gap-1.5">
                <span className="text-[10px] text-muted-foreground/50">
                  {order.publisher.slice(0, 8)}
                </span>
                {order.tags.length > 0 && (
                  <div className="flex gap-1">
                    {order.tags.slice(0, 3).map((tag) => (
                      <Badge
                        key={tag}
                        variant="secondary"
                        className="text-[9px] h-3.5 px-1 bg-surface border-0"
                      >
                        {tag}
                      </Badge>
                    ))}
                  </div>
                )}
              </div>
              {order.publisher === currentUserUid && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 text-[10px] text-muted-foreground hover:text-foreground px-1.5"
                  onClick={() => onArchive(order)}
                >
                  <Archive className="h-3 w-3 mr-0.5" />
                  Archive
                </Button>
              )}
            </div>
          </SpotlightCard>
        </motion.div>
      ))}
    </div>
  );
}

/* ──────────── Shared UI ──────────── */

function SidebarButton({
  active,
  icon: Icon,
  label,
  onClick,
}: {
  active: boolean;
  icon: typeof Wallet;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-colors text-left",
        active
          ? "bg-foreground text-background"
          : "text-muted-foreground hover:bg-muted hover:text-foreground",
      )}
    >
      <Icon className="h-3.5 w-3.5" />
      {label}
    </button>
  );
}

function ChipButton({
  active,
  label,
  onClick,
}: {
  active: boolean;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "px-2.5 py-1 rounded-full text-xs font-medium transition-colors",
        active
          ? "bg-foreground text-background"
          : "bg-muted text-muted-foreground hover:text-foreground",
      )}
    >
      {label}
    </button>
  );
}

function Section({
  icon: Icon,
  title,
  children,
}: {
  icon: typeof Wallet;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <h3 className="text-xs font-medium text-muted-foreground mb-3 flex items-center gap-1.5">
        <Icon className="h-3.5 w-3.5" />
        {title}
      </h3>
      {children}
    </div>
  );
}

function EmptyState({
  icon: Icon,
  text,
}: {
  icon: typeof Wallet;
  text: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <motion.div
        initial={{ scale: 0.8, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 0.4 }}
      >
        <div className="h-16 w-16 rounded-2xl bg-muted border border-border flex items-center justify-center mb-3">
          <Icon className="h-8 w-8 text-muted-foreground/20" />
        </div>
      </motion.div>
      <p className="text-sm text-muted-foreground/50">{text}</p>
    </div>
  );
}

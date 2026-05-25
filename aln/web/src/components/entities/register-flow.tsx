/* Entity registration flow — step wizard: kind → provider → configure. */

import { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  UserPlus,
  Loader2,
  Bot,
  User,
  Users,
  Wrench,
  ChevronDown,
  ChevronUp,
  ChevronLeft,
  ChevronRight,
  CheckCircle2,
  XCircle,
  FolderOpen,
  Folder,
  Plus,
  Trash2,
  Settings2,
  Upload,
} from "lucide-react";

import { cn, EASE_SMOOTH } from "@/lib/utils";
import { apiClient, checkProvider, getProviderCheckErrorMessage, listDirs } from "@/api";
import { registerBatch } from "@/api/entity";
import type { ProviderCheckResult } from "@/api";
import { useAppStore } from "@/stores/app";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { EntityKind, StandardResponse, Contact } from "@/types";

/* --- Constants --- */

const ENTITY_KINDS: {
  value: EntityKind;
  label: string;
  description: string;
  icon: typeof Bot;
  disabled?: boolean;
}[] = [
  {
    value: "agent",
    label: "Agent",
    description: "AI agent with autonomous processing",
    icon: Bot,
  },
  {
    value: "organization",
    label: "Organization",
    description: "Group of entities working together",
    icon: Users,
  },
  {
    value: "human",
    label: "Human",
    description: "Human participant in the network",
    icon: User,
    disabled: true,
  },
  {
    value: "tool",
    label: "Tool",
    description: "MCP-based tool or service",
    icon: Wrench,
    disabled: true,
  },
];

const PROVIDERS = [
  { value: "autowork", label: "Autowork", description: "Autowork agent", logo: "/logos/foundationagents.png" },
  { value: "claude", label: "Claude Code", description: "Anthropic Claude CLI", logo: "/logos/anthropic.com.png" },
  { value: "codex", label: "Codex", description: "OpenAI Codex CLI", logo: "/logos/openai.com.png" },
  { value: "openclaw", label: "OpenClaw", description: "OpenClaw agent", logo: "/logos/openclaw.png" },
  { value: "hermes", label: "HermesAgent", description: "Nous Research Hermes agent", logo: "/logos/nousresearch.png" },
];

const TRUST_LEVELS = [
  { value: "untrusted", label: "Untrusted", description: "Read-only access" },
  { value: "semi_trusted", label: "Semi-trusted", description: "Auto-approve safe operations" },
  { value: "fully_trusted", label: "Fully-trusted", description: "Bypass all approvals" },
];

const TOTAL_STEPS = 3;

/* --- Organization Templates --- */

interface OrgMember {
  name: string;
  kind: string;
  provider: string;
  description: string;
  is_public: boolean;
  trust_level: string;
  model: string;
  workdir: string;
}

interface OrgTemplate {
  id: string;
  name: string;
  description: string;
  members: OrgMember[];
}

const ORG_TEMPLATES: OrgTemplate[] = [
  {
    id: "dev-team",
    name: "Dev Team",
    description: "A full-stack development team",
    members: [
      { name: "PM", kind: "agent", provider: "claude", description: "Manages project scope, timelines, and cross-team coordination. Breaks down requirements into actionable tasks and tracks progress across all members.", is_public: true, trust_level: "fully_trusted", model: "", workdir: "" },
      { name: "Architect", kind: "agent", provider: "claude", description: "Designs system architecture, defines API contracts, and ensures technical consistency. Reviews major design decisions and maintains architecture documentation.", is_public: true, trust_level: "fully_trusted", model: "", workdir: "" },
      { name: "Frontend", kind: "agent", provider: "claude", description: "Builds user interfaces with React/TypeScript, implements responsive layouts, handles client-side state management, and ensures accessibility compliance.", is_public: true, trust_level: "fully_trusted", model: "", workdir: "" },
      { name: "Backend", kind: "agent", provider: "claude", description: "Develops REST/GraphQL APIs, implements business logic, manages database schemas and migrations, and handles authentication and authorization flows.", is_public: true, trust_level: "fully_trusted", model: "", workdir: "" },
      { name: "QA", kind: "agent", provider: "claude", description: "Writes unit, integration, and end-to-end tests. Performs code review for edge cases, validates acceptance criteria, and maintains test coverage standards.", is_public: true, trust_level: "fully_trusted", model: "", workdir: "" },
      { name: "DevOps", kind: "agent", provider: "claude", description: "Manages CI/CD pipelines, container orchestration, and infrastructure as code. Monitors system health, handles deployments, and optimizes build performance.", is_public: true, trust_level: "fully_trusted", model: "", workdir: "" },
    ],
  },
  {
    id: "custom",
    name: "Custom",
    description: "Start from scratch",
    members: [],
  },
];

/* --- Animation --- */

const containerVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.08, delayChildren: 0.1 },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 12 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.35, ease: EASE_SMOOTH },
  },
};

const stepTransition = {
  initial: { opacity: 0, x: 30 },
  animate: { opacity: 1, x: 0 },
  exit: { opacity: 0, x: -30 },
  transition: { duration: 0.15, ease: EASE_SMOOTH },
};

/* --- Folder Picker --- */

function FolderPicker({
  open,
  onOpenChange,
  onSelect,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onSelect: (path: string) => void;
}) {
  const [currentPath, setCurrentPath] = useState("~");
  const [dirs, setDirs] = useState<string[]>([]);
  const [parentPath, setParentPath] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async (path: string) => {
    setLoading(true);
    try {
      const result = await listDirs(path);
      setCurrentPath(result.current);
      setParentPath(result.parent);
      setDirs(result.dirs);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) load("~");
  }, [open, load]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="text-sm">Select Folder</DialogTitle>
        </DialogHeader>
        <div className="flex items-center gap-1.5 px-1 py-1 rounded-lg bg-muted/50 overflow-x-auto">
          <Folder className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
          <span className="text-xs font-mono text-muted-foreground truncate">
            {currentPath}
          </span>
        </div>
        <div className="max-h-64 overflow-y-auto rounded-lg border border-border">
          {parentPath && (
            <button
              onClick={() => load(parentPath)}
              className="flex items-center gap-2 w-full px-3 py-2 text-sm text-muted-foreground hover:bg-surface-hover transition-colors border-b border-border"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
              ..
            </button>
          )}
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
            </div>
          ) : dirs.length === 0 ? (
            <div className="py-8 text-center text-xs text-muted-foreground/50">
              No subdirectories
            </div>
          ) : (
            dirs.map((dir) => (
              <button
                key={dir}
                onClick={() => load(`${currentPath}/${dir}`)}
                className="flex items-center gap-2 w-full px-3 py-2 text-sm hover:bg-surface-hover transition-colors"
              >
                <Folder className="h-3.5 w-3.5 text-muted-foreground/60 shrink-0" />
                <span className="truncate">{dir}</span>
                <ChevronRight className="h-3.5 w-3.5 text-muted-foreground/30 ml-auto shrink-0" />
              </button>
            ))
          )}
        </div>
        <Button
          onClick={() => {
            onSelect(currentPath);
            onOpenChange(false);
          }}
          className="w-full"
        >
          Select This Folder
        </Button>
      </DialogContent>
    </Dialog>
  );
}

/* --- Register Flow Component --- */

interface RegisterFlowProps {
  onCreated: () => void;
  onCancel?: () => void;
  showBackOnStep1?: boolean;
}

export function RegisterFlow({ onCreated, onCancel, showBackOnStep1 }: RegisterFlowProps) {
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [name, setName] = useState("");
  const [kind, setKind] = useState<EntityKind>("agent");
  const [description, setDescription] = useState("");
  const [provider, setProvider] = useState("claude");
  const [trustLevel, setTrustLevel] = useState("fully_trusted");
  const [model, setModel] = useState("");
  const [workdir, setWorkdir] = useState("");
  const [isPublic, setIsPublic] = useState(true);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [providerStatus, setProviderStatus] = useState<ProviderCheckResult | null>(null);
  const [checkingProvider, setCheckingProvider] = useState(false);
  const [folderPickerOpen, setFolderPickerOpen] = useState(false);
  const [folderPickerTarget, setFolderPickerTarget] = useState<"agent" | "org" | number>("agent");

  // Organization state
  const [orgName, setOrgName] = useState("");
  const [orgMembers, setOrgMembers] = useState<OrgMember[]>([]);
  const [expandedMember, setExpandedMember] = useState<number | null>(null);
  const [orgSettingsOpen, setOrgSettingsOpen] = useState(false);
  const [orgProvider, setOrgProvider] = useState("claude");
  const [orgTrustLevel, setOrgTrustLevel] = useState("fully_trusted");
  const [orgModel, setOrgModel] = useState("");
  const [orgWorkdir, setOrgWorkdir] = useState("");
  const importInputRef = useRef<HTMLInputElement>(null);

  const runProviderCheck = useCallback(async (p: string) => {
    setCheckingProvider(true);
    setProviderStatus(null);
    try {
      const result = await checkProvider(p);
      setProviderStatus(result);
    } catch (error) {
      setProviderStatus({
        available: false,
        provider: p,
        version: null,
        executable_path: null,
        error: getProviderCheckErrorMessage(error),
      });
    } finally {
      setCheckingProvider(false);
    }
  }, []);

  useEffect(() => {
    if (step === 2 && kind === "agent") {
      runProviderCheck(provider);
    }
  }, [provider, kind, step, runProviderCheck]);

  function handleSelectKind(value: EntityKind) {
    setKind(value);
    if (value === "organization") {
      setStep(2);
    } else {
      setStep(value === "agent" ? 2 : 3);
    }
  }

  function handleBack() {
    if (step === 1 && onCancel) {
      onCancel();
    } else if (step === 3) {
      setStep(kind === "agent" || kind === "organization" ? 2 : 1);
    } else if (step === 2) {
      setStep(1);
    }
    setError(null);
  }

  async function handleRegister() {
    if (!name.trim()) return;
    setLoading(true);
    setError(null);

    try {
      const isAgent = kind === "agent";
      const payload: Record<string, unknown> = {
        name: name.trim(),
        kind,
        description: description.trim() || undefined,
        is_public: isPublic,
        provider: isAgent ? provider : undefined,
        trust_level: isAgent ? trustLevel : undefined,
        model: isAgent && model.trim() ? model.trim() : undefined,
        workdir: isAgent && workdir.trim() ? workdir.trim() : undefined,
        timeout: isAgent ? 300.0 : undefined,
        interaction_mode: isAgent ? "batch" : undefined,
        stream_output: isAgent ? false : undefined,
        output_format: isAgent ? "json" : undefined,
      };

      const { data } = await apiClient.post<StandardResponse<Contact>>(
        "/entities",
        payload,
      );

      if (data.data) {
        await useAppStore.getState().loadContacts();
        onCreated();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setLoading(false);
    }
  }

  const kindMeta = ENTITY_KINDS.find((ek) => ek.value === kind)!;
  const showBack = step > 1 || (step === 1 && showBackOnStep1);

  function handleSelectTemplate(template: OrgTemplate) {
    setOrgMembers(template.members.map((m) => ({ ...m })));
    if (template.id !== "custom") setOrgName(template.name);
    setStep(3);
  }

  function handleUpdateMember(index: number, field: keyof OrgMember, value: string | boolean) {
    setOrgMembers((prev) => prev.map((m, i) => (i === index ? { ...m, [field]: value } : m)));
  }

  function handleAddMember() {
    setOrgMembers((prev) => [
      ...prev,
      { name: "", kind: "agent", provider: orgProvider, description: "", is_public: true, trust_level: "fully_trusted", model: "", workdir: "" },
    ]);
  }

  function handleRemoveMember(index: number) {
    setOrgMembers((prev) => prev.filter((_, i) => i !== index));
  }

  async function handleCreateOrganization() {
    if (!orgName.trim() || orgMembers.length === 0) return;
    setLoading(true);
    setError(null);
    try {
      await registerBatch({
        organization_name: orgName.trim(),
        members: orgMembers.map((m) => ({
          name: m.name.trim(),
          kind: m.kind,
          provider: m.provider || undefined,
          description: m.description.trim() || undefined,
          is_public: m.is_public,
          trust_level: m.trust_level || undefined,
          model: m.model.trim() || undefined,
          workdir: m.workdir.trim() || undefined,
        })),
        auto_friend: true,
      });
      await useAppStore.getState().loadContacts();
      onCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create organization");
    } finally {
      setLoading(false);
    }
  }

  function handleExportOrg() {
    const payload = {
      organization_name: orgName.trim(),
      members: orgMembers.map(({ name, kind, provider, description, is_public, trust_level, model, workdir }) => ({
        name, kind, provider, description, is_public, trust_level, model, workdir,
      })),
      auto_friend: true,
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${orgName.trim() || "organization"}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  function handleImportOrg(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const data = JSON.parse(reader.result as string);
        if (data.organization_name) setOrgName(data.organization_name);
        if (Array.isArray(data.members)) {
          setOrgMembers(data.members.map((m: Record<string, unknown>) => ({
            name: String(m.name ?? ""),
            kind: String(m.kind ?? "agent"),
            provider: String(m.provider ?? "claude"),
            description: String(m.description ?? ""),
            is_public: m.is_public !== false,
            trust_level: String(m.trust_level ?? "fully_trusted"),
            model: String(m.model ?? ""),
            workdir: String(m.workdir ?? ""),
          })));
        }
        setStep(3);
      } catch {
        setError("Invalid JSON file");
      }
    };
    reader.readAsText(file);
    e.target.value = "";
  }

  function handleApplyOrgProvider(prov: string) {
    setOrgProvider(prov);
    setOrgMembers((prev) => prev.map((m) => ({ ...m, provider: prov })));
  }

  function handleApplyOrgField(field: keyof OrgMember, value: string) {
    if (field === "provider") return handleApplyOrgProvider(value);
    if (field === "trust_level") setOrgTrustLevel(value);
    else if (field === "model") setOrgModel(value);
    else if (field === "workdir") setOrgWorkdir(value);
    setOrgMembers((prev) => prev.map((m) => ({ ...m, [field]: value })));
  }

  return (
    <div className="h-full flex flex-col">
      <header className="px-4 md:px-6 h-14 flex items-center border-b border-border shrink-0">
        {showBack && (
          <button
            onClick={handleBack}
            className="mr-2 p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-surface-hover transition-colors"
          >
            <ChevronLeft className="h-5 w-5" />
          </button>
        )}
        <div className="h-7 w-7 rounded-lg bg-muted flex items-center justify-center mr-2">
          <UserPlus className="h-4 w-4 text-muted-foreground" />
        </div>
        <h1 className="font-heading text-sm font-semibold">
          {step === 1 ? "Register Entity" : kind === "organization" ? "New Organization" : `New ${kindMeta.label}`}
        </h1>
      </header>

      {/* Step progress bar */}
      <div className="px-4 md:px-6 py-3 shrink-0">
        <div className="max-w-md mx-auto flex items-center gap-3">
          {Array.from({ length: TOTAL_STEPS }, (_, i) => (
            <div
              key={i}
              className={cn(
                "h-1 flex-1 rounded-full transition-colors duration-200",
                step >= i + 1 ? "bg-primary" : "bg-muted",
              )}
            />
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-auto p-4 md:p-6">
        <AnimatePresence mode="wait">
          {step === 1 && (
            <motion.div key="step-kind" {...stepTransition} className="max-w-md mx-auto">
              <p className="text-sm text-muted-foreground mb-5">
                Choose the type of entity to register
              </p>
              <div className="grid gap-3">
                {ENTITY_KINDS.map((ek) => (
                  <motion.button
                    key={ek.value}
                    whileHover={ek.disabled ? undefined : { scale: 1.01 }}
                    whileTap={ek.disabled ? undefined : { scale: 0.98 }}
                    onClick={() => !ek.disabled && handleSelectKind(ek.value)}
                    disabled={ek.disabled}
                    className={cn(
                      "flex items-center gap-4 px-5 py-4 rounded-xl border text-left transition-all duration-200",
                      ek.disabled
                        ? "border-border bg-surface opacity-40 cursor-not-allowed"
                        : "border-border bg-surface hover:border-primary/30 hover:bg-primary/5",
                    )}
                  >
                    <div className="h-10 w-10 rounded-lg bg-surface-hover flex items-center justify-center shrink-0">
                      <ek.icon className="h-5 w-5 text-muted-foreground" />
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium">{ek.label}</span>
                        {ek.disabled && (
                          <span className="text-[10px] text-muted-foreground/40 font-mono">
                            coming soon
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-muted-foreground/60 mt-0.5">
                        {ek.description}
                      </p>
                    </div>
                  </motion.button>
                ))}
              </div>
            </motion.div>
          )}

          {step === 2 && kind === "organization" && (
            <motion.div key="step-org-template" {...stepTransition} className="max-w-md mx-auto space-y-5">
              <p className="text-sm text-muted-foreground">
                Choose a template to get started
              </p>
              <div className="grid gap-3">
                {ORG_TEMPLATES.map((tpl) => (
                  <motion.button
                    key={tpl.id}
                    whileHover={{ scale: 1.01 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => handleSelectTemplate(tpl)}
                    className="flex items-center gap-4 px-5 py-4 rounded-xl border border-border bg-surface hover:border-primary/30 hover:bg-primary/5 text-left transition-all duration-200"
                  >
                    <div className="h-10 w-10 rounded-lg bg-surface-hover flex items-center justify-center shrink-0">
                      {tpl.id === "custom" ? (
                        <Plus className="h-5 w-5 text-muted-foreground" />
                      ) : (
                        <Users className="h-5 w-5 text-muted-foreground" />
                      )}
                    </div>
                    <div className="flex-1">
                      <span className="text-sm font-medium">{tpl.name}</span>
                      <p className="text-xs text-muted-foreground/60 mt-0.5">{tpl.description}</p>
                    </div>
                  </motion.button>
                ))}
                <motion.button
                  whileHover={{ scale: 1.01 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={() => importInputRef.current?.click()}
                  className="flex items-center gap-4 px-5 py-4 rounded-xl border border-dashed border-border bg-surface hover:border-primary/30 hover:bg-primary/5 text-left transition-all duration-200"
                >
                  <div className="h-10 w-10 rounded-lg bg-surface-hover flex items-center justify-center shrink-0">
                    <Upload className="h-5 w-5 text-muted-foreground" />
                  </div>
                  <div className="flex-1">
                    <span className="text-sm font-medium">Import JSON</span>
                    <p className="text-xs text-muted-foreground/60 mt-0.5">Load from exported file</p>
                  </div>
                </motion.button>
              </div>
              <input
                ref={importInputRef}
                type="file"
                accept=".json"
                className="hidden"
                onChange={handleImportOrg}
              />
            </motion.div>
          )}

          {step === 2 && kind !== "organization" && (
            <motion.div key="step-provider" {...stepTransition} className="max-w-md mx-auto space-y-5">
              <p className="text-sm text-muted-foreground">
                Select a provider for your agent
              </p>
              <div className="grid gap-1.5">
                {PROVIDERS.map((p) => {
                  const selected = provider === p.value;
                  return (
                    <button
                      key={p.value}
                      onClick={() => setProvider(p.value)}
                      className={cn(
                        "flex items-center gap-3 px-3 py-2.5 rounded-xl border text-left transition-all duration-200",
                        selected
                          ? "border-accent/30 bg-accent/5"
                          : "border-border bg-surface hover:border-muted-foreground/20",
                      )}
                    >
                      <div
                        className={cn(
                          "h-7 w-7 rounded-md flex items-center justify-center shrink-0 overflow-hidden",
                          selected ? "bg-accent/10" : "bg-surface-hover",
                        )}
                      >
                        {p.logo ? (
                          <img src={p.logo} alt={p.label} className="h-5 w-5 object-contain logo-adapt" />
                        ) : (
                          <span className={cn(
                            "text-[10px] font-mono font-bold",
                            selected ? "text-accent" : "text-muted-foreground/60",
                          )}>{p.label.slice(0, 2).toUpperCase()}</span>
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <span className="text-sm font-medium">{p.label}</span>
                        <p className="text-[11px] text-muted-foreground/50">
                          {p.description}
                        </p>
                      </div>
                      {selected && (
                        <div className="shrink-0">
                          {checkingProvider ? (
                            <Loader2 className="h-4 w-4 animate-spin text-muted-foreground/40" />
                          ) : providerStatus?.available ? (
                            <CheckCircle2 className="h-4 w-4 text-success" />
                          ) : providerStatus ? (
                            <XCircle className="h-4 w-4 text-destructive" />
                          ) : null}
                        </div>
                      )}
                    </button>
                  );
                })}
              </div>
              {providerStatus && !checkingProvider && (
                <motion.div
                  initial={{ opacity: 0, y: -4 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={cn(
                    "px-3 py-2 rounded-lg text-xs",
                    providerStatus.available
                      ? "bg-success/5 border border-success/10 text-success"
                      : "bg-destructive/5 border border-destructive/10 text-destructive",
                  )}
                >
                  {providerStatus.available ? (
                    <span className="font-mono">{providerStatus.version}</span>
                  ) : (
                    <span>{providerStatus.error}</span>
                  )}
                </motion.div>
              )}
              <Button
                onClick={() => setStep(3)}
                disabled={kind === "agent" && providerStatus?.available === false}
                className="w-full bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
              >
                Continue
              </Button>
            </motion.div>
          )}

          {step === 3 && kind === "organization" && (
            <motion.div key="step-org-edit" {...stepTransition}>
              <motion.div
                variants={containerVariants}
                initial="hidden"
                animate="show"
                className="max-w-md mx-auto space-y-4"
              >
                {/* Root node — org name, click to open settings */}
                <motion.div variants={itemVariants} className="flex flex-col items-center">
                  <button
                    onClick={() => setOrgSettingsOpen(!orgSettingsOpen)}
                    className={cn(
                      "rounded-xl border-2 px-5 py-3 flex items-center gap-3 transition-all",
                      orgSettingsOpen
                        ? "border-primary bg-primary/10"
                        : "border-primary/30 bg-primary/5 hover:border-primary/50",
                    )}
                  >
                    <Users className="h-4.5 w-4.5 text-primary shrink-0" />
                    <input
                      value={orgName}
                      onChange={(e) => setOrgName(e.target.value)}
                      onClick={(e) => e.stopPropagation()}
                      placeholder="Organization Name"
                      className="bg-transparent text-sm font-semibold outline-none placeholder:text-muted-foreground/40 w-40 text-center"
                    />
                    <Settings2 className={cn(
                      "h-3.5 w-3.5 transition-colors",
                      orgSettingsOpen ? "text-primary" : "text-primary/30",
                    )} />
                  </button>
                  {orgSettingsOpen && (
                    <motion.div
                      initial={{ opacity: 0, y: -4 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="mt-2 w-80 rounded-xl border border-border bg-surface p-3 space-y-3 shadow-sm z-20 relative"
                    >
                      <p className="text-[10px] text-muted-foreground/50">Changes apply to all members</p>
                      <div className="space-y-1">
                        <label className="text-[10px] font-medium text-muted-foreground/60">Organization Name</label>
                        <Input
                          value={orgName}
                          onChange={(e: React.ChangeEvent<HTMLInputElement>) => setOrgName(e.target.value)}
                          placeholder="My Team"
                          className="bg-muted/30 border-border focus:border-primary/25 text-sm h-8"
                        />
                      </div>
                      <div className="grid grid-cols-2 gap-2">
                        <div className="space-y-1">
                          <label className="text-[10px] font-medium text-muted-foreground/60">Provider</label>
                          <select
                            value={orgProvider}
                            onChange={(e) => handleApplyOrgProvider(e.target.value)}
                            className="w-full h-8 rounded-lg border border-border bg-muted/30 px-2 text-sm outline-none focus:border-primary/25"
                          >
                            {PROVIDERS.map((p) => (
                              <option key={p.value} value={p.value}>{p.label}</option>
                            ))}
                          </select>
                        </div>
                        <div className="space-y-1">
                          <label className="text-[10px] font-medium text-muted-foreground/60">Trust Level</label>
                          <select
                            value={orgTrustLevel}
                            onChange={(e) => handleApplyOrgField("trust_level", e.target.value)}
                            className="w-full h-8 rounded-lg border border-border bg-muted/30 px-2 text-sm outline-none focus:border-primary/25"
                          >
                            {TRUST_LEVELS.map((tl) => (
                              <option key={tl.value} value={tl.value}>{tl.label}</option>
                            ))}
                          </select>
                        </div>
                      </div>
                      <div className="space-y-1">
                        <label className="text-[10px] font-medium text-muted-foreground/60">Model</label>
                        <Input
                          value={orgModel}
                          onChange={(e: React.ChangeEvent<HTMLInputElement>) => handleApplyOrgField("model", e.target.value)}
                          placeholder="e.g. claude-sonnet-4-6 (leave empty for default)"
                          className="bg-muted/30 border-border focus:border-primary/25 text-sm h-8 font-mono"
                        />
                      </div>
                      <div className="space-y-1">
                        <label className="text-[10px] font-medium text-muted-foreground/60">Working Directory</label>
                        <div className="flex gap-1.5">
                          <Input
                            value={orgWorkdir}
                            onChange={(e: React.ChangeEvent<HTMLInputElement>) => handleApplyOrgField("workdir", e.target.value)}
                            placeholder="~/projects/my-team (leave empty for default)"
                            className="bg-muted/30 border-border focus:border-primary/25 text-sm h-8 font-mono flex-1"
                          />
                          <button
                            onClick={() => { setFolderPickerTarget("org"); setFolderPickerOpen(true); }}
                            className="shrink-0 h-8 w-8 rounded-lg border border-border bg-muted/30 flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-surface-hover transition-colors"
                          >
                            <FolderOpen className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      </div>
                    </motion.div>
                  )}
                </motion.div>

                {/* Member cards */}
                {orgMembers.length > 0 && (
                  <motion.div variants={itemVariants} className="grid gap-2">
                    {orgMembers.map((member, idx) => {
                      const prov = PROVIDERS.find((p) => p.value === member.provider);
                      const isExpanded = expandedMember === idx;
                      return (
                        <div
                          key={idx}
                          className={cn(
                            "rounded-xl border bg-surface transition-colors",
                            isExpanded ? "border-primary/20" : "border-border",
                          )}
                        >
                          <div className="px-4 py-3 flex items-center gap-3">
                            {prov?.logo && (
                              <img src={prov.logo} alt={prov.label} className="h-5 w-5 object-contain logo-adapt shrink-0" />
                            )}
                            <input
                              value={member.name}
                              onChange={(e) => handleUpdateMember(idx, "name", e.target.value)}
                              placeholder="Name"
                              className="bg-transparent text-sm font-medium outline-none flex-1 min-w-0 placeholder:text-muted-foreground/40"
                            />
                            <select
                              value={member.provider}
                              onChange={(e) => handleUpdateMember(idx, "provider", e.target.value)}
                              className="bg-transparent text-xs text-muted-foreground/60 outline-none cursor-pointer shrink-0"
                            >
                              {PROVIDERS.map((p) => (
                                <option key={p.value} value={p.value}>{p.label}</option>
                              ))}
                            </select>
                            <button
                              onClick={() => setExpandedMember(isExpanded ? null : idx)}
                              className={cn(
                                "shrink-0 p-1 rounded-md transition-colors",
                                isExpanded
                                  ? "text-primary bg-primary/10"
                                  : "text-muted-foreground/40 hover:text-muted-foreground hover:bg-surface-hover",
                              )}
                            >
                              <Settings2 className="h-3.5 w-3.5" />
                            </button>
                          </div>
                          {isExpanded && (
                            <div className="border-t border-border/50 px-4 pb-3 pt-2.5 space-y-2">
                              <div className="space-y-1">
                                <label className="text-[10px] font-medium text-muted-foreground/50">Description</label>
                                <textarea
                                  value={member.description}
                                  onChange={(e) => handleUpdateMember(idx, "description", e.target.value)}
                                  placeholder="What does this member do?"
                                  rows={2}
                                  className="w-full bg-muted/30 rounded-md border border-border px-2 py-1.5 text-xs outline-none focus:border-primary/25 resize-none"
                                />
                              </div>
                              <div className="grid grid-cols-2 gap-2">
                                <div className="space-y-1">
                                  <label className="text-[10px] font-medium text-muted-foreground/50">Trust Level</label>
                                  <select
                                    value={member.trust_level}
                                    onChange={(e) => handleUpdateMember(idx, "trust_level", e.target.value)}
                                    className="w-full h-7 rounded-md border border-border bg-muted/30 px-2 text-xs outline-none focus:border-primary/25"
                                  >
                                    {TRUST_LEVELS.map((tl) => (
                                      <option key={tl.value} value={tl.value}>{tl.label}</option>
                                    ))}
                                  </select>
                                </div>
                                <div className="space-y-1">
                                  <label className="text-[10px] font-medium text-muted-foreground/50">Model</label>
                                  <input
                                    value={member.model}
                                    onChange={(e) => handleUpdateMember(idx, "model", e.target.value)}
                                    placeholder="Default"
                                    className="w-full h-7 bg-muted/30 rounded-md border border-border px-2 text-xs font-mono outline-none focus:border-primary/25"
                                  />
                                </div>
                              </div>
                              <div className="space-y-1">
                                <label className="text-[10px] font-medium text-muted-foreground/50">Working Directory</label>
                                <div className="flex gap-1.5">
                                  <input
                                    value={member.workdir}
                                    onChange={(e) => handleUpdateMember(idx, "workdir", e.target.value)}
                                    placeholder="Default"
                                    className="flex-1 h-7 bg-muted/30 rounded-md border border-border px-2 text-xs font-mono outline-none focus:border-primary/25"
                                  />
                                  <button
                                    onClick={() => { setFolderPickerTarget(idx); setFolderPickerOpen(true); }}
                                    className="shrink-0 h-7 w-7 rounded-md border border-border bg-muted/30 flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-surface-hover transition-colors"
                                  >
                                    <FolderOpen className="h-3 w-3" />
                                  </button>
                                </div>
                              </div>
                              <button
                                onClick={() => handleRemoveMember(idx)}
                                className="flex items-center gap-1 text-[10px] text-destructive/60 hover:text-destructive transition-colors"
                              >
                                <Trash2 className="h-3 w-3" />
                                Remove
                              </button>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </motion.div>
                )}

                {/* Add member + actions */}
                <motion.div variants={itemVariants} className="flex flex-col items-center gap-4">
                  <button
                    onClick={handleAddMember}
                    className="flex items-center gap-1.5 text-xs text-primary hover:text-primary/80 transition-colors"
                  >
                    <Plus className="h-3.5 w-3.5" />
                    Add Member
                  </button>

                  {error && (
                    <p className="text-xs text-destructive">{error}</p>
                  )}

                  <div className="w-full max-w-xs flex gap-2">
                    <Button
                      variant="outline"
                      onClick={handleExportOrg}
                      disabled={orgMembers.length === 0}
                      className="flex-1 text-xs"
                    >
                      Export JSON
                    </Button>
                    <Button
                      onClick={handleCreateOrganization}
                      disabled={!orgName.trim() || orgMembers.length === 0 || orgMembers.some((m) => !m.name.trim()) || loading}
                      className="flex-1 bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
                    >
                      {loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Users className="h-4 w-4 mr-2" />}
                      Create
                    </Button>
                  </div>
                </motion.div>
              </motion.div>
            </motion.div>
          )}

          {step === 3 && kind !== "organization" && (
            <motion.div key="step-config" {...stepTransition}>
              <motion.div
                variants={containerVariants}
                initial="hidden"
                animate="show"
                className="max-w-md mx-auto space-y-5"
              >
                <motion.div variants={itemVariants} className="space-y-2">
                  <label className="text-xs font-medium text-muted-foreground">Name</label>
                  <Input
                    value={name}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => setName(e.target.value)}
                    placeholder="My AI Agent"
                    className="bg-surface border-border focus:border-primary/25"
                  />
                </motion.div>

                {kind === "agent" && (
                  <motion.div variants={itemVariants} className="space-y-2">
                    <label className="text-xs font-medium text-muted-foreground">Working Directory</label>
                    <div className="flex gap-2">
                      <Input
                        value={workdir}
                        onChange={(e: React.ChangeEvent<HTMLInputElement>) => setWorkdir(e.target.value)}
                        placeholder="~/.fp/entities/<uid>/workspace"
                        className="bg-surface border-border focus:border-primary/25 font-mono text-sm flex-1"
                      />
                      <button
                        onClick={() => { setFolderPickerTarget("agent"); setFolderPickerOpen(true); }}
                        className="shrink-0 h-9 w-9 rounded-lg border border-border bg-surface flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-surface-hover transition-colors"
                      >
                        <FolderOpen className="h-4 w-4" />
                      </button>
                    </div>
                    <p className="text-[10px] text-muted-foreground/40">
                      Agent workspace path, defaults to ~/.fp entity directory
                    </p>
                  </motion.div>
                )}

                <motion.div variants={itemVariants} className="space-y-2">
                  <label className="text-xs font-medium text-muted-foreground">Description</label>
                  <textarea
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="What does this entity do?"
                    rows={2}
                    className={cn(
                      "w-full rounded-xl border border-border bg-surface px-4 py-3 text-sm outline-none",
                      "focus:border-primary/25 resize-none placeholder:text-muted-foreground/40",
                    )}
                  />
                </motion.div>

                <motion.div variants={itemVariants} className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium">Public</p>
                    <p className="text-[11px] text-muted-foreground/50">Discoverable by other entities</p>
                  </div>
                  <button
                    onClick={() => setIsPublic(!isPublic)}
                    className={cn(
                      "relative w-11 h-6 rounded-full transition-colors duration-200 focus-visible:outline-none",
                      isPublic ? "bg-primary" : "bg-muted-foreground/20",
                    )}
                  >
                    <span
                      className={cn(
                        "absolute left-0 top-[2px] h-5 w-5 rounded-full bg-white shadow-md transition-transform duration-200",
                        isPublic ? "translate-x-[22px]" : "translate-x-[2px]",
                      )}
                    />
                  </button>
                </motion.div>

                {kind === "agent" && (
                  <motion.div variants={itemVariants}>
                    <button
                      onClick={() => setShowAdvanced(!showAdvanced)}
                      className="flex items-center gap-1.5 text-xs text-muted-foreground/60 hover:text-muted-foreground transition-colors"
                    >
                      {showAdvanced ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                      Advanced Settings
                    </button>
                    {showAdvanced && (
                      <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: "auto" }}
                        className="mt-3 space-y-4 pt-3 border-t border-border"
                      >
                        <div className="space-y-2">
                          <label className="text-xs font-medium text-muted-foreground">Trust Level</label>
                          <div className="grid gap-1.5">
                            {TRUST_LEVELS.map((tl) => (
                              <button
                                key={tl.value}
                                onClick={() => setTrustLevel(tl.value)}
                                className={cn(
                                  "flex items-center justify-between px-3 py-2 rounded-lg border text-left text-sm transition-all",
                                  trustLevel === tl.value
                                    ? "border-primary/30 bg-primary/5"
                                    : "border-border bg-surface hover:border-muted-foreground/20",
                                )}
                              >
                                <span className="font-medium">{tl.label}</span>
                                <span className="text-[11px] text-muted-foreground/50">{tl.description}</span>
                              </button>
                            ))}
                          </div>
                        </div>
                        <div className="space-y-2">
                          <label className="text-xs font-medium text-muted-foreground">Model</label>
                          <Input
                            value={model}
                            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setModel(e.target.value)}
                            placeholder="e.g. claude-sonnet-4-6, o3"
                            className="bg-surface border-border focus:border-primary/25 font-mono text-sm"
                          />
                          <p className="text-[10px] text-muted-foreground/40">Leave empty for provider default</p>
                        </div>
                      </motion.div>
                    )}
                  </motion.div>
                )}

                {error && (
                  <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-xs text-destructive">
                    {error}
                  </motion.p>
                )}

                <motion.div variants={itemVariants}>
                  <Button
                    onClick={handleRegister}
                    disabled={!name.trim() || loading}
                    className="w-full bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
                  >
                    {loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <UserPlus className="h-4 w-4 mr-2" />}
                    Create Entity
                  </Button>
                </motion.div>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <FolderPicker
        open={folderPickerOpen}
        onOpenChange={setFolderPickerOpen}
        onSelect={(path) => {
          if (folderPickerTarget === "agent") setWorkdir(path);
          else if (folderPickerTarget === "org") handleApplyOrgField("workdir", path);
          else handleUpdateMember(folderPickerTarget, "workdir", path);
        }}
      />
    </div>
  );
}

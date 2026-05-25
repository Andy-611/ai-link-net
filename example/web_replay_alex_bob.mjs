import fs from "node:fs";
import path from "node:path";
import playwright from "../aln/web/node_modules/playwright/index.js";

const { chromium } = playwright;

const port = process.env.TRUST_DEMO_PORT ?? "18164";
const uiPort = process.env.TRUST_DEMO_UI_PORT ?? "5179";
const videoFile = process.env.TRUST_VIDEO_FILE;
const summaryFile = process.env.TRUST_SUMMARY_FILE;
const contractFile = process.env.TRUST_CONTRACT_FILE;
const timelineFile = process.env.TRUST_TIMELINE_FILE;

if (!videoFile || !summaryFile || !contractFile || !timelineFile) {
  throw new Error("Missing output env vars");
}

const base = `http://127.0.0.1:${port}/api/v1`;
const title = `Vendor Portal MVP Outsourcing Delivery ${new Date()
  .toISOString()
  .slice(11, 19)
  .replaceAll(":", "")}`;

async function request(method, pathName, body) {
  const response = await fetch(`${base}${pathName}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body == null ? undefined : JSON.stringify(body),
  });
  const text = await response.text();
  if (!response.ok) {
    throw new Error(`${method} ${pathName} failed: ${response.status} ${text}`);
  }
  return JSON.parse(text);
}

async function register(kind, name, description) {
  const existing = (await request("GET", "/entities")).data;
  const found = existing.find((entity) => entity.kind === kind && entity.name === name);
  if (found) return found;
  return (await request("POST", "/entities", {
    kind,
    name,
    description,
    is_public: true,
  })).data;
}

async function getContract(contractId) {
  return (await request("GET", `/trade/contracts/${contractId}`)).data;
}

async function tradeSend(actor, kind, payload) {
  return request("POST", "/trade/send", {
    from_entity: actor,
    kind,
    payload,
  });
}

function shortHash(value) {
  return value ? value.slice(0, 12) : "-";
}

async function delay(ms) {
  await new Promise((resolve) => setTimeout(resolve, ms));
}

function actionPayload(contract, extra = {}) {
  return {
    contract_id: contract.contract_id,
    expected_status: contract.status,
    revision: contract.draft_version,
    terms_hash: contract.terms_hash,
    source_snapshot_hash: contract.current_snapshot_hash,
    ...extra,
  };
}

function deliveryPayload(contract, { version, summary, artifacts, messageId, producedAt }) {
  return {
    delivery_id: `${contract.contract_id}-${version}`,
    version,
    summary,
    artifacts,
    source_session_id: contract.work_session_id,
    source_message_id: messageId,
    produced_by: { address: contract.party_b.address },
    produced_at: producedAt,
  };
}

function executionCostsPayload(contract, { phase, inputTokens, outputTokens, costUsd, runtimeMs, notes, recordedAt }) {
  return [{
    report_id: `${contract.contract_id}-cost-${phase}`,
    actor: { address: contract.party_b.address },
    phase,
    provider: "codex",
    model: "gpt-5-codex",
    input_tokens: inputTokens,
    output_tokens: outputTokens,
    cost_usd: costUsd,
    runtime_ms: runtimeMs,
    notes,
    recorded_at: recordedAt,
  }];
}

function loginUrlFor(user, hostUrl) {
  return `http://127.0.0.1:${uiPort}/?entity_uid=${user.entity_uid}&host_url=${encodeURIComponent(hostUrl)}`;
}

async function ensureSpotlightStyles(page) {
  await page.evaluate(() => {
    if (document.getElementById("__codex_spotlight_style")) return;
    const style = document.createElement("style");
    style.id = "__codex_spotlight_style";
    style.textContent = `
      .__codex_spotlight {
        position: relative;
        z-index: 3;
        outline: 3px solid rgba(249, 115, 22, 0.92);
        outline-offset: 6px;
        border-radius: 20px;
        box-shadow: 0 0 0 9999px rgba(15, 23, 42, 0.18), 0 22px 52px rgba(249, 115, 22, 0.22);
        transition: box-shadow 160ms ease, outline-color 160ms ease;
      }
    `;
    document.head.appendChild(style);
  });
}

async function spotlight(page, locator, ms = 1400, { required = false } = {}) {
  const target = locator;
  try {
    await target.waitFor({ state: "visible", timeout: 15000 });
  } catch (error) {
    if (required) throw error;
    return false;
  }
  await target.evaluate((node) => {
    node.scrollIntoView({ block: "center", behavior: "instant" });
  });
  await ensureSpotlightStyles(page);
  await target.evaluate((node) => {
    node.classList.add("__codex_spotlight");
  });
  await delay(ms);
  await target.evaluate((node) => {
    node.classList.remove("__codex_spotlight");
  }).catch(() => {});
  return true;
}

async function visibleTextLocator(page, text, exact = true) {
  const locator = page.getByText(text, { exact });
  const count = await locator.count();
  for (let index = 0; index < count; index += 1) {
    const candidate = locator.nth(index);
    if (await candidate.isVisible().catch(() => false)) {
      return candidate;
    }
  }
  return locator.first();
}

async function clickReplayStep(page, stepIndex) {
  const stepChip = page.locator("button").filter({ hasText: `S${stepIndex} ` }).first();
  if (await stepChip.count()) {
    await stepChip.scrollIntoViewIfNeeded().catch(() => {});
    await stepChip.click().catch(() => {});
    await delay(500);
  }
}

async function showTradeFocus(page, stepIndex, focusItems) {
  if (typeof stepIndex === "number") {
    await clickReplayStep(page, stepIndex);
  }
  for (const item of focusItems) {
    const locator = await visibleTextLocator(page, item.text, item.exact !== false);
    if (item.click) {
      await locator.click().catch(() => {});
      await delay(item.afterClickMs ?? 400);
    }
    await spotlight(page, locator, item.ms ?? 1500);
  }
}

async function openObserver(page, user, hostUrl, contractId) {
  await page.goto(loginUrlFor(user, hostUrl), { waitUntil: "networkidle" });
  await page.goto(`http://127.0.0.1:${uiPort}/observer`, { waitUntil: "networkidle" });
  await (await visibleTextLocator(page, "Observer")).waitFor({ timeout: 20000 });
  const select = page.locator("select").first();
  await select.selectOption(contractId).catch(() => {});
  await delay(1000);
}

async function showObserverSnapshot(page, hostUrl, user, contractId, focusItems) {
  await openObserver(page, user, hostUrl, contractId);
  await spotlight(page, await visibleTextLocator(page, "Protocol Flow"), 1200, { required: true });
  await (await visibleTextLocator(page, "Snapshot")).click();
  await delay(500);
  for (const item of focusItems) {
    const locator = await visibleTextLocator(page, item.text, item.exact !== false);
    await spotlight(page, locator, item.ms ?? 1500);
  }
}

async function switchUser(page, user, hostUrl, contractId) {
  await page.goto(loginUrlFor(user, hostUrl), { waitUntil: "networkidle" });
  await page.waitForURL(/\/chat$/, { timeout: 20000 }).catch(() => {});
  await page.goto(`http://127.0.0.1:${uiPort}/trade`, { waitUntil: "networkidle" });
  await Promise.race([
    page.getByRole("button", { name: "Contract" }).waitFor({ timeout: 20000 }),
    page.getByText("My Trade", { exact: true }).waitFor({ timeout: 20000 }),
    page.getByText(title).first().waitFor({ timeout: 20000 }),
  ]);
  if (contractId) {
    await expandContract(page, contractId);
  }
}

async function expandContract(page, contractId) {
  const card = page.locator("button").filter({ hasText: title }).first();
  await card.waitFor({ timeout: 10000 });
  await card.click();
  await page.getByText(contractId).waitFor({ timeout: 10000 }).catch(() => {});
}

async function createContractViaUi(page, alex, bob) {
  await page.getByRole("button", { name: "Contract" }).click();
  await page.getByRole("dialog").waitFor({ timeout: 5000 });

  const selects = page.locator("select");
  await selects.nth(0).selectOption(alex.entity_uid);
  await selects.nth(1).selectOption(bob.entity_uid);
  await page.getByPlaceholder("Contract title").fill(title);
  await page.getByPlaceholder("Task description...").fill(
    "Bob will deliver a vendor portal MVP for Alex in multiple versions. Alex may request rework, and every step references the latest signed contract snapshot.",
  );
  await page.getByPlaceholder("0.00").fill("300");
  await selects.nth(2).selectOption("direct");
  await page.getByRole("button", { name: "Create Contract" }).click();
  await page.getByRole("dialog").waitFor({ state: "hidden", timeout: 10000 });
  await page.getByText(title).first().waitFor({ timeout: 10000 });
}

function timelineEntry(label, actor, contract, source, note) {
  return {
    label,
    actor,
    note,
    status: contract.status,
    source_snapshot_hash: source,
    snapshot_hash: contract.current_snapshot_hash,
    prev_snapshot_hash: contract.prev_snapshot_hash,
    linked: source == null || contract.prev_snapshot_hash === source,
    terms_hash: contract.terms_hash,
    last_action: contract.last_action,
    rework_count: contract.rework_count,
    rating: contract.rating,
    delivery_version: contract.current_delivery?.version ?? null,
    delivery_artifacts: (contract.current_delivery?.artifacts ?? []).length,
    execution_cost_count: (contract.current_execution_costs ?? []).length,
    execution_cost_usd: (contract.current_execution_costs ?? []).reduce((sum, item) => sum + (item.cost_usd ?? 0), 0),
  };
}

async function main() {
  const outDir = path.dirname(videoFile);
  const alex = await register("human", "Alex", "Creates task and reviews Bob's delivery");
  const bob = await register("human", "Bob", "Accepts task and iterates on delivery");
  const arbiter = await register("arbiter", "Arbiter", "Reviews transitions and signs snapshots");

  const hostUrl = `http://127.0.0.1:${port}`;
  const browser = await chromium.launch({
    channel: "chrome",
    headless: false,
  });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 960 },
    recordVideo: {
      dir: outDir,
      size: { width: 1440, height: 960 },
    },
  });
  const page = await context.newPage();

  const timeline = [];

  await switchUser(page, alex, hostUrl, null);
  await delay(1200);
  await createContractViaUi(page, alex, bob);
  await delay(1800);

  let contracts = (await request("GET", "/trade/contracts")).data;
  let contract = contracts
    .filter((item) => item.title === title)
    .sort((left, right) => (right.created_at ?? 0) - (left.created_at ?? 0))[0];
  if (!contract) {
    throw new Error("Created contract not found");
  }

  timeline.push(
    timelineEntry(
      "S0_CREATE",
      "Alex",
      contract,
      null,
      "Alex creates the contract in the Web UI; Arbiter signs the draft snapshot.",
    ),
  );
  await switchUser(page, alex, hostUrl, contract.contract_id);
  await delay(1800);
  await showTradeFocus(page, 0, [
    { text: "Replay", ms: 1400 },
    { text: "Snapshot Evidence", ms: 1500 },
    { text: "Current Snapshot", ms: 1300 },
    { text: "Arbiter Review", ms: 1500 },
    { text: "Signed At", ms: 1200 },
  ]);

  let source = contract.current_snapshot_hash;
  await switchUser(page, bob, hostUrl, contract.contract_id);
  await delay(1200);
  await tradeSend("Bob", "contract_approve", actionPayload(contract));
  await delay(1800);
  contract = await getContract(contract.contract_id);
  timeline.push(
    timelineEntry(
      "S1_ACCEPT",
      "Bob",
      contract,
      source,
      "Bob approves from the draft snapshot and the contract becomes active.",
    ),
  );
  await switchUser(page, bob, hostUrl, contract.contract_id);
  await delay(1800);
  await showTradeFocus(page, 1, [
    { text: "Replay", ms: 1200 },
    { text: "Snapshot Timeline", ms: 1500 },
    { text: "S1 Approve", exact: false, ms: 1500 },
    { text: "Source Snapshot", ms: 1200 },
    { text: "Signed Snapshot", ms: 1200 },
  ]);

  source = contract.current_snapshot_hash;
  let now = Date.now() / 1000;
  await tradeSend("Bob", "contract_complete", actionPayload(contract, {
    reason: "Delivery v1: login, project list, and base contract detail page are ready.",
    delivery: deliveryPayload(contract, {
      version: "v1.0.0",
      summary: "Vendor portal MVP first delivery with login, project list, and base contract detail page.",
      artifacts: [
        { kind: "preview", uri: "https://preview.example/vendor-portal/v1", label: "Preview v1" },
        { kind: "commit", uri: "git://ai-link-net/commit/v1-base", label: "Commit v1-base", digest: "sha256:v1-base" },
      ],
      messageId: "web-replay-delivery-v1",
      producedAt: now,
    }),
    execution_costs: executionCostsPayload(contract, {
      phase: "implementation",
      inputTokens: 1200,
      outputTokens: 450,
      costUsd: 0.37,
      runtimeMs: 182000,
      notes: "Initial implementation delivery turn",
      recordedAt: now,
    }),
  }));
  await delay(1800);
  contract = await getContract(contract.contract_id);
  timeline.push(
    timelineEntry(
      "S2_DELIVER_V1",
      "Bob",
      contract,
      source,
      "Bob submits outsourced delivery v1 from the active snapshot.",
    ),
  );
  await switchUser(page, bob, hostUrl, contract.contract_id);
  await delay(1800);
  await showTradeFocus(page, 2, [
    { text: "Delivery Evidence", ms: 1500 },
    { text: "Version", ms: 1100 },
    { text: "v1.0.0", ms: 1400 },
    { text: "Preview v1", ms: 1400 },
    { text: "Commit v1-base", ms: 1400 },
    { text: "Execution Costs", ms: 1500 },
    { text: "$0.37", ms: 1400 },
  ]);
  await showObserverSnapshot(page, hostUrl, alex, contract.contract_id, [
    { text: "Snapshot", click: true, afterClickMs: 500, ms: 1000 },
    { text: "Current Delivery", ms: 1500 },
    { text: "v1.0.0", ms: 1300 },
    { text: "Execution Costs", ms: 1500 },
    { text: "$0.37", ms: 1300 },
    { text: "Snapshot Chain", ms: 1300 },
  ]);

  source = contract.current_snapshot_hash;
  await switchUser(page, alex, hostUrl, contract.contract_id);
  await delay(1200);
  await tradeSend("Alex", "contract_rework", actionPayload(contract, {
    reason: "Please add trust evidence for review: snapshot chain, approvals, and Arbiter attestation.",
  }));
  await delay(1800);
  contract = await getContract(contract.contract_id);
  timeline.push(
    timelineEntry(
      "S3_REWORK",
      "Alex",
      contract,
      source,
      "Alex requests rework on the outsourced delivery from the completing snapshot.",
    ),
  );
  await switchUser(page, alex, hostUrl, contract.contract_id);
  await delay(1800);
  await showTradeFocus(page, 3, [
    { text: "Replay", ms: 1200 },
    { text: "S3 Rework", exact: false, ms: 1500 },
    { text: "Reason / Review", ms: 1300 },
    { text: "Snapshot Timeline", ms: 1500 },
    { text: "Please add trust evidence for review", exact: false, ms: 1600 },
  ]);

  source = contract.current_snapshot_hash;
  await switchUser(page, bob, hostUrl, contract.contract_id);
  await delay(1200);
  now = Date.now() / 1000;
  await tradeSend("Bob", "contract_complete", actionPayload(contract, {
    reason: "Delivery v2: trust review view, signed snapshot chain, and approval evidence are added.",
    delivery: deliveryPayload(contract, {
      version: "v2.0.0",
      summary: "Second delivery adds trust evidence, signed snapshot chain, approval review, and Arbiter attestation context.",
      artifacts: [
        { kind: "preview", uri: "https://preview.example/vendor-portal/v2", label: "Preview v2" },
        { kind: "commit", uri: "git://ai-link-net/commit/v2-trust", label: "Commit v2-trust", digest: "sha256:v2-trust" },
      ],
      messageId: "web-replay-delivery-v2",
      producedAt: now,
    }),
    execution_costs: executionCostsPayload(contract, {
      phase: "rework",
      inputTokens: 900,
      outputTokens: 320,
      costUsd: 0.24,
      runtimeMs: 133000,
      notes: "Rework delivery with trust evidence",
      recordedAt: now,
    }),
  }));
  await delay(1800);
  contract = await getContract(contract.contract_id);
  timeline.push(
    timelineEntry(
      "S4_DELIVER_V2",
      "Bob",
      contract,
      source,
      "Bob submits outsourced delivery v2 from the rework snapshot.",
    ),
  );
  await switchUser(page, bob, hostUrl, contract.contract_id);
  await delay(1800);
  await showTradeFocus(page, 4, [
    { text: "Delivery Evidence", ms: 1500 },
    { text: "v2.0.0", ms: 1400 },
    { text: "Preview v2", ms: 1400 },
    { text: "Commit v2-trust", ms: 1400 },
    { text: "Execution Costs", ms: 1500 },
    { text: "$0.24", ms: 1400 },
  ]);
  await showObserverSnapshot(page, hostUrl, alex, contract.contract_id, [
    { text: "Snapshot", click: true, afterClickMs: 500, ms: 1000 },
    { text: "Current Delivery", ms: 1500 },
    { text: "v2.0.0", ms: 1300 },
    { text: "Execution Costs", ms: 1500 },
    { text: "$0.24", ms: 1300 },
    { text: "Replay Steps", ms: 1300 },
  ]);

  source = contract.current_snapshot_hash;
  await switchUser(page, alex, hostUrl, contract.contract_id);
  await delay(1200);
  await tradeSend("Alex", "contract_accept", actionPayload(contract, {
    reason: "Alex accepts v2 as the final outsourced delivery.",
  }));
  await delay(1800);
  contract = await getContract(contract.contract_id);
  timeline.push(
    timelineEntry(
      "S5_ACCEPT_DELIVERY",
      "Alex",
      contract,
      source,
      "Alex accepts the revised outsourced delivery and moves the contract to settling.",
    ),
  );
  await switchUser(page, alex, hostUrl, contract.contract_id);
  await delay(1800);
  await showTradeFocus(page, 5, [
    { text: "Replay", ms: 1200 },
    { text: "S5 Accept", exact: false, ms: 1500 },
    { text: "Arbiter Review", ms: 1500 },
    { text: "Delivery Evidence", ms: 1400 },
  ]);

  source = contract.current_snapshot_hash;
  await tradeSend("Alex", "contract_rate", actionPayload(contract, {
    rating: 5,
    review: "Clear delivery history, clean rework loop, and auditable trust evidence.",
  }));
  await delay(1800);
  contract = await getContract(contract.contract_id);
  timeline.push(
    timelineEntry(
      "S6_RATE",
      "Alex",
      contract,
      source,
      "Alex rates the finished outsourced delivery in the same UI.",
    ),
  );
  await switchUser(page, alex, hostUrl, contract.contract_id);
  await delay(2400);
  await showTradeFocus(page, 6, [
    { text: "Replay", ms: 1200 },
    { text: "S6 Rate", exact: false, ms: 1500 },
    { text: "Rating:", exact: false, ms: 1400 },
    { text: "\"Clear delivery history, clean rework loop, and auditable trust evidence.\"", ms: 1700 },
    { text: "Snapshot Timeline", ms: 1500 },
    { text: "Arbiter Review", ms: 1500 },
  ]);
  await showObserverSnapshot(page, hostUrl, alex, contract.contract_id, [
    { text: "Snapshot", click: true, afterClickMs: 500, ms: 1000 },
    { text: "Current Delivery", ms: 1400 },
    { text: "Execution Costs", ms: 1400 },
    { text: "Replay Steps", ms: 1400 },
    { text: "Exec Cost", exact: false, ms: 1200 },
  ]);
  await delay(2400);

  fs.writeFileSync(contractFile, JSON.stringify(contract, null, 2));
  fs.writeFileSync(summaryFile, JSON.stringify({
    web_url: `http://127.0.0.1:${uiPort}/?entity_uid=${alex.entity_uid}&host_url=${encodeURIComponent(hostUrl)}#/trade`,
    api_host: hostUrl,
    contract_detail_api: `${base}/trade/contracts/${contract.contract_id}`,
    contract_id: contract.contract_id,
    participants: {
      alex: { uid: alex.entity_uid, address: alex.address.address },
      bob: { uid: bob.entity_uid, address: bob.address.address },
      arbiter: { uid: arbiter.entity_uid, address: arbiter.address.address },
    },
    final: {
      status: contract.status,
      rating: contract.rating,
      review: contract.review,
      rework_count: contract.rework_count,
      snapshot_hash: contract.current_snapshot_hash,
      terms_hash: contract.terms_hash,
      delivery_version: contract.current_delivery?.version ?? null,
      artifact_count: (contract.current_delivery?.artifacts ?? []).length,
      cost_entries: (contract.current_execution_costs ?? []).length,
      cost_usd: (contract.current_execution_costs ?? []).reduce((sum, item) => sum + (item.cost_usd ?? 0), 0),
    },
    timeline,
  }, null, 2));
  fs.writeFileSync(timelineFile, [
    "# Alex/Bob Native Web UI Replay Timeline",
    "",
    "| Step | Actor | Status | Source | Snapshot | Linked | Last Action | Delivery | Artifacts | Cost USD |",
    "|---|---|---|---|---|---|---|---|---:|---:|",
    ...timeline.map((step) => `| ${step.label} | ${step.actor} | ${step.status} | \`${shortHash(step.source_snapshot_hash)}\` | \`${shortHash(step.snapshot_hash)}\` | ${step.linked} | ${step.last_action} | ${step.delivery_version ?? "-"} | ${step.delivery_artifacts} | ${step.execution_cost_usd.toFixed(2)} |`),
    "",
    "## Notes",
    "",
    ...timeline.map((step) => `- **${step.label}**: ${step.note}`),
    "",
  ].join("\n"));

  await context.close();
  await browser.close();

  const recorded = fs.readdirSync(outDir).find((name) => name.endsWith(".webm"));
  if (!recorded) {
    throw new Error("Playwright did not produce a .webm video");
  }
  const webmPath = path.join(outDir, recorded);
  console.log(`playwright_video_webm=${webmPath}`);
}

await main();

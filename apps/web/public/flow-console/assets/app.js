const state = {
  selectedTemplateId: null,
  templates: [],
  savedFlows: [],
  runs: [],
  currentSavedFlowId: null,
  nodes: [],
  flow: null,
  plan: null,
  aiEditResult: null,
  repairResult: null,
  run: null,
  task: null,
  runtimeCommand: "",
  selectedStepId: null,
  runPollTimer: null,
  runPollToken: 0,
  activePage: "hub",
  creationMode: "template",
  generationTimer: null,
  generationStageIndex: 0,
  executors: [],
  capabilities: [],
  discoveredCapabilities: [],
  capabilityFilter: "all",
  capabilityQuery: "",
};

const terminalRunStatuses = new Set(["succeeded", "failed", "cancelled"]);
const activeRunStorageKey = "promptNodeFlow.activeRunId";
const runPollInitialDelayMs = 3000;
const runPollIntervalMs = 10000;
const keywordTemplates = new Set();
const targetUrlsTemplates = new Set();
const inquiryTextTemplates = new Set();
const reportFocusTemplates = new Set(["compact", "balanced", "fine"]);

const generationStages = [
  {id: "understand", label: "理解任务", message: "正在读取你的任务描述和任务材料。"},
  {id: "template", label: "结合模板", message: "正在把自然语言需求映射到当前任务模板。"},
  {id: "compose", label: "生成业务步骤", message: "正在拆解数据获取、整理、分析和报告步骤。"},
  {id: "validate", label: "校验 Flow", message: "正在检查节点、依赖、风险边界和完成条件。"},
  {id: "plan", label: "生成执行计划", message: "正在渲染用户可读的 Prompt Node 计划。"},
];

const templatePresets = {
  compact: {
    request: "Explain how an observable outer Agent loop improves long, repeatable work while preserving each Agent's inner loop.",
    materials: "Audience: developers evaluating reusable multi-Agent workflows. Deliverable: a substantial Markdown article with concrete boundaries and trade-offs.",
    maxPages: 1,
    maxPagesDisabled: true,
  },
  balanced: {
    request: "Explain how an observable outer Agent loop improves long, repeatable work while preserving each Agent's inner loop.",
    materials: "Use Planner, Writer and Editor roles. Show durable handoffs, evidence, recovery and adjustable task granularity.",
    maxPages: 1,
    maxPagesDisabled: true,
  },
  fine: {
    request: "Explain how an observable outer Agent loop improves long, repeatable work while preserving each Agent's inner loop.",
    materials: "Expose research, planning, drafting, review and revision as separate observable Agent Nodes, then publish article.md.",
    maxPages: 1,
    maxPagesDisabled: true,
  },
  inquiry_customer_priority_clustering: {
    request: "按商品、国家、采购意图和紧急程度聚类，标记高优先级客户，并给出跟进建议和话术草稿。",
    materials: "customer,country,product,quantity,inquiry_time,message\nAlice Trading,US,waterproof laptop bag,500,2026-06-12,Need quote ASAP and sample shipping cost\nBeta Import,DE,solar garden light,1200,2026-06-10,Ready to place order this week if price is good\nChen Retail,MY,bluetooth earbuds,80,2026-05-30,Ask for catalog and MOQ",
    targetUrl: "",
    targetUrls: "",
    inquiryText: "customer,country,product,quantity,inquiry_time,message\nAlice Trading,US,waterproof laptop bag,500,2026-06-12,Need quote ASAP and sample shipping cost\nBeta Import,DE,solar garden light,1200,2026-06-10,Ready to place order this week if price is good\nChen Retail,MY,bluetooth earbuds,80,2026-05-30,Ask for catalog and MOQ",
    keyword: "",
    maxPages: 1,
    maxPagesDisabled: true,
  },
  taobao_product_detail_diagnosis: {
    request: "诊断淘宝商品详情页标题、主图、规格、卖点和页面结构是否清晰，并给出优化建议；如遇登录或风控拦截，说明边界。",
    materials: "",
    targetUrl: "",
    targetUrls: "",
    inquiryText: "",
    keyword: "",
    maxPages: 1,
    maxPagesDisabled: true,
  },
  taobao_keyword_competitor_price_analysis: {
    request: "分析淘宝搜索结果页可见竞品、价格带、标题表达和常见卖点；如遇登录或风控拦截，说明边界。",
    materials: "电脑包",
    targetUrl: "https://www.taobao.com",
    targetUrls: "",
    inquiryText: "",
    keyword: "电脑包",
    maxPages: 1,
    maxPagesDisabled: true,
  },
  taobao_search_snapshot_report: {
    request: "识别淘宝搜索结果页中可见商品、价格、店铺、卖点和页面结构；如遇登录拦截，说明边界和下一步。",
    materials: "电脑",
    targetUrl: "https://www.taobao.com",
    targetUrls: "",
    inquiryText: "",
    keyword: "电脑",
    maxPages: 1,
    maxPagesDisabled: true,
  },
  product_list_analysis: {
    request: "帮我采集这个店铺前 2 页商品标题、价格、链接，并生成价格分析。",
    materials: "https://example.com",
    targetUrl: "https://example.com",
    targetUrls: "",
    inquiryText: "",
    keyword: "",
    maxPages: 2,
    maxPagesDisabled: false,
  },
  web_page_snapshot_report: {
    request: "识别页面主要内容、可见文字和页面用途。",
    materials: "https://example.com",
    targetUrl: "https://example.com",
    targetUrls: "",
    inquiryText: "",
    keyword: "",
    maxPages: 1,
    maxPagesDisabled: true,
  },
};

const $ = (id) => document.getElementById(id);

function bindClick(id, action) {
  const element = $(id);
  if (element) {
    element.addEventListener("click", () => guarded(action));
  }
}

function setStatus(text, kind = "") {
  $("status").textContent = text;
  $("status-dot").className = "dot" + (kind ? ` ${kind}` : "");
}

function setNotice(id, text, kind = "") {
  const element = $(id);
  element.textContent = text;
  element.className = "notice" + (kind ? ` ${kind}` : "");
}

function startGenerationProgress() {
  stopGenerationProgress();
  state.generationStageIndex = 0;
  const panel = $("generation-progress");
  if (!panel) return;
  panel.hidden = false;
  setGenerationStage(0);
  state.generationTimer = window.setInterval(() => {
    const next = Math.min(state.generationStageIndex + 1, generationStages.length - 1);
    setGenerationStage(next);
    if (next === generationStages.length - 1) {
      stopGenerationTimerOnly();
    }
  }, 1400);
}

function stopGenerationTimerOnly() {
  if (state.generationTimer) {
    window.clearInterval(state.generationTimer);
    state.generationTimer = null;
  }
}

function stopGenerationProgress({success = false, error = ""} = {}) {
  stopGenerationTimerOnly();
  const panel = $("generation-progress");
  if (!panel) return;
  if (success) {
    setGenerationStage(generationStages.length - 1);
    document.querySelectorAll(".generation-step").forEach((step) => {
      step.classList.add("done");
      step.classList.remove("active");
    });
    $("generation-stage").textContent = "完成";
    $("generation-stage").className = "pill ok";
    $("generation-message").textContent = "候选 Flow 已生成并通过前端流程，正在展示结果。";
    return;
  }
  if (error) {
    $("generation-stage").textContent = "失败";
    $("generation-stage").className = "pill err";
    $("generation-message").textContent = error;
  }
}

function setGenerationStage(index) {
  state.generationStageIndex = index;
  const stage = generationStages[index];
  if (!stage) return;
  $("generation-title").textContent = "正在生成 Flow";
  $("generation-stage").textContent = stage.label;
  $("generation-stage").className = "pill warn";
  $("generation-message").textContent = stage.message;
  document.querySelectorAll(".generation-step").forEach((element) => {
    const stageIndex = generationStages.findIndex((item) => item.id === element.dataset.stage);
    element.classList.toggle("active", stageIndex === index);
    element.classList.toggle("done", stageIndex >= 0 && stageIndex < index);
  });
}

function switchPage(page) {
  state.activePage = page;
  document.querySelectorAll(".workspace-page").forEach((section) => {
    section.classList.toggle("active", section.dataset.page === page);
  });
  document.querySelectorAll(".nav-item, .section-tab").forEach((button) => {
    button.classList.toggle("active", button.dataset.page === page);
  });
  if (page === "hub") renderHub();
  if (page === "template-admin") renderTemplateAdmin();
  if (page === "capabilities") renderCapabilities();
  if (page === "flows" && state.flow) {
    renderCanvas(state.flow, null);
  }
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: {"content-type": "application/json", ...(options.headers || {})},
    ...options,
  });
  const text = await response.text();
  let body = null;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch (_) {
      body = text;
    }
  }
  if (!response.ok) {
    throw new Error(typeof body === "string" ? body : JSON.stringify(body, null, 2));
  }
  return body;
}

async function loadCatalog() {
  setStatus("连接中");
  const [templates, nodes, savedFlows, runs, system, capabilityCatalog] = await Promise.all([
    api("/api/flow-templates"),
    api("/api/flow-nodes"),
    api("/api/flows"),
    api("/api/flows/runs"),
    api("/api/v1/system/status"),
    api("/api/v1/capabilities"),
  ]);
  state.templates = templates;
  state.nodes = nodes;
  state.savedFlows = savedFlows;
  state.runs = runs;
  state.executors = Array.isArray(system.executors) ? system.executors : [];
  state.capabilities = Array.isArray(capabilityCatalog.items) ? capabilityCatalog.items : [];
  state.selectedTemplateId = state.selectedTemplateId
    || (templates.find((template) => template.template_id === "balanced") || templates[0] || {}).template_id;
  renderTemplates();
  renderSavedFlows();
  renderTemplateAdmin();
  restoreActiveRunFromHistory();
  renderRun();
  renderRunHistory();
  applyTemplatePreset();
  syncExecutorOptions();
  renderCapabilities();
  syncCapabilityForm();
  $("catalog-count").textContent = `${templates.length} / ${nodes.length}`;
  setStatus("已连接", "ok");
  setNotice("input-message", "模板已加载。", "ok");
  renderHub();
}

function capabilityKindLabel(kind) {
  return ({agent_cli: "Agent CLI", cli: "JSON CLI", mcp_stdio: "MCP stdio", http: "HTTP"})[kind] || kind;
}

function capabilityAvatar(capability) {
  const id = `${capability.id || ""} ${capability.name || ""}`.toLowerCase();
  if (id.includes("codex")) return "CX";
  if (id.includes("opencode")) return "OC";
  if (capability.kind === "mcp_stdio") return "M";
  if (capability.kind === "http") return "↗";
  if (capability.kind === "cli") return ">_";
  const initials = String(capability.name || "Agent").split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join("");
  return initials.toUpperCase() || "A";
}

function capabilitySummary(capability, connected) {
  if (connected && capability.kind === "agent_cli") return "可作为 Agent Node 的本地执行者，保留内部 Agent loop。";
  if (!connected && capability.kind === "agent_cli") return "已在本机发现。连接后即可绑定到 Agent Node。";
  if (capability.kind === "mcp_stdio") return "通过标准 stdio 生命周期调用固定 MCP tool。";
  if (capability.kind === "http") return "通过固定 GET / POST endpoint 执行并记录结果。";
  if (capability.kind === "cli") return "通过 JSON stdin/stdout 合同执行本地命令。";
  return capability.description || capability.id;
}

function capabilityTechnicalDetails(capability) {
  const config = capability.config || {};
  const target = config.executable || config.url || "-";
  const version = config.version || capability.version || "-";
  const effects = (capability.effects || []).join(", ") || "-";
  const fingerprint = capability.fingerprint || "Not saved yet";
  return `
    <details class="capability-technical">
      <summary>技术详情</summary>
      <dl>
        <div><dt>Target</dt><dd><code>${escapeHtml(target)}</code></dd></div>
        <div><dt>Version</dt><dd>${escapeHtml(version)}</dd></div>
        <div><dt>Effects</dt><dd>${escapeHtml(effects)}</dd></div>
        <div><dt>Fingerprint</dt><dd><code>${escapeHtml(fingerprint)}</code></dd></div>
      </dl>
    </details>`;
}

function capabilityLibraryItems() {
  const savedIds = new Set(state.capabilities.map((item) => item.id));
  return [
    ...state.capabilities.map((capability) => ({capability, connected: true, discoveredIndex: -1})),
    ...state.discoveredCapabilities
      .map((capability, discoveredIndex) => ({capability, connected: false, discoveredIndex}))
      .filter((item) => !savedIds.has(item.capability.id)),
  ];
}

function renderCapabilities() {
  const catalog = $("capability-list");
  if (!catalog) return;
  const allItems = capabilityLibraryItems();
  const query = state.capabilityQuery.trim().toLowerCase();
  const filteredItems = allItems.filter(({capability}) => {
    const kindMatches = state.capabilityFilter === "all"
      || (state.capabilityFilter === "agent_cli" && capability.kind === "agent_cli")
      || (state.capabilityFilter === "tools" && capability.kind !== "agent_cli");
    const queryMatches = !query || [capability.name, capability.id, capability.kind, capability.description]
      .filter(Boolean).join(" ").toLowerCase().includes(query);
    return kindMatches && queryMatches;
  });
  $("capability-count").textContent = String(allItems.length);
  $("capability-connected-count").textContent = String(state.capabilities.length);
  $("capability-available-count").textContent = String(Math.max(0, allItems.length - state.capabilities.length));
  catalog.innerHTML = filteredItems.length ? filteredItems.map(({capability, connected, discoveredIndex}) => `
    <article class="capability-row ${connected ? "is-connected" : "is-discovered"}">
      <div class="capability-avatar" data-kind="${escapeHtml(capability.kind)}">${escapeHtml(capabilityAvatar(capability))}</div>
      <div class="capability-main">
        <div class="capability-title">
          <strong>${escapeHtml(capability.name)}</strong>
          <span class="capability-state ${connected ? "connected" : "discovered"}"><i></i>${connected ? "已连接" : "已发现"}</span>
        </div>
        <p>${escapeHtml(capabilitySummary(capability, connected))}</p>
        <div class="capability-meta">
          <span>${escapeHtml(capabilityKindLabel(capability.kind))}</span>
          <code>${escapeHtml(capability.id)}</code>
          ${capability.config && capability.config.version ? `<span>${escapeHtml(capability.config.version)}</span>` : ""}
        </div>
      </div>
      <div class="capability-row-actions">
        ${connected
          ? `<button class="quiet-button" data-probe-capability="${escapeHtml(capability.id)}">测试连接</button><button class="icon-button danger-icon" data-delete-capability="${escapeHtml(capability.id)}" title="删除能力" aria-label="删除 ${escapeHtml(capability.name)}">×</button>`
          : `<button class="primary-button compact-button" data-save-discovered-capability="${discoveredIndex}">连接</button>`}
      </div>
      ${capability.last_probe ? `<div class="capability-probe ${capability.last_probe.ok ? "ok" : "err"}">${escapeHtml(capability.last_probe.summary || "")}</div>` : ""}
      ${capabilityTechnicalDetails(capability)}
    </article>
  `).join("") : `
    <div class="capability-empty">
      <div class="capability-empty-mark">⌁</div>
      <strong>${allItems.length ? "没有匹配的能力" : "还没有连接本地能力"}</strong>
      <p>${allItems.length ? "调整搜索词或筛选条件。" : "先扫描本机 Agent CLI，或手动添加 CLI、MCP 和 HTTP。"}</p>
    </div>`;
}

function openCapabilityDrawer() {
  const drawer = $("capability-drawer");
  const backdrop = $("capability-drawer-backdrop");
  if (!drawer || !backdrop) return;
  backdrop.hidden = false;
  drawer.classList.add("open");
  drawer.setAttribute("aria-hidden", "false");
  document.body.classList.add("drawer-open");
  window.setTimeout(() => $("capability-kind").focus(), 80);
}

function closeCapabilityDrawer() {
  const drawer = $("capability-drawer");
  const backdrop = $("capability-drawer-backdrop");
  if (!drawer || !backdrop) return;
  drawer.classList.remove("open");
  drawer.setAttribute("aria-hidden", "true");
  backdrop.hidden = true;
  document.body.classList.remove("drawer-open");
  $("open-capability-drawer")?.focus();
}

function syncCapabilityForm() {
  const kind = $("capability-kind") ? $("capability-kind").value : "agent_cli";
  document.querySelectorAll(".capability-process-field").forEach((item) => { item.hidden = kind === "http"; });
  document.querySelectorAll(".capability-agent-field").forEach((item) => { item.hidden = kind !== "agent_cli"; });
  document.querySelectorAll(".capability-mcp-field").forEach((item) => { item.hidden = kind !== "mcp_stdio"; });
  document.querySelectorAll(".capability-http-field").forEach((item) => { item.hidden = kind !== "http"; });
}

function capabilityDraftFromForm() {
  const kind = $("capability-kind").value;
  const staticValue = JSON.parse($("capability-static").value || "{}");
  if (!staticValue || Array.isArray(staticValue) || typeof staticValue !== "object") throw new Error("Static arguments/body 必须是 JSON object");
  const draft = {
    id: $("capability-id").value.trim() || undefined,
    name: $("capability-name").value.trim(),
    kind,
    source: "manual",
    description: `User-added local ${kind} Capability.`,
    config: {},
  };
  if (kind === "http") {
    draft.config = {url: $("capability-url").value.trim(), method: $("capability-method").value, body: staticValue, context_key: "context"};
  } else {
    const args = JSON.parse($("capability-args").value || "[]");
    if (!Array.isArray(args)) throw new Error("Arguments 必须是 JSON array");
    draft.config = {executable: $("capability-executable").value.trim(), args};
    if (kind === "agent_cli") Object.assign(draft.config, {input_mode: $("capability-input-mode").value, output_format: "text"});
    if (kind === "mcp_stdio") Object.assign(draft.config, {tool: $("capability-tool").value.trim(), arguments: staticValue, context_key: "context"});
  }
  return draft;
}

async function discoverCapabilities() {
  const button = $("discover-capabilities");
  if (button) {
    button.disabled = true;
    button.textContent = "正在扫描…";
  }
  const result = await api("/api/v1/capabilities/discover", {method: "POST", body: "{}"});
  state.discoveredCapabilities = result.items || [];
  renderCapabilities();
  const available = capabilityLibraryItems().filter((item) => !item.connected).length;
  const scanMessage = $("capability-scan-message");
  if (scanMessage) scanMessage.textContent = `扫描完成：发现 ${state.discoveredCapabilities.length} 个，${available} 个待连接。`;
  if (button) {
    button.disabled = false;
    button.innerHTML = '<span aria-hidden="true">⌁</span> 重新扫描';
  }
}

async function validateCapabilityDraft() {
  const result = await api("/api/v1/capabilities/validate", {method: "POST", body: JSON.stringify({capability: capabilityDraftFromForm(), probe: true})});
  const probe = result.probe;
  setNotice("capability-message", probe && probe.ok ? `验证通过：${probe.summary}` : `合同有效，但探测失败：${probe ? probe.summary : "未探测"}`, probe && probe.ok ? "ok" : "err");
}

async function saveCapabilityDraft(draft = null) {
  const capability = await api("/api/v1/capabilities", {method: "POST", body: JSON.stringify({capability: draft || capabilityDraftFromForm()})});
  state.capabilities = [...state.capabilities.filter((item) => item.id !== capability.id), capability];
  renderCapabilities();
  const scanMessage = $("capability-scan-message");
  if (scanMessage) scanMessage.textContent = `已连接 ${capability.name}，现在可在 Canvas Node 中选择。`;
  if (!draft) closeCapabilityDrawer();
}

async function probeSavedCapability(capabilityId) {
  const capability = await api(`/api/v1/capabilities/${encodeURIComponent(capabilityId)}/probe`, {method: "POST", body: "{}"});
  state.capabilities = state.capabilities.map((item) => item.id === capability.id ? capability : item);
  renderCapabilities();
}

async function deleteSavedCapability(capabilityId) {
  if (!window.confirm(`删除能力 ${capabilityId}？被保存 Flow 引用时会拒绝删除。`)) return;
  await api(`/api/v1/capabilities/${encodeURIComponent(capabilityId)}`, {method: "DELETE"});
  state.capabilities = state.capabilities.filter((item) => item.id !== capabilityId);
  renderCapabilities();
}

function syncExecutorOptions() {
  const select = $("executor-select");
  if (!select) return;
  Array.from(select.options).forEach((option) => {
    const executor = state.executors.find((item) => item.id === option.value);
    option.disabled = executor ? !executor.available : option.value !== "deterministic";
    if (executor && !executor.available) option.textContent = `${option.textContent.replace(" (not installed)", "")} (not installed)`;
  });
  if (select.selectedOptions[0] && select.selectedOptions[0].disabled) select.value = "deterministic";
}

function saveActiveRunId(runId) {
  try {
    if (runId) window.localStorage.setItem(activeRunStorageKey, runId);
  } catch (_) {
    // Best-effort UI recovery only.
  }
}

function clearActiveRunId() {
  try {
    window.localStorage.removeItem(activeRunStorageKey);
  } catch (_) {
    // Best-effort UI recovery only.
  }
}

function readActiveRunId() {
  try {
    return window.localStorage.getItem(activeRunStorageKey);
  } catch (_) {
    return null;
  }
}

function rememberRun(run) {
  if (!run || !run.run_id) return;
  state.runs = [run, ...(state.runs || []).filter((item) => item.run_id !== run.run_id)].slice(0, 20);
  saveActiveRunId(run.run_id);
}

function restoreActiveRunFromHistory() {
  if (state.run) return;
  const activeRunId = readActiveRunId();
  const remembered = activeRunId ? (state.runs || []).find((run) => run.run_id === activeRunId) : null;
  state.run = remembered || (state.runs && state.runs.length ? state.runs[0] : null);
  state.task = null;
  if (state.run) {
    updateRuntimeCommand();
    if (!terminalRunStatuses.has(state.run.status)) startRunPolling(state.run.run_id);
  }
}

async function openRunFromHistory(runId) {
  stopRunPolling();
  const run = await api(`/api/flows/runs/${encodeURIComponent(runId)}`);
  state.run = run;
  state.task = null;
  state.repairResult = null;
  rememberRun(run);
  renderRun();
  renderRunHistory();
  renderHub();
  updateRuntimeCommand();
  if (!terminalRunStatuses.has(run.status)) startRunPolling(run.run_id);
  switchPage("runs");
  setNotice("run-message", `已加载 Run：${run.run_id}，状态 ${run.status}。页面会低频刷新状态。`, run.status === "failed" || run.status === "cancelled" ? "err" : "ok");
}

function renderTemplates() {
  const list = $("template-list");
  list.innerHTML = "";
  state.templates.forEach((template) => {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "template-card" + (template.template_id === state.selectedTemplateId ? " active" : "");
    card.dataset.templateId = template.template_id;
    const tags = (template.intent_tags || [])
      .slice(0, 4)
      .map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`)
      .join("");
    card.innerHTML = `
      <div class="template-title">
        <span>${escapeHtml(template.name)}</span>
        <span class="pill">任务</span>
      </div>
      <div class="template-desc">${escapeHtml(template.description)}</div>
      <div class="tag-row">${tags}</div>
    `;
    card.addEventListener("click", () => {
      state.selectedTemplateId = template.template_id;
      renderTemplates();
      applyTemplatePreset();
    });
    list.appendChild(card);
  });
}

function renderSavedFlows() {
  const list = $("saved-flow-list");
  list.innerHTML = "";
  renderHubSavedFlows();
  if (!state.savedFlows.length) {
    const empty = document.createElement("div");
    empty.className = "notice";
    empty.textContent = "还没有保存的 Flow。";
    list.appendChild(empty);
    return;
  }
  state.savedFlows.forEach((saved) => {
    const card = document.createElement("div");
    card.className = "saved-flow-card" + (saved.flow_id === state.currentSavedFlowId ? " active" : "");
    card.dataset.flowId = saved.flow_id;
    card.innerHTML = `
      <div class="template-title">
        <span>${escapeHtml(saved.name)}</span>
        <span class="pill">${escapeHtml(saved.flow_id)}</span>
      </div>
      <div class="template-desc">${escapeHtml(saved.description || "无描述")}</div>
      <div class="node-meta">${escapeHtml(saved.template_id || "custom")} · ${escapeHtml(formatDate(saved.updated_at))}</div>
      <div class="saved-flow-actions">
        <button type="button" data-open-flow="${escapeHtml(saved.flow_id)}">打开编辑</button>
        <button type="button" class="danger-button" data-delete-flow="${escapeHtml(saved.flow_id)}">删除</button>
      </div>
    `;
    list.appendChild(card);
  });
  renderHub();
  renderTemplateAdmin();
}

function renderTemplateAdmin() {
  renderOfficialTemplates();
  renderMyTemplateCandidates();
}

function renderOfficialTemplates() {
  const list = $("official-template-list");
  if (!list) return;
  list.innerHTML = "";
  const count = $("official-template-count");
  if (count) count.textContent = String(state.templates.length || 0);
  if (!state.templates.length) {
    const empty = document.createElement("div");
    empty.className = "notice";
    empty.textContent = "还没有加载到官方模板。";
    list.appendChild(empty);
    return;
  }
  state.templates.forEach((template) => {
    const card = document.createElement("div");
    card.className = "template-admin-card";
    const tags = (template.intent_tags || [])
      .slice(0, 5)
      .map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`)
      .join("");
    const slots = (template.slots || [])
      .map((slot) => `
        <div class="slot-row">
          <span>${escapeHtml(slot.name || slot.id)}</span>
          <strong>${escapeHtml(slot.required ? "必填" : "可选")} · ${escapeHtml(slot.type || "string")}</strong>
        </div>
      `)
      .join("");
    card.innerHTML = `
      <div class="template-title">
        <span>${escapeHtml(template.name)}</span>
        <span class="pill ok">官方</span>
      </div>
      <div class="template-desc">${escapeHtml(template.description || "无描述")}</div>
      <div class="node-meta">${escapeHtml(template.template_id)}</div>
      <div class="tag-row">${tags}</div>
      <div class="slot-list">${slots || '<div class="slot-row"><span>无槽位</span><strong>-</strong></div>'}</div>
      <div class="button-row">
        <button class="ghost-button" data-template-new="${escapeHtml(template.template_id)}">使用模板</button>
      </div>
    `;
    list.appendChild(card);
  });
}

function renderMyTemplateCandidates() {
  const list = $("my-template-list");
  if (!list) return;
  list.innerHTML = "";
  const count = $("my-template-count");
  if (count) count.textContent = String(state.savedFlows.length || 0);
  if (!state.savedFlows.length) {
    const empty = document.createElement("div");
    empty.className = "notice";
    empty.textContent = "还没有可沉淀的保存 Flow。先跑通一个稳定 Flow，再把它作为自有模板候选。";
    list.appendChild(empty);
    return;
  }
  state.savedFlows.forEach((saved) => {
    const stepCount = saved.flow && Array.isArray(saved.flow.steps) ? saved.flow.steps.length : 0;
    const nodeTypes = saved.flow && Array.isArray(saved.flow.steps)
      ? [...new Set(saved.flow.steps.map((step) => step.type).filter(Boolean))].slice(0, 4)
      : [];
    const tags = nodeTypes.map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`).join("");
    const card = document.createElement("div");
    card.className = "template-admin-card";
    card.innerHTML = `
      <div class="template-title">
        <span>${escapeHtml(saved.name)}</span>
        <span class="pill warn">候选</span>
      </div>
      <div class="template-desc">${escapeHtml(saved.description || "无描述")}</div>
      <div class="node-meta">${escapeHtml(saved.flow_id)} · ${escapeHtml(saved.template_id || "custom")} · ${escapeHtml(formatDate(saved.updated_at))}</div>
      <div class="tag-row">${tags}</div>
      <div class="slot-list">
        <div class="slot-row"><span>节点数</span><strong>${escapeHtml(stepCount)}</strong></div>
        <div class="slot-row"><span>来源</span><strong>保存 Flow</strong></div>
        <div class="slot-row"><span>发布状态</span><strong>未清洗</strong></div>
      </div>
      <div class="button-row">
        <button class="ghost-button" data-template-flow="${escapeHtml(saved.flow_id)}">打开 Flow</button>
      </div>
    `;
    list.appendChild(card);
  });
}

function renderHub() {
  renderHubSavedFlows();
  renderHubRunSummary();
  const optimizeFlowCount = $("optimize-flow-count");
  if (optimizeFlowCount) optimizeFlowCount.textContent = String(state.savedFlows.length || 0);
  const optimizeRunStatus = $("optimize-run-status");
  if (optimizeRunStatus) optimizeRunStatus.textContent = state.run ? state.run.status : "-";
  const optimizeRepairStatus = $("optimize-repair-status");
  if (optimizeRepairStatus) {
    const failed = failedRunStep();
    optimizeRepairStatus.textContent = state.repairResult
      ? (state.repairResult.ai_patch && state.repairResult.ai_patch.status) || "returned"
      : failed ? "待修复" : "-";
  }
}

function renderHubSavedFlows() {
  const list = $("hub-saved-flow-list");
  if (!list) return;
  list.innerHTML = "";
  const flows = (state.savedFlows || []).slice(0, 4);
  if (!flows.length) {
    const empty = document.createElement("div");
    empty.className = "notice";
    empty.textContent = "还没有保存的 Flow。可以先从新建 Flow 开始。";
    list.appendChild(empty);
    return;
  }
  flows.forEach((saved) => {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "saved-flow-card compact";
    card.innerHTML = `
      <div class="template-title">
        <span>${escapeHtml(saved.name)}</span>
        <span class="pill">${escapeHtml(saved.template_id || "custom")}</span>
      </div>
      <div class="template-desc">${escapeHtml(saved.description || "无描述")}</div>
      <div class="node-meta">${escapeHtml(saved.flow_id)} · ${escapeHtml(formatDate(saved.updated_at))}</div>
    `;
    card.addEventListener("click", () => guarded(() => openSavedFlow(saved.flow_id)));
    list.appendChild(card);
  });
}

function renderHubRunSummary() {
  const container = $("hub-run-summary");
  if (!container) return;
  if (!state.run) {
    container.innerHTML = `
      <div class="notice">当前没有运行。选择一个保存 Flow 或新建 Flow 后即可创建 Run。</div>
      <div class="hub-metrics">
        <div><span>模板</span><strong>${escapeHtml(state.templates.length || 0)}</strong></div>
        <div><span>保存 Flow</span><strong>${escapeHtml(state.savedFlows.length || 0)}</strong></div>
        <div><span>节点</span><strong>${escapeHtml(state.nodes.length || 0)}</strong></div>
      </div>
    `;
    return;
  }
  const report = findMarkdownReport(state.run);
  const failed = failedRunStep();
  container.innerHTML = `
    <div class="hub-run-card ${escapeHtml(state.run.status)}">
      <div>
        <span>Run ID</span>
        <strong>${escapeHtml(state.run.run_id)}</strong>
      </div>
      <div>
        <span>状态</span>
        <strong><span class="pill ${pillKind(state.run.status)}">${escapeHtml(state.run.status)}</span></strong>
      </div>
      <div>
        <span>下一步</span>
        <strong>${escapeHtml(nextTaskLabel())}</strong>
      </div>
      <div>
        <span>结果</span>
        <strong>${report ? "报告已生成" : failed ? "待修复" : "运行中"}</strong>
      </div>
    </div>
    <div class="button-row">
      <button class="ghost-button hub-action-inline" data-target-page="runs">查看运行</button>
      ${report ? `<a class="report-link" href="${report.href}" target="_blank" rel="noreferrer">打开报告</a>` : ""}
    </div>
  `;
}

function applyTemplatePreset() {
  const preset = templatePresets[state.selectedTemplateId] || {};
  if (preset.request) $("user-request").value = preset.request;
  $("supplemental-materials").value = preset.materials || "";
  $("target-url").value = preset.targetUrl || "";
  $("target-url").disabled = targetUrlsTemplates.has(state.selectedTemplateId) || inquiryTextTemplates.has(state.selectedTemplateId);
  $("target-urls").value = preset.targetUrls || "";
  $("target-urls").disabled = !targetUrlsTemplates.has(state.selectedTemplateId);
  $("inquiry-text").value = preset.inquiryText || "";
  $("inquiry-text").disabled = !inquiryTextTemplates.has(state.selectedTemplateId);
  $("keyword").value = preset.keyword || "";
  $("keyword").disabled = !keywordTemplates.has(state.selectedTemplateId);
  $("max-pages").value = preset.maxPages || 2;
  $("max-pages").disabled = Boolean(preset.maxPagesDisabled);
}

function flowInputDefault(flow, key) {
  const spec = flow && flow.inputs ? flow.inputs[key] : null;
  if (!spec || !Object.prototype.hasOwnProperty.call(spec, "default") || spec.default === null) {
    return null;
  }
  return spec.default;
}

function hydrateInputsFromFlow(flow) {
  const targetUrl = flowInputDefault(flow, "target_url") || "";
  const targetUrls = flowInputDefault(flow, "target_urls") || [];
  const inquiryText = flowInputDefault(flow, "inquiry_text") || "";
  const keyword = flowInputDefault(flow, "keyword") || "";
  const maxPages = flowInputDefault(flow, "max_pages") || 2;
  const reportFocus = flowInputDefault(flow, "report_focus") || flow.description || "";
  $("target-url").value = targetUrl;
  $("target-urls").value = Array.isArray(targetUrls) ? targetUrls.join("\n") : String(targetUrls || "");
  $("inquiry-text").value = inquiryText;
  $("keyword").value = keyword;
  $("max-pages").value = maxPages;
  $("user-request").value = reportFocus;
  if (inquiryTextTemplates.has(state.selectedTemplateId)) {
    $("supplemental-materials").value = inquiryText;
  } else if (targetUrlsTemplates.has(state.selectedTemplateId)) {
    $("supplemental-materials").value = $("target-urls").value;
  } else if (keywordTemplates.has(state.selectedTemplateId)) {
    $("supplemental-materials").value = keyword;
  } else {
    $("supplemental-materials").value = targetUrl;
  }
  $("target-url").disabled = targetUrlsTemplates.has(state.selectedTemplateId) || inquiryTextTemplates.has(state.selectedTemplateId);
  $("target-urls").disabled = !targetUrlsTemplates.has(state.selectedTemplateId);
  $("inquiry-text").disabled = !inquiryTextTemplates.has(state.selectedTemplateId);
  $("keyword").disabled = !keywordTemplates.has(state.selectedTemplateId);
  $("max-pages").disabled = Boolean(templatePresets[state.selectedTemplateId] && templatePresets[state.selectedTemplateId].maxPagesDisabled);
}

async function draftFlow() {
  if (!state.selectedTemplateId) throw new Error("请先选择模板");
  syncLegacyInputsFromMaterials();
  startGenerationProgress();
  setNotice("input-message", "正在生成并保存 Flow，请稍等。");
  const targetUrls = parseTargetUrls($("target-urls").value);
  const payload = {
    template_id: state.selectedTemplateId,
    user_request: $("user-request").value,
    target_url: $("target-url").value || null,
    target_urls: targetUrlsTemplates.has(state.selectedTemplateId) ? targetUrls : [],
    inquiry_text: inquiryTextTemplates.has(state.selectedTemplateId) ? $("inquiry-text").value : null,
    keyword: $("keyword").value || null,
    max_pages: Number($("max-pages").value || 2),
    report_focus: reportFocusTemplates.has(state.selectedTemplateId) ? $("user-request").value : null,
    mode: $("mode").value,
  };
  const result = await api("/api/flows/draft", {method: "POST", body: JSON.stringify(payload)});
  stopGenerationProgress({success: true});
  state.aiEditResult = null;
  state.repairResult = null;
  state.plan = result.plan;
  setFlow(result.flow_dsl);
  renderPlan(result.plan);
  let saved = null;
  if (result.validation && result.validation.valid) {
    saved = await api("/api/flows", {
      method: "POST",
      body: JSON.stringify({flow: result.flow_dsl, template_id: state.selectedTemplateId}),
    });
    state.currentSavedFlowId = saved.flow_id;
    await loadSavedFlows();
  } else {
    state.currentSavedFlowId = null;
    renderSavedFlows();
  }
  renderAiEditResult();
  renderRepairResult();
  renderHub();
  switchPage("flows");
  const missing = (result.missing_slots || []).length ? `缺少任务材料：${result.missing_slots.join(", ")}` : "任务材料已填齐";
  setNotice(
    "input-message",
    saved
      ? `${result.template_name || result.template_id}\n${missing}，已保存到我的 Flow：${saved.flow_id}`
      : `${result.template_name || result.template_id}\n${missing}`,
    result.validation.valid ? "ok" : "err",
  );
  setNotice(
    "validation-message",
    saved
      ? `Flow 已生成、校验通过并保存：${saved.flow_id}`
      : result.validation.valid ? "Draft 校验通过。" : JSON.stringify(result.validation, null, 2),
    result.validation.valid ? "ok" : "err",
  );
}

function setFlow(flow) {
  state.flow = flow;
  state.selectedStepId = flow.steps && flow.steps.length ? flow.steps[0].id : null;
  $("flow-json").value = JSON.stringify(flow, null, 2);
  $("flow-name").textContent = flow.name || flow.id || "未命名 Flow";
  $("flow-desc").textContent = flow.description || "无描述";
  $("flow-status").textContent = flow.execution && flow.execution.mode ? flow.execution.mode : "draft";
  renderCanvas(flow, null);
  renderHub();
}

function clearFlowView() {
  state.flow = null;
  state.plan = null;
  state.run = null;
  state.task = null;
  state.currentSavedFlowId = null;
  state.selectedStepId = null;
  $("flow-json").value = "";
  $("flow-name").textContent = "等待生成 Flow";
  $("flow-desc").textContent = "从模板、自然语言或 DSL 创建一个任务 Flow。";
  $("flow-status").textContent = "draft";
  renderCanvas(null, null);
  renderPlan(null);
  renderNodeDetail();
  renderHub();
}

function currentFlow() {
  const text = $("flow-json").value.trim();
  if (!text) throw new Error("Flow DSL 为空");
  return JSON.parse(text);
}

function cloneValue(value) {
  return value == null ? value : JSON.parse(JSON.stringify(value));
}

async function setFlowFromCanvas(nextFlow, reason = "canvas-edit") {
  state.flow = nextFlow;
  if (!state.selectedStepId && nextFlow.steps && nextFlow.steps.length) {
    state.selectedStepId = nextFlow.steps[0].id;
  }
  $("flow-json").value = JSON.stringify(nextFlow, null, 2);
  $("flow-name").textContent = nextFlow.name || nextFlow.id || "未命名 Flow";
  $("flow-desc").textContent = nextFlow.description || "无描述";
  $("flow-status").textContent = nextFlow.execution && nextFlow.execution.mode ? nextFlow.execution.mode : "draft";
  renderNodeDetail();
  renderHub();
  updateDevSummary();
  window.dispatchEvent(new CustomEvent("flow-console:flow-updated", {detail: {flow: nextFlow, reason}}));
  if (nextFlow.steps && nextFlow.steps.length) {
    await refreshPlanForFlow(nextFlow, {silent: true});
  } else {
    state.plan = null;
    renderPlan(null);
  }
}

function initFlowCanvasBridge() {
  window.flowCanvasBridge = {
    getFlow: () => cloneValue(state.flow),
    setFlow: (nextFlow, reason) => guarded(() => setFlowFromCanvas(nextFlow, reason)),
    getPlan: () => cloneValue(state.plan),
    getRun: () => cloneValue(state.run),
    selectStep: (stepId) => {
      state.selectedStepId = stepId;
      renderNodeDetail();
    },
    openNodeInspector: (stepId) => {
      state.selectedStepId = stepId;
      renderNodeDetail();
    },
    validateFlow: () => guarded(validateFlow),
    renderPlan: () => guarded(renderFlowPlan),
    createStep: (kind, dependency) => cloneValue(defaultStepForKind(state.flow || newBlankFlow(), kind, dependency)),
    addNode: (kind, options) => guarded(() => addNodeToCurrentFlow(kind, options || {})),
  };
}

function newBlankFlow() {
  const stamp = new Date().toISOString().slice(0, 19).replace(/[-:T]/g, "");
  return {
    schema_version: 1,
    id: `custom_prompt_flow_${stamp}`,
    name: "未命名空白 Flow",
    description: "从空白画布手动搭建的 Prompt Node Flow。",
    execution: {
      mode: "semi_auto",
      default_blocking: true,
      stop_on_error: false,
      require_confirm_before: [],
      session_policy: {default: "flow_session", groups: []},
    },
    inputs: {},
    steps: [],
    outputs: {},
  };
}

async function openBlankFlow() {
  stopRunPolling();
  state.currentSavedFlowId = null;
  state.selectedTemplateId = null;
  state.aiEditResult = null;
  state.repairResult = null;
  state.run = null;
  state.task = null;
  state.plan = null;
  setFlow(newBlankFlow());
  renderPlan(null);
  renderAiEditResult();
  renderRepairResult();
  renderRun();
  renderSavedFlows();
  switchPage("flows");
  switchTab("plan");
  setNotice("validation-message", "已创建未保存的空白 Flow。请添加节点后保存。", "ok");
}

function renderCanvas(flow, run = null) {
  const canvas = $("canvas-content");
  canvas.className = "xy-canvas-host";
  window.dispatchEvent(new CustomEvent("flow-console:flow-updated", {detail: {flow, run}}));
  renderNodeDetail();
}

function createFlowCard(flow, step, index, status, totalSteps) {
  const promptNode = planStepFor(step.id);
  const sessionGroup = sessionGroupForStep(flow, step.id);
  const branchLabel = branchConditionLabel(step);
  const loopStep = isLoopStep(step);
  const nodeSummary = step.type === "rpa.local_cli.run_app"
    ? `应用：${(step.params && step.params.app_name) || "未选择"}`
    : step.type === "flow.if"
      ? `判断：${(step.params && (step.params.question || step.params.condition)) || "未配置"}`
      : (promptNode.prompt || step.prompt || `内部步骤：${step.type}`);
  const node = document.createElement("div");
  node.className = `flow-card${status ? ` ${status}` : ""}${step.id === state.selectedStepId ? " selected" : ""}${branchLabel ? ` branch-${branchLabel}` : ""}${loopStep ? " loop-step" : ""}`;
  node.dataset.stepId = step.id;
  node.innerHTML = `
    <div class="node-top">
      <span class="node-badge">${index + 1}</span>
      <span class="node-order-controls">
        <button type="button" data-move-node="${escapeHtml(step.id)}" data-direction="up" title="上移" aria-label="上移"${index === 0 ? " disabled" : ""}>↑</button>
        <button type="button" data-move-node="${escapeHtml(step.id)}" data-direction="down" title="下移" aria-label="下移"${index === totalSteps - 1 ? " disabled" : ""}>↓</button>
      </span>
      ${loopStep ? `<span class="loop-marker" title="循环路径">↻</span>` : ""}
      ${status ? `<span class="pill ${pillKind(status)}">${escapeHtml(status)}</span>` : ""}
    </div>
    <div class="node-body">
      <div class="node-id">${escapeHtml(promptNode.title || step.id)}</div>
      <div class="node-type">${escapeHtml(promptNode.stage || "执行任务")} · ${escapeHtml(nodeKindLabel(promptNode.node_kind, step.type))}</div>
      ${branchLabel ? `<div class="node-branch">分支：${escapeHtml(branchLabel)}</div>` : ""}
      ${sessionGroup ? `<div class="node-session">会话：${escapeHtml(sessionGroup)}</div>` : ""}
      <div class="node-meta">${escapeHtml(nodeSummary)}</div>
    </div>
  `;
  node.addEventListener("click", (event) => {
    if (event.target instanceof Element && event.target.closest("[data-move-node]")) return;
    selectFlowStep(step.id);
  });
  return node;
}

function branchChildrenForStep(steps, stepId) {
  const children = steps.filter((step) => dependenciesForStep(step).includes(stepId));
  return {
    trueStep: children.find((step) => branchConditionLabel(step) === "true") || null,
    falseStep: children.find((step) => branchConditionLabel(step) === "false") || null,
  };
}

function branchConditionLabel(step) {
  const when = String(step.when || "");
  if (!when.includes(".output.condition_met")) return "";
  if (when.includes("== true") || when.includes("!= false")) return "true";
  if (when.includes("== false") || when.includes("!= true")) return "false";
  return "";
}

function isLoopStep(step) {
  const when = String(step.when || "");
  return Boolean(
    when.includes("has_reply != true")
    || /^run_local_cli_\d+$/.test(step.id || "")
    || /^recognize_reply_\d+$/.test(step.id || "")
    || /^wait_reply_\d+$/.test(step.id || "")
  );
}

function selectFlowStep(stepId) {
  state.selectedStepId = stepId;
  if (state.flow) renderCanvas(state.flow, null);
}

function renderNodeDetail() {
  const detail = $("node-detail");
  const steps = state.flow && Array.isArray(state.flow.steps) ? state.flow.steps : [];
  const step = steps.find((item) => item.id === state.selectedStepId) || steps[0];
  if (!step) {
    detail.className = "node-detail empty";
    detail.textContent = "未选择节点";
    return;
  }
  const runStep = state.activePage === "runs" && state.run && Array.isArray(state.run.steps)
    ? state.run.steps.find((item) => item.step_id === step.id)
    : null;
  const dependencies = step.from || step.depends_on || "start";
  const promptNode = planStepFor(step.id);
  const isRpaNode = promptNode.node_kind === "rpa" || step.type === "rpa.local_cli.run_app";
  const isIfNode = step.type === "flow.if";
  const isSleepNode = step.type === "time.sleep";
  const isAgentNode = promptNode.node_kind === "agent" || step.type === "agent.task";
  const isCapabilityNode = step.type === "capability.task";
  const isPromptOnlyNode = isAgentNode || promptNode.node_kind === "llm";
  const promptTitle = promptDetailTitle(promptNode.node_kind);
  const promptText = step.prompt || promptNode.prompt || "请执行这个节点对应的低风险任务。";
  const activeSessionGroup = sessionGroupForStep(state.flow, step.id);
  const sessionOptions = sessionGroupOptions(activeSessionGroup);
  const sessionEditor = isAgentNode ? `
    <div class="detail-row prompt-detail-row">
      <span>归属会话</span>
      <input id="node-session-group-editor" class="node-text-editor" list="session-group-options" value="${escapeHtml(activeSessionGroup)}" placeholder="例如：worker_loop；留空则每个节点独立会话" />
      <datalist id="session-group-options">
        ${sessionOptions.map((group) => `<option value="${escapeHtml(group)}"></option>`).join("")}
      </datalist>
      <small>仅 session-capable Agent 支持复用；同组节点在 Run 证据中必须显示相同 conversation ref，否则运行前校验失败。</small>
    </div>
  ` : "";
  const compatibleCapabilities = state.capabilities.filter((capability) => isAgentNode ? capability.kind === "agent_cli" : isCapabilityNode ? capability.kind !== "agent_cli" : false);
  const selectedCapabilityId = step.params && step.params.capability_id ? step.params.capability_id : "";
  const capabilityEditor = (isAgentNode || isCapabilityNode) ? `
    <div class="detail-row prompt-detail-row">
      <span>${isAgentNode ? "Agent 执行者" : "Node 能力"}</span>
      <select id="node-capability-editor" class="node-text-editor">
        ${isAgentNode ? '<option value="">Run 默认 Agent</option>' : '<option value="">请选择已保存能力</option>'}
        ${compatibleCapabilities.map((capability) => `<option value="${escapeHtml(capability.id)}" ${capability.id === selectedCapabilityId ? "selected" : ""}>${escapeHtml(capability.name)} · ${escapeHtml(capability.kind)}</option>`).join("")}
      </select>
      <small>${compatibleCapabilities.length ? "保存后会固定 Capability fingerprint；Run 时间线记录真实 executor identity 和 effects。" : "请先到“能力”页面发现或添加可用能力。"}</small>
    </div>
  ` : "";
  const primaryEditor = isRpaNode ? `
    <div class="detail-row prompt-detail-row">
      <span>应用名</span>
      <input id="local_cli-app-name-editor" class="node-text-editor" value="${escapeHtml((step.params && step.params.app_name) || "")}" placeholder="例如：钉钉截图" />
      <small>${escapeHtml(promptRuntimeHint(promptNode.node_kind))}</small>
      <div class="inline-actions">
        <button type="button" class="primary-button" id="apply-node-edits">应用节点修改</button>
      </div>
    </div>
  ` : isIfNode ? `
    <div class="detail-row prompt-detail-row">
      <span>判断问题</span>
      <textarea id="flow-if-question-editor" class="node-prompt-editor" placeholder="例如：上游识别结果是否显示钉钉群里已有新回复？">${escapeHtml((step.params && (step.params.question || step.params.condition)) || "")}</textarea>
      <small>运行时会把上游输出交给我们的 LLM，并用 system prompt 强制返回 true/false。</small>
      <div class="inline-actions">
        <button type="button" class="primary-button" id="apply-node-edits">应用节点修改</button>
      </div>
    </div>
  ` : isSleepNode ? `
    <div class="detail-row prompt-detail-row">
      <span>等待设置</span>
      <input id="sleep-seconds-editor" class="node-text-editor" type="number" min="1" max="3600" value="${escapeHtml((step.params && step.params.seconds) || 10)}" />
      <textarea id="sleep-reason-editor" class="node-prompt-editor" placeholder="等待原因">${escapeHtml((step.params && step.params.reason) || "")}</textarea>
      <small>等待节点由后端执行，不连接本地监视器。</small>
      <div class="inline-actions">
        <button type="button" class="primary-button" id="apply-node-edits">应用节点修改</button>
      </div>
    </div>
  ` : `
    <div class="detail-row prompt-detail-row">
      <span>${escapeHtml(promptTitle)}</span>
      <textarea id="node-prompt-editor" class="node-prompt-editor">${escapeHtml(promptText)}</textarea>
      <small>${escapeHtml(promptRuntimeHint(promptNode.node_kind))}</small>
      <div class="inline-actions">
        <button type="button" class="primary-button" id="apply-node-edits">应用节点修改</button>
      </div>
    </div>
  `;
  const insertActions = state.flow ? `
    <div class="detail-row node-insert-row">
      <span>从此节点后添加</span>
      <div class="mini-node-actions">
        <button type="button" class="ghost-button" data-add-node-after="agent" data-after-step="${escapeHtml(step.id)}">Agent</button>
        <button type="button" class="ghost-button" data-add-node-after="capability" data-after-step="${escapeHtml(step.id)}">Capability</button>
        <button type="button" class="ghost-button" data-add-node-after="end" data-after-step="${escapeHtml(step.id)}">结束</button>
      </div>
      <small>Local Alpha 先支持一条可真实运行、可恢复的线性链路；分支会在校验阶段明确拒绝。</small>
    </div>
  ` : "";
  const technicalDetails = isPromptOnlyNode ? "" : `
    <div class="detail-row">
      <span>上游任务</span>
      <code>${escapeHtml(Array.isArray(dependencies) ? dependencies.join(", ") : dependencies)}</code>
    </div>
    <div class="detail-row">
      <span>完成条件</span>
      <code>${escapeHtml(completionSummary(step.completion_policy))}</code>
    </div>
    <div class="detail-row">
      <span>内部实现</span>
      <code>${escapeHtml(step.type)}</code>
    </div>
    <details class="internal-detail">
      <summary>内部参数</summary>
      <pre class="param-block">${escapeHtml(JSON.stringify(step.params || {}, null, 2))}</pre>
    </details>
  `;
  detail.className = "node-detail";
  detail.innerHTML = `
    <div class="detail-row">
      <span>任务节点</span>
      <strong>${escapeHtml(promptNode.title || step.id)}</strong>
    </div>
    <div class="detail-row">
      <span>业务步骤</span>
      <strong>${escapeHtml(promptNode.stage || "执行任务")} · ${escapeHtml(nodeKindLabel(promptNode.node_kind, step.type))}</strong>
    </div>
    ${runStep ? `
      <div class="detail-row">
        <span>状态</span>
        <strong><span class="pill ${pillKind(runStep.status)}">${escapeHtml(runStep.status)}</span></strong>
      </div>
      ${runStep.session ? `
        <div class="detail-row">
          <span>Agent 对话</span>
          <code>${escapeHtml(runStep.session.session_group)} / ${escapeHtml(runStep.session.conversation_ref)}</code>
          <small>Turn: ${escapeHtml(runStep.session.turn_ref)}${runStep.session.reused ? " · 已复用" : " · 首次绑定"}</small>
        </div>
      ` : ""}
    ` : ""}
    ${primaryEditor}
    ${capabilityEditor}
    ${sessionEditor}
    ${insertActions}
    ${technicalDetails}
  `;
}

function renderPlan(plan) {
  const planTab = $("plan-tab");
  planTab.innerHTML = "";
  const list = document.createElement("div");
  list.className = "plan-list";
  if (!plan || !Array.isArray(plan.steps)) {
    list.innerHTML = '<div class="notice">等待计划。</div>';
    planTab.appendChild(list);
    return;
  }
  plan.steps.forEach((step, index) => {
    const item = document.createElement("div");
    item.className = "plan-item";
    item.innerHTML = `
      <strong>${index + 1}. ${escapeHtml(step.title)}</strong>
      <span class="plan-stage">${escapeHtml(step.stage || "执行任务")} · ${escapeHtml(nodeKindLabel(step.node_kind))}</span>
      <p>${escapeHtml(step.prompt || step.completion)}</p>
      <span>${escapeHtml(step.node_type)} / ${escapeHtml(step.completion)}</span>
    `;
    list.appendChild(item);
  });
  planTab.appendChild(list);
}

async function aiEditFlow() {
  const flow = currentFlow();
  const editRequest = $("ai-edit-request").value.trim();
  if (!editRequest) throw new Error("请先输入编辑意图");
  setNotice("ai-edit-message", "正在生成 AI 候选修改...");
  const result = await api("/api/flows/ai-edit", {
    method: "POST",
    body: JSON.stringify({
      flow,
      template_id: state.selectedTemplateId,
      user_request: $("user-request").value || null,
      edit_request: editRequest,
      include_case_retrieval: true,
    }),
  });
  state.aiEditResult = result;
  renderAiEditResult();
  const valid = result.candidate_validation && result.candidate_validation.valid;
  setNotice(
    "ai-edit-message",
    valid ? "AI 候选已生成并通过校验。" : aiPatchSummary(result),
    valid ? "ok" : result.ai_patch && result.ai_patch.status === "failed" ? "err" : "warn",
  );
  switchTab("ai-edit");
}

function renderAiEditResult() {
  const container = $("ai-edit-result");
  if (!container) return;
  const applyButton = $("apply-ai-candidate");
  if (!state.aiEditResult) {
    container.innerHTML = "";
    if (applyButton) applyButton.disabled = true;
    return;
  }
  const result = state.aiEditResult;
  const patch = result.ai_patch || {};
  const candidateValid = result.candidate_validation && result.candidate_validation.valid;
  if (applyButton) applyButton.disabled = !candidateValid || !result.candidate_flow_dsl;
  const caseUsage = Array.isArray(patch.case_usage) && patch.case_usage.length
    ? patch.case_usage.map((item) => `<li>${escapeHtml(item)}</li>`).join("")
    : "<li>未使用或未返回 case usage。</li>";
  const patches = Array.isArray(patch.patches) && patch.patches.length
    ? patch.patches.map((item) => `
        <li>
          <strong>${escapeHtml(item.operation || "patch")}</strong>
          <span>${escapeHtml(item.target_step_id || "flow")}</span>
          <p>${escapeHtml(item.reason || "")}</p>
        </li>
      `).join("")
    : "<li>当前没有可应用 patch；可能需要更多信息或 LLM patch 未开启。</li>";
  const candidateSteps = result.candidate_plan && Array.isArray(result.candidate_plan.steps)
    ? result.candidate_plan.steps.map((step, index) => `
        <div class="mini-plan-item">
          <strong>${index + 1}. ${escapeHtml(step.title)}</strong>
          <span>${escapeHtml(step.stage || "执行任务")} · ${escapeHtml(nodeKindLabel(step.node_kind))}</span>
        </div>
      `).join("")
    : '<div class="notice">暂无候选计划。</div>';
  const errors = result.candidate_validation && Array.isArray(result.candidate_validation.errors)
    ? result.candidate_validation.errors.map((item) => `<li>${escapeHtml(item.code)}: ${escapeHtml(item.message)}</li>`).join("")
    : "";
  container.innerHTML = `
    <div class="ai-edit-summary">
      <div>
        <span>Patch 状态</span>
        <strong><span class="pill ${pillKind(patch.status)}">${escapeHtml(patch.status || "unknown")}</span></strong>
      </div>
      <div>
        <span>决策</span>
        <strong>${escapeHtml(patch.decision || "-")}</strong>
      </div>
      <div>
        <span>候选校验</span>
        <strong><span class="pill ${candidateValid ? "ok" : "warn"}">${candidateValid ? "valid" : "not ready"}</span></strong>
      </div>
    </div>
    <div class="ai-edit-section">
      <strong>说明</strong>
      <p>${escapeHtml(patch.rationale || patch.reason || result.explanation || "暂无说明。")}</p>
    </div>
    <div class="ai-edit-grid">
      <div class="ai-edit-section">
        <strong>候选修改</strong>
        <ul>${patches}</ul>
      </div>
      <div class="ai-edit-section">
        <strong>Case 使用</strong>
        <ul>${caseUsage}</ul>
      </div>
    </div>
    ${errors ? `<div class="ai-edit-section err"><strong>校验问题</strong><ul>${errors}</ul></div>` : ""}
    <div class="ai-edit-section">
      <strong>候选计划</strong>
      <div class="mini-plan-list">${candidateSteps}</div>
    </div>
  `;
}

async function suggestRunRepair() {
  if (!state.run) throw new Error("尚未创建 Run");
  const failedStep = failedRunStep();
  if (!failedStep) throw new Error("当前 Run 没有失败节点");
  setNotice("run-message", "正在生成修复候选...");
  const result = await api(`/api/flows/runs/${encodeURIComponent(state.run.run_id)}/repair-suggest`, {
    method: "POST",
    body: JSON.stringify({
      failed_step_id: failedStep.step_id,
      template_id: state.selectedTemplateId,
      user_request: $("user-request").value || null,
      repair_request: `修复失败节点 ${failedStep.step_id}，优先给出安全降级或局部 Flow patch。`,
      include_case_retrieval: true,
    }),
  });
  state.repairResult = result;
  renderRepairResult();
  const valid = result.candidate_validation && result.candidate_validation.valid;
  setNotice(
    "run-message",
    valid ? "修复候选已生成并通过校验。" : aiPatchSummary(result),
    valid ? "ok" : result.ai_patch && result.ai_patch.status === "failed" ? "err" : "warn",
  );
}

function renderRepairResult() {
  const card = $("repair-card");
  if (!card) return;
  const title = $("repair-title");
  const body = $("repair-body");
  const status = $("repair-status");
  const suggestButton = $("suggest-repair");
  const applyButton = $("apply-repair-candidate");
  const container = $("repair-result");
  const failedStep = failedRunStep();
  const canSuggest = Boolean(state.run && failedStep);
  suggestButton.disabled = !canSuggest;
  if (!state.repairResult) {
    card.className = "repair-card" + (canSuggest ? " ready" : "");
    title.textContent = canSuggest ? `失败节点：${failedStep.step_id}` : "等待失败节点";
    body.textContent = canSuggest ? "可生成候选修复。" : "Run 失败后可生成候选修复。";
    status.textContent = canSuggest ? "ready" : "idle";
    status.className = "pill" + (canSuggest ? " warn" : "");
    applyButton.disabled = true;
    container.innerHTML = "";
    return;
  }
  const result = state.repairResult;
  const patch = result.ai_patch || {};
  const candidateValid = result.candidate_validation && result.candidate_validation.valid;
  card.className = "repair-card ready";
  title.textContent = `候选修复：${result.failed_step_id || (failedStep && failedStep.step_id) || "-"}`;
  body.textContent = patch.rationale || patch.reason || result.explanation || "修复候选已返回。";
  status.textContent = patch.status || "unknown";
  status.className = `pill ${pillKind(patch.status)}${candidateValid ? " ok" : ""}`;
  applyButton.disabled = !candidateValid || !result.candidate_flow_dsl;
  container.innerHTML = candidateResultHtml(result, "暂无修复候选计划。");
}

function candidateResultHtml(result, emptyPlanText) {
  const patch = result.ai_patch || {};
  const candidateValid = result.candidate_validation && result.candidate_validation.valid;
  const caseUsage = Array.isArray(patch.case_usage) && patch.case_usage.length
    ? patch.case_usage.map((item) => `<li>${escapeHtml(item)}</li>`).join("")
    : "<li>未使用或未返回 case usage。</li>";
  const patches = Array.isArray(patch.patches) && patch.patches.length
    ? patch.patches.map((item) => `
        <li>
          <strong>${escapeHtml(item.operation || "patch")}</strong>
          <span>${escapeHtml(item.target_step_id || "flow")}</span>
          <p>${escapeHtml(item.reason || "")}</p>
        </li>
      `).join("")
    : "<li>当前没有可应用 patch；可能需要更多信息或 LLM patch 未开启。</li>";
  const candidateSteps = result.candidate_plan && Array.isArray(result.candidate_plan.steps)
    ? result.candidate_plan.steps.map((step, index) => `
        <div class="mini-plan-item">
          <strong>${index + 1}. ${escapeHtml(step.title)}</strong>
          <span>${escapeHtml(step.stage || "执行任务")} · ${escapeHtml(nodeKindLabel(step.node_kind))}</span>
        </div>
      `).join("")
    : `<div class="notice">${escapeHtml(emptyPlanText)}</div>`;
  const errors = result.candidate_validation && Array.isArray(result.candidate_validation.errors)
    ? result.candidate_validation.errors.map((item) => `<li>${escapeHtml(item.code)}: ${escapeHtml(item.message)}</li>`).join("")
    : "";
  return `
    <div class="ai-edit-summary">
      <div>
        <span>Patch 状态</span>
        <strong><span class="pill ${pillKind(patch.status)}">${escapeHtml(patch.status || "unknown")}</span></strong>
      </div>
      <div>
        <span>决策</span>
        <strong>${escapeHtml(patch.decision || "-")}</strong>
      </div>
      <div>
        <span>候选校验</span>
        <strong><span class="pill ${candidateValid ? "ok" : "warn"}">${candidateValid ? "valid" : "not ready"}</span></strong>
      </div>
    </div>
    <div class="ai-edit-section">
      <strong>说明</strong>
      <p>${escapeHtml(patch.rationale || patch.reason || result.explanation || "暂无说明。")}</p>
    </div>
    <div class="ai-edit-grid">
      <div class="ai-edit-section">
        <strong>候选修改</strong>
        <ul>${patches}</ul>
      </div>
      <div class="ai-edit-section">
        <strong>Case 使用</strong>
        <ul>${caseUsage}</ul>
      </div>
    </div>
    ${errors ? `<div class="ai-edit-section err"><strong>校验问题</strong><ul>${errors}</ul></div>` : ""}
    <div class="ai-edit-section">
      <strong>候选计划</strong>
      <div class="mini-plan-list">${candidateSteps}</div>
    </div>
  `;
}

function applyAiCandidate() {
  const result = state.aiEditResult;
  if (!result || !result.candidate_flow_dsl) throw new Error("当前没有可应用的候选 Flow");
  if (!result.candidate_validation || !result.candidate_validation.valid) throw new Error("候选 Flow 未通过校验");
  state.currentSavedFlowId = null;
  setFlow(result.candidate_flow_dsl);
  state.plan = result.candidate_plan;
  renderPlan(state.plan);
  renderSavedFlows();
  renderHub();
  setNotice("ai-edit-message", "候选 Flow 已应用到当前画布和 DSL，保存前仍可继续编辑。", "ok");
  setNotice("validation-message", "AI 候选已应用；如需持久化请点击保存当前 Flow。", "ok");
  switchTab("plan");
  updateDevSummary();
}

function applyRepairCandidate() {
  const result = state.repairResult;
  if (!result || !result.candidate_flow_dsl) throw new Error("当前没有可应用的修复候选 Flow");
  if (!result.candidate_validation || !result.candidate_validation.valid) throw new Error("修复候选 Flow 未通过校验");
  state.currentSavedFlowId = null;
  setFlow(result.candidate_flow_dsl);
  state.plan = result.candidate_plan;
  renderPlan(state.plan);
  renderSavedFlows();
  renderHub();
  setNotice("run-message", "修复候选已应用到当前画布和 DSL，保存和再次运行仍需手动确认。", "ok");
  setNotice("validation-message", "修复候选已应用；如需持久化请点击保存当前 Flow。", "ok");
  switchPage("flows");
  switchTab("plan");
  updateDevSummary();
}

function aiPatchSummary(result) {
  const patch = result && result.ai_patch ? result.ai_patch : {};
  if (patch.status === "skipped") return patch.reason || "AI patch 当前未启用。";
  if (patch.status === "failed") return patch.error_message || "AI patch 生成失败。";
  if (patch.questions && patch.questions.length) return `需要补充：${patch.questions.join("；")}`;
  return "AI 候选未生成可应用 Flow。";
}

async function validateFlow() {
  const flow = currentFlow();
  const result = await api("/api/flows/validate", {method: "POST", body: JSON.stringify(flow)});
  setFlow(flow);
  setNotice("validation-message", result.valid ? "Flow 校验通过。" : JSON.stringify(result, null, 2), result.valid ? "ok" : "err");
  switchTab("status");
}

async function renderFlowPlan() {
  const flow = currentFlow();
  const plan = await api("/api/flows/render-plan", {method: "POST", body: JSON.stringify(flow)});
  state.plan = plan;
  renderPlan(plan);
  setNotice("validation-message", `计划已刷新：${plan.steps.length} 个节点。`, "ok");
  switchTab("plan");
}

async function refreshPlanForFlow(flow, {silent = false} = {}) {
  if (!flow || !Array.isArray(flow.steps) || !flow.steps.length) {
    state.plan = null;
    renderPlan(null);
    return null;
  }
  const plan = await api("/api/flows/render-plan", {method: "POST", body: JSON.stringify(flow)});
  state.plan = plan;
  renderPlan(plan);
  if (!silent) setNotice("validation-message", `计划已刷新：${plan.steps.length} 个节点。`, "ok");
  return plan;
}

async function persistCurrentSavedFlow(flow, successMessage) {
  if (!state.currentSavedFlowId) return null;
  const saved = await api(`/api/flows/${encodeURIComponent(state.currentSavedFlowId)}`, {
    method: "PUT",
    body: JSON.stringify({flow, template_id: state.selectedTemplateId}),
  });
  const reloaded = await api(`/api/flows/${encodeURIComponent(saved.flow_id)}`);
  state.currentSavedFlowId = reloaded.flow_id;
  await loadSavedFlows();
  setNotice("run-message", successMessage || `Flow 已更新：${reloaded.flow_id}`, "ok");
  updateDevSummary();
  return reloaded;
}

async function refreshSavedFlowFromDb(saved) {
  if (!saved || !saved.flow) return;
  state.flow = saved.flow;
  $("flow-json").value = JSON.stringify(saved.flow, null, 2);
  state.plan = await api("/api/flows/render-plan", {method: "POST", body: JSON.stringify(saved.flow)});
  renderCanvas(state.flow, null);
  renderPlan(state.plan);
  renderNodeDetail();
  updateDevSummary();
}

async function applySelectedNodeEdits() {
  if (!state.flow || !state.selectedStepId) throw new Error("请先选择一个 Flow 节点");
  const flow = JSON.parse(JSON.stringify(state.flow));
  const step = Array.isArray(flow.steps) ? flow.steps.find((item) => item.id === state.selectedStepId) : null;
  if (!step) throw new Error("节点不存在");
  let groupId = sessionGroupForStep(flow, step.id);
  const isRpaNode = step.type === "rpa.local_cli.run_app";
  const isIfNode = step.type === "flow.if";
  const isSleepNode = step.type === "time.sleep";
  const promptNode = planStepFor(step.id);
  const isAgentNode = promptNode.node_kind === "agent" || step.type === "agent.task";
  const isCapabilityNode = step.type === "capability.task";
  let savedMessage = "节点提示词已应用。点击保存当前 Flow 后持久化。";
  if (isRpaNode) {
    const editor = $("local_cli-app-name-editor");
    const appName = editor.value.trim();
    if (!appName) throw new Error("应用名不能为空");
    step.params = {...(step.params || {}), app_name: appName};
    savedMessage = "Local CLI应用名已应用。点击保存当前 Flow 后持久化。";
  } else if (isIfNode) {
    const editor = $("flow-if-question-editor");
    const question = editor.value.trim();
    if (!question) throw new Error("判断问题不能为空");
    step.params = {...(step.params || {}), question};
    savedMessage = "判断问题已应用。点击保存当前 Flow 后持久化。";
  } else if (isSleepNode) {
    const secondsEditor = $("sleep-seconds-editor");
    const reasonEditor = $("sleep-reason-editor");
    const seconds = Number.parseInt(secondsEditor.value, 10);
    const reason = reasonEditor.value.trim() || "等待后继续执行后续节点。";
    if (!Number.isInteger(seconds) || seconds < 1 || seconds > 3600) {
      throw new Error("等待秒数必须是 1 到 3600 之间的整数");
    }
    step.params = {...(step.params || {}), seconds, reason};
    step.prompt = `等待 ${seconds} 秒后继续执行后续节点。`;
    step.timeout_seconds = Math.max((seconds || 1) + 10, step.timeout_seconds || 0);
    savedMessage = "等待节点设置已应用。点击保存当前 Flow 后持久化。";
  } else {
    const editor = $("node-prompt-editor");
    const prompt = editor.value.trim();
    if (!prompt) throw new Error("提示词不能为空");
    step.prompt = prompt;
    if (state.plan && Array.isArray(state.plan.steps)) {
      const planStep = state.plan.steps.find((item) => item.step_id === state.selectedStepId);
      if (planStep) {
        planStep.prompt = prompt;
      }
    }
  }
  if (isAgentNode) {
    const sessionEditor = $("node-session-group-editor");
    groupId = normalizeSessionGroupId(sessionEditor ? sessionEditor.value : "");
    setStepSessionGroup(flow, step.id, groupId);
    savedMessage = groupId
      ? `Agent节点已归属会话：${groupId}。点击保存当前 Flow 后持久化。`
      : "Agent节点将使用独立会话。点击保存当前 Flow 后持久化。";
  }
  if (isAgentNode || isCapabilityNode) {
    const capabilityEditor = $("node-capability-editor");
    const capabilityId = capabilityEditor ? capabilityEditor.value : "";
    if (isCapabilityNode && !capabilityId) throw new Error("能力节点必须选择一个已保存 Capability");
    step.params = {...(step.params || {})};
    if (capabilityId) {
      const capability = state.capabilities.find((item) => item.id === capabilityId);
      if (!capability) throw new Error("选择的 Capability 不存在，请刷新能力目录");
      step.params.capability_id = capabilityId;
      step.params.capability_fingerprint = capability.fingerprint;
      savedMessage = `节点已绑定能力：${capabilityId}。点击保存当前 Flow 后持久化。`;
    } else {
      delete step.params.capability_id;
      delete step.params.capability_fingerprint;
    }
  }
  state.flow = flow;
  $("flow-json").value = JSON.stringify(flow, null, 2);
  renderCanvas(flow, null);
  renderPlan(state.plan);
  renderNodeDetail();
  const saved = await persistCurrentSavedFlow(flow, `节点修改已保存到 DB：${state.currentSavedFlowId}`);
  if (saved && !savedFlowHasNodeEdit(saved.flow, step.id, step.prompt || "", groupId, step.params || {})) {
    throw new Error("节点修改提交后没有在 DB 读回相同结果，请刷新或确认 pre 已部署最新保存接口。");
  }
  await refreshSavedFlowFromDb(saved);
  setNotice(
    "validation-message",
    saved
      ? (isRpaNode ? "Local CLI应用名已保存到 DB。" : isIfNode ? "判断问题已保存到 DB。" : "节点修改已保存到 DB。")
      : savedMessage,
    "ok",
  );
}

async function saveCurrentFlow() {
  const flow = currentFlow();
  const updatingSavedFlow = Boolean(state.currentSavedFlowId);
  const savedResponse = updatingSavedFlow
    ? await api(`/api/flows/${encodeURIComponent(state.currentSavedFlowId)}`, {
        method: "PUT",
        body: JSON.stringify({flow, template_id: state.selectedTemplateId}),
      })
    : await api("/api/flows", {
        method: "POST",
        body: JSON.stringify({flow, template_id: state.selectedTemplateId}),
      });
  const saved = await api(`/api/flows/${encodeURIComponent(savedResponse.flow_id)}`);
  state.currentSavedFlowId = saved.flow_id;
  await loadSavedFlows();
  await refreshSavedFlowFromDb(saved);
  setNotice("run-message", updatingSavedFlow ? `Flow 已更新到 DB：${saved.flow_id}` : `Flow 已保存：${saved.flow_id}`, "ok");
  renderHub();
  updateDevSummary();
}

async function deleteSavedFlow(flowId) {
  const saved = state.savedFlows.find((item) => item.flow_id === flowId);
  const label = saved ? `${saved.name} (${saved.flow_id})` : flowId;
  if (!window.confirm(`删除已保存 Flow：${label}？此操作不会删除运行记录。`)) return;
  await api(`/api/flows/${encodeURIComponent(flowId)}`, {method: "DELETE"});
  if (state.currentSavedFlowId === flowId) {
    clearFlowView();
  }
  await loadSavedFlows();
  setNotice("validation-message", `已删除保存 Flow：${flowId}`, "ok");
}

async function loadSavedFlows() {
  state.savedFlows = await api("/api/flows");
  renderSavedFlows();
  renderHub();
}

async function openSavedFlow(flowId) {
  const saved = await api(`/api/flows/${encodeURIComponent(flowId)}`);
  state.currentSavedFlowId = saved.flow_id;
  state.selectedTemplateId = saved.template_id || state.selectedTemplateId;
  if (state.selectedTemplateId) renderTemplates();
  hydrateInputsFromFlow(saved.flow);
  state.plan = await api("/api/flows/render-plan", {method: "POST", body: JSON.stringify(saved.flow)});
  setFlow(saved.flow);
  renderPlan(state.plan);
  renderSavedFlows();
  renderHub();
  switchPage("flows");
  setNotice("input-message", `已加载保存 Flow：${saved.name}`, "ok");
  setNotice("validation-message", `已加载保存 Flow：${saved.flow_id}`, "ok");
  updateDevSummary();
}

async function createRun() {
  const flow = currentFlow();
  const executor = $("executor-select").value;
  const runSavedFlow = Boolean(state.currentSavedFlowId);
  if (!runSavedFlow) {
    syncLegacyInputsFromMaterials();
  }
  const inputs = {};
  Object.entries(flow.inputs || {}).forEach(([key, spec]) => {
    if (spec && Object.prototype.hasOwnProperty.call(spec, "default") && spec.default !== null) {
      inputs[key] = spec.default;
    }
  });
  if (!runSavedFlow && $("target-url").value) inputs.target_url = $("target-url").value;
  if (!runSavedFlow && targetUrlsTemplates.has(state.selectedTemplateId)) {
    const targetUrls = parseTargetUrls($("target-urls").value);
    if (targetUrls.length) inputs.target_urls = targetUrls;
  }
  if (!runSavedFlow && inquiryTextTemplates.has(state.selectedTemplateId) && $("inquiry-text").value) {
    inputs.inquiry_text = $("inquiry-text").value;
  }
  if (!runSavedFlow && !$("keyword").disabled && $("keyword").value) inputs.keyword = $("keyword").value;
  if (!runSavedFlow && !$("max-pages").disabled) inputs.max_pages = Number($("max-pages").value || inputs.max_pages || 2);
  if (!runSavedFlow && reportFocusTemplates.has(state.selectedTemplateId)) inputs.report_focus = $("user-request").value;
  setNotice("run-message", `正在由 ${executor} 执行 Flow；结果和 Artifact 会自动写入本地工作区。`, "warn");
  switchPage("runs");
  const result = state.currentSavedFlowId
    ? await api(`/api/flows/${encodeURIComponent(state.currentSavedFlowId)}/runs`, {method: "POST", body: JSON.stringify({inputs, executor})})
    : await api("/api/flows/runs", {method: "POST", body: JSON.stringify({flow, inputs, executor})});
  state.run = result.run;
  state.task = result.next_task;
  state.repairResult = null;
  rememberRun(state.run);
  renderRun();
  renderCanvas(flow, null);
  renderHub();
  updateRuntimeCommand();
  if (terminalRunStatuses.has(state.run.status)) {
    setNotice(
      "run-message",
      `Run 已结束：${state.run.status}。执行器：${executor}；节点证据和 Artifact 已持久化。`,
      state.run.status === "succeeded" ? "ok" : "err",
    );
  } else {
    setNotice(
      "run-message",
      `Run 已创建并正在执行：${state.run.run_id}。页面会持续刷新实时证据。`,
      "warn",
    );
    startRunPolling(state.run.run_id);
  }
}

async function refreshRun(runId = state.run && state.run.run_id, options = {}) {
  if (!runId) return null;
  const run = await api(`/api/flows/runs/${encodeURIComponent(runId)}`);
  if (!state.run || state.run.run_id !== runId) return run;
  state.run = run;
  rememberRun(run);
  reconcileTaskWithRun();
  renderRun();
  if (state.flow) renderCanvas(state.flow, null);
  if (!options.silent) {
    setNotice("run-message", `Run 状态已刷新：${run.status}`, run.status === "failed" || run.status === "cancelled" ? "err" : "ok");
  }
  renderHub();
  return run;
}

function startRunPolling(runId) {
  stopRunPolling();
  const token = state.runPollToken + 1;
  state.runPollToken = token;
  const poll = async () => {
    if (!state.run || state.run.run_id !== runId || state.runPollToken !== token) return;
    try {
      const run = await refreshRun(runId, {silent: true});
      if (!state.run || state.run.run_id !== runId || state.runPollToken !== token) return;
      if (!run || terminalRunStatuses.has(run.status)) {
        stopRunPolling(token);
        setNotice("run-message", run ? `Run 已结束：${run.status}` : "Run 轮询已停止。", run && run.status === "succeeded" ? "ok" : "err");
        return;
      }
      state.runPollTimer = window.setTimeout(poll, runPollIntervalMs);
    } catch (error) {
      if (state.runPollToken !== token) return;
      stopRunPolling(token);
      setNotice("run-message", `Run 状态轮询失败：${error.message || String(error)}`, "err");
    }
  };
  state.runPollTimer = window.setTimeout(poll, runPollInitialDelayMs);
}

function stopRunPolling(token = null) {
  if (token !== null && state.runPollToken !== token) return;
  if (token === null) {
    state.runPollToken += 1;
  }
  if (state.runPollTimer) {
    window.clearTimeout(state.runPollTimer);
    state.runPollTimer = null;
  }
}

function reconcileTaskWithRun() {
  if (!state.run) {
    state.task = null;
    return;
  }
  if (terminalRunStatuses.has(state.run.status)) {
    state.task = null;
    return;
  }
  if (!state.task) return;
  const matchingStep = (state.run.steps || []).find((step) => step.step_id === state.task.step_id);
  if (matchingStep && !["pending", "running"].includes(matchingStep.status)) {
    state.task = null;
  }
}

function updateRuntimeCommand() {
  if (!state.run) {
    state.runtimeCommand = "";
    $("runtime-command").textContent = "Desktop owns the Local Runtime and invokes the selected Agent CLI.";
    $("runtime-llm-hint").textContent = "";
    $("copy-runtime").disabled = true;
    updateDevSummary();
    return;
  }
  state.runtimeCommand = "";
  $("runtime-command").textContent = "Desktop-owned Local Runtime · no extra worker process required";
  $("runtime-llm-hint").textContent = "";
  $("copy-runtime").disabled = true;
  renderHub();
  updateDevSummary();
}

function flowHasLlmReport() {
  return Boolean(
    state.flow
    && Array.isArray(state.flow.steps)
    && state.flow.steps.some((step) => step.type === "llm.report" || step.type === "flow.if")
  );
}

function renderRun() {
  $("run-id").textContent = state.run ? state.run.run_id : "-";
  $("run-status").textContent = state.run ? state.run.status : "未创建";
  $("next-task").textContent = nextTaskLabel();
  $("poll-task").disabled = !state.run;
  $("refresh-run").disabled = !state.run;
  $("cancel-run").disabled = !state.run || terminalRunStatuses.has(state.run.status);
  $("close-run").disabled = !state.run;
  $("mock-result").disabled = !state.task;
  $("mock-failure").disabled = !state.task;
  renderReportSummary();
  renderRepairResult();
  const runSteps = $("run-steps");
  runSteps.innerHTML = "";
  if (!state.run || !Array.isArray(state.run.steps)) {
    updateDevSummary();
    return;
  }
  state.run.steps.forEach((step, index) => {
    const markdownUrl = markdownArtifactUrl(step);
    const item = document.createElement("div");
    item.className = `run-step ${step.status}`;
    item.innerHTML = `
      <span class="node-badge">${index + 1}</span>
      <div>
        <div class="node-id">${escapeHtml(planStepFor(step.step_id).title || step.step_id)}</div>
        <div class="node-meta">${escapeHtml(step.node_type)} · attempts=${step.attempts}${markdownUrl ? ` · <a class="artifact-link" href="${markdownUrl}" target="_blank">打开报告</a>` : ""}</div>
      </div>
      <span class="pill ${pillKind(step.status)}">${escapeHtml(step.status)}</span>
    `;
    runSteps.appendChild(item);
  });
  renderNodeDetail();
  renderHub();
  renderRunHistory();
  updateDevSummary();
}

function renderRunHistory() {
  const list = $("run-history-list");
  if (!list) return;
  list.innerHTML = "";
  if (!state.runs || !state.runs.length) {
    const empty = document.createElement("div");
    empty.className = "notice";
    empty.textContent = "还没有运行记录。创建 Run 后会显示在这里；刷新页面也会自动恢复最近一次运行。";
    list.appendChild(empty);
    return;
  }
  state.runs.forEach((run) => {
    const report = findMarkdownReport(run);
    const active = state.run && state.run.run_id === run.run_id;
    const canCancel = !terminalRunStatuses.has(run.status);
    const card = document.createElement("div");
    card.className = "run-history-card" + (active ? " active" : "");
    card.dataset.runId = run.run_id;
    card.innerHTML = `
      <div class="template-title">
        <span>${escapeHtml(run.run_id)}</span>
        <span class="pill ${pillKind(run.status)}">${escapeHtml(run.status)}</span>
      </div>
      <div class="template-desc">${escapeHtml(run.flow_id)} · ${escapeHtml(formatDate(run.updated_at || run.created_at))}</div>
      <div class="node-meta">${report ? "报告已生成" : terminalRunStatuses.has(run.status) ? "已结束" : "等待 runtime / 运行中"}</div>
      <div class="run-history-actions">
        <button type="button" class="ghost-button" data-open-run="${escapeHtml(run.run_id)}">打开</button>
        ${canCancel ? `<button type="button" class="danger-button" data-cancel-run="${escapeHtml(run.run_id)}">停止</button>` : ""}
      </div>
    `;
    list.appendChild(card);
  });
}

async function cancelRunById(runId) {
  if (!runId) throw new Error("尚未创建 Run");
  if (!window.confirm(`停止 Run：${runId}？`)) return;
  const run = await api(`/api/flows/runs/${encodeURIComponent(runId)}/cancel`, {
    method: "POST",
    body: "{}",
  });
  const isActiveRun = !state.run || state.run.run_id === run.run_id;
  if (!state.run || state.run.run_id === run.run_id) {
    state.run = run;
    state.task = null;
  }
  rememberRun(run);
  renderRun();
  if (isActiveRun && state.flow) renderCanvas(state.flow, null);
  renderHub();
  updateRuntimeCommand();
  if (run.status === "cancel_requested") {
    setNotice("run-message", `已请求停止 Run：${run.run_id}；正在等待当前执行边界关闭。`, "warn");
    if (isActiveRun) startRunPolling(run.run_id);
  } else if (run.status === "cancelled") {
    stopRunPolling();
    setNotice("run-message", `Run 已停止：${run.run_id}`, "warn");
  } else {
    setNotice(
      "run-message",
      `Run 已结束为 ${run.status}，未改写为 cancelled：${run.run_id}`,
      run.status === "succeeded" ? "ok" : "err",
    );
  }
}

async function cancelRun() {
  if (!state.run) throw new Error("尚未创建 Run");
  await cancelRunById(state.run.run_id);
}

function closeRunPanel() {
  stopRunPolling();
  state.run = null;
  state.task = null;
  state.repairResult = null;
  clearActiveRunId();
  renderRun();
  renderHub();
  updateRuntimeCommand();
  setNotice("run-message", "已关闭当前 Run 面板；运行记录仍保留在右侧列表。", "ok");
}

async function pollTask() {
  if (!state.run) throw new Error("尚未创建 Run");
  const task = await api(`/api/local-agent/tasks/poll?run_id=${encodeURIComponent(state.run.run_id)}`);
  state.task = task;
  await refreshRun(state.run.run_id, {silent: true});
  renderRun();
  setNotice("run-message", task ? `已领取：${task.step_id} / ${task.node_type}` : "当前没有可领取任务。", task ? "ok" : "warn");
  renderHub();
}

function taskCapability(task) {
  if (task && task.params && typeof task.params.capability === "string" && task.params.capability) {
    return task.params.capability;
  }
  return task ? task.node_type : "";
}

async function submitMockResult() {
  if (!state.run || !state.task) throw new Error("没有可提交的任务");
  const task = state.task;
  const requiredArtifacts = (task.completion_policy && task.completion_policy.required_artifacts) || [];
  const artifactTypes = requiredArtifacts.length ? requiredArtifacts : ["json"];
  const requiredOutputs = (task.completion_policy && task.completion_policy.required_outputs) || [];
  const capability = taskCapability(task);
  const output = {};
  requiredOutputs.forEach((key) => {
    output[key] = key === "products" ? [{title: "mock", price: "1.00", url: "https://example.com"}] : `mock_${key}`;
  });
  if (capability === "browser.open") {
    output.opened_url = task.params.url || $("target-url").value;
    output.url = output.opened_url;
    output.title = "mock page";
  }
  if (capability === "browser.search") {
    output.keyword = task.params.keyword || $("keyword").value || "电脑";
    output.result_url = "https://s.taobao.com/search?q=" + encodeURIComponent(output.keyword);
    output.title = "mock taobao search";
    output.visible_summary = "mock 搜索结果页摘要";
    output.requires_login = false;
    output.products = [
      {title: `${output.keyword} 商务款`, price: "39.90", shop: "mock 店铺 A", url: "https://example.com/a", selling_points: ["通勤", "大容量"]},
      {title: `${output.keyword} 防水款`, price: "89.00", shop: "mock 店铺 B", url: "https://example.com/b", selling_points: ["防水", "轻量"]},
    ];
  }
  if (capability === "browser.inspect_product_detail") {
    const targetUrls = Array.isArray(task.params.target_urls) ? task.params.target_urls : parseTargetUrls($("target-urls").value || $("supplemental-materials").value);
    output.product_details = (targetUrls.length ? targetUrls : ["https://item.taobao.com/item.htm?id=mock"]).slice(0, 3).map((url, index) => ({
      url,
      title: `mock 商品详情 ${index + 1}`,
      price: "99.00",
      main_image: "主图可见",
      specs: ["颜色", "尺码"],
      selling_points: ["清晰卖点", "规格完整"],
      structure_summary: "标题、主图、价格和规格模块可见。",
      diagnosis: "mock 详情页结构完整，可继续强化首图利益点。",
      optimization_suggestions: ["标题补充核心场景", "主图突出差异化卖点"],
      requires_login: false,
    }));
    output.requires_login = false;
  }
  if (task.node_type === "input.parse_inquiries") {
    output.inquiries = [
      {
        customer: "Alice Trading",
        country: "US",
        product: "waterproof laptop bag",
        quantity: "500",
        inquiry_time: "2026-06-12",
        message: "Need quote ASAP and sample shipping cost",
        intent: "quote",
        urgency: "high",
        priority_score: 68,
        priority_reasons: ["紧急程度高", "采购意图=quote", "采购量大于等于 100"],
      },
      {
        customer: "Beta Import",
        country: "DE",
        product: "solar garden light",
        quantity: "1200",
        inquiry_time: "2026-06-10",
        message: "Ready to place order this week if price is good",
        intent: "purchase",
        urgency: "high",
        priority_score: 80,
        priority_reasons: ["紧急程度高", "采购意图=purchase", "采购量大于等于 1000"],
      },
    ];
    output.inquiry_count = output.inquiries.length;
  }
  if (task.node_type === "data.cluster_inquiries") {
    output.clusters = [
      {
        cluster_key: "solar garden light / DE / purchase / high",
        product: "solar garden light",
        country: "DE",
        intent: "purchase",
        urgency: "high",
        count: 1,
        total_quantity: 1200,
        top_priority_score: 80,
        sample_customers: ["Beta Import"],
        follow_up_action: "当天优先回复，确认规格、数量、交期和收货国家。",
      },
    ];
    output.priority_customers = [
      {
        customer: "Beta Import",
        country: "DE",
        product: "solar garden light",
        quantity: "1200",
        intent: "purchase",
        urgency: "high",
        priority_score: 80,
        priority_reasons: ["紧急程度高", "采购意图=purchase", "采购量大于等于 1000"],
      },
    ];
    output.summary = {
      inquiry_count: 2,
      cluster_count: 1,
      high_priority_count: 1,
      products: ["solar garden light"],
      countries: ["DE"],
    };
  }
  const artifacts = task.completion_policy.type === "artifact_exists"
    ? await Promise.all(artifactTypes.map((type) => uploadMockArtifact(task, type, output)))
    : [];
  const result = {
    task_id: task.task_id,
    run_id: task.run_id,
    step_id: task.step_id,
    status: "succeeded",
    output,
    artifacts,
    logs: [{level: "info", message: "console mock result"}],
    error: null,
  };
  const run = await api(`/api/local-agent/tasks/${encodeURIComponent(task.task_id)}/result`, {method: "POST", body: JSON.stringify(result)});
  state.run = run;
  state.task = null;
  renderRun();
  if (state.flow) renderCanvas(state.flow, null);
  setNotice("run-message", `已提交 ${task.step_id} mock result，run=${run.status}`, "ok");
  renderHub();
  if (!terminalRunStatuses.has(run.status)) startRunPolling(run.run_id);
}

async function submitMockFailure() {
  if (!state.run || !state.task) throw new Error("没有可提交的任务");
  const task = state.task;
  const result = {
    task_id: task.task_id,
    run_id: task.run_id,
    step_id: task.step_id,
    status: "failed",
    output: {
      failed_node_type: task.node_type,
      visible_summary: "Console mock failure",
    },
    artifacts: [],
    logs: [{level: "error", message: "console mock failure"}],
    error: {code: "CONSOLE_MOCK_FAILURE", message: `${task.step_id} mock failed`},
  };
  const run = await api(`/api/local-agent/tasks/${encodeURIComponent(task.task_id)}/result`, {method: "POST", body: JSON.stringify(result)});
  state.run = run;
  state.task = null;
  state.repairResult = null;
  renderRun();
  if (state.flow) renderCanvas(state.flow, null);
  setNotice("run-message", `已提交 ${task.step_id} 失败结果，可生成修复候选。`, "err");
  renderHub();
}

async function uploadMockArtifact(task, type, output) {
  const filename = `mock_${task.step_id}.${artifactExtension(type)}`;
  const content = mockArtifactContent(task, type, output);
  const uploaded = await api("/api/local-agent/artifacts", {
    method: "POST",
    body: JSON.stringify({
      type,
      content_base64: base64EncodeUtf8(content),
      content_type: artifactContentType(type),
      filename,
      metadata: {
        run_id: task.run_id,
        task_id: task.task_id,
        step_id: task.step_id,
        source: "flow_console_mock",
      },
    }),
  });
  return uploaded.artifact;
}

function mockArtifactContent(task, type, output) {
  if (type === "markdown") {
    const upstreamMarkdown = findPreviousMarkdown(task.input && task.input.previous_outputs);
    return upstreamMarkdown || output.markdown || [
      `# Mock Report: ${task.step_id}`,
      "",
      "- 执行边界：Console 开发 Mock 生成的报告产物。",
      "- 关键发现：Flow 已推进到 artifact.save，并保存了可下载 Markdown。",
      "- 下一步建议：使用本地 runtime 或 pre runtime 做真实节点验证。",
    ].join("\n");
  }
  if (type === "json") {
    return JSON.stringify({
      step_id: task.step_id,
      node_type: task.node_type,
      output,
      previous_outputs: task.input && task.input.previous_outputs,
    }, null, 2);
  }
  return `Mock ${type} artifact for ${task.step_id}`;
}

function findPreviousMarkdown(previousOutputs) {
  if (!previousOutputs || typeof previousOutputs !== "object") return "";
  for (const value of Object.values(previousOutputs)) {
    if (value && typeof value === "object" && typeof value.markdown === "string" && value.markdown.trim()) {
      return value.markdown;
    }
  }
  return "";
}

function artifactExtension(type) {
  if (type === "markdown") return "md";
  if (type === "json") return "json";
  if (type === "html") return "html";
  if (type === "screenshot") return "txt";
  return "txt";
}

function artifactContentType(type) {
  if (type === "markdown") return "text/markdown; charset=utf-8";
  if (type === "json") return "application/json";
  if (type === "html") return "text/html; charset=utf-8";
  return "text/plain; charset=utf-8";
}

function base64EncodeUtf8(text) {
  const bytes = new TextEncoder().encode(text);
  let binary = "";
  bytes.forEach((byte) => {
    binary += String.fromCharCode(byte);
  });
  return btoa(binary);
}

function markdownArtifactUrl(step) {
  const artifact = (step.artifacts || []).find((item) => markdownArtifactHref(item));
  if (!artifact) return "";
  return markdownArtifactHref(artifact);
}

function markdownArtifactHref(artifact) {
  if (!artifact || artifact.type !== "markdown") return "";
  const uri = String(artifact.uri || "");
  if (!uri.startsWith("artifact://")) return "";
  return `/api/flow-artifacts/${encodeURIComponent(uri.replace("artifact://", ""))}`;
}

function findMarkdownReport(run) {
  const steps = run && Array.isArray(run.steps) ? [...run.steps].reverse() : [];
  for (const step of steps) {
    const artifact = (step.artifacts || []).find((item) => markdownArtifactHref(item));
    if (artifact) {
      return {
        href: markdownArtifactHref(artifact),
        stepId: step.step_id,
        filename: artifact.metadata && artifact.metadata.filename,
      };
    }
  }
  return null;
}

function renderReportSummary() {
  const card = $("report-card");
  const title = $("report-title");
  const body = $("report-body");
  const link = $("report-link");
  const report = findMarkdownReport(state.run);
  if (report) {
    card.className = "report-card ready";
    title.textContent = report.filename || "Markdown 报告已生成";
    body.textContent = `来自节点 ${report.stepId}`;
    link.href = report.href;
    link.hidden = false;
    return;
  }
  link.hidden = true;
  link.removeAttribute("href");
  if (!state.run) {
    card.className = "report-card waiting";
    title.textContent = "等待报告";
    body.textContent = "runtime 完成后这里会显示 Markdown 报告。";
    return;
  }
  card.className = "report-card waiting";
  title.textContent = terminalRunStatuses.has(state.run.status) ? "未发现 Markdown 报告" : "报告生成中";
  body.textContent = terminalRunStatuses.has(state.run.status)
    ? "请查看节点时间线或 runtime 日志。"
    : "页面会随 Run 状态自动刷新。";
}

function nextTaskLabel() {
  if (state.task) return `${planStepFor(state.task.step_id).title || state.task.step_id} / ${state.task.node_type}`;
  if (!state.run || !Array.isArray(state.run.steps)) return "-";
  const activeStep = state.run.steps.find((step) => step.status === "running")
    || state.run.steps.find((step) => step.status === "pending");
  if (!activeStep || terminalRunStatuses.has(state.run.status)) return "-";
  return `${planStepFor(activeStep.step_id).title || activeStep.step_id} / ${activeStep.node_type}`;
}

function failedRunStep() {
  if (!state.run || !Array.isArray(state.run.steps)) return null;
  return state.run.steps.find((step) => step.status === "failed") || null;
}

function planStepFor(stepId) {
  const steps = state.plan && Array.isArray(state.plan.steps) ? state.plan.steps : [];
  return steps.find((step) => step.step_id === stepId) || {};
}

function sessionGroupForStep(flow, stepId) {
  const steps = flow && Array.isArray(flow.steps) ? flow.steps : [];
  const step = steps.find((item) => item.id === stepId);
  if (step && step.session_group) return String(step.session_group);
  const policy = flow && flow.execution ? flow.execution.session_policy : null;
  const groups = policy && Array.isArray(policy.groups) ? policy.groups : [];
  const group = groups.find((item) => item && Array.isArray(item.steps) && item.steps.includes(stepId));
  return group && group.id ? String(group.id) : "";
}

function savedFlowHasNodeEdit(flow, stepId, prompt, sessionGroup, params = {}) {
  const steps = flow && Array.isArray(flow.steps) ? flow.steps : [];
  const step = steps.find((item) => item.id === stepId);
  if (!step) return false;
  if (step.type === "rpa.local_cli.run_app") {
    return (step.params && step.params.app_name) === params.app_name;
  }
  if (step.type === "flow.if") {
    return (step.params && (step.params.question || step.params.condition)) === (params.question || params.condition);
  }
  return (step.prompt || "") === prompt && sessionGroupForStep(flow, stepId) === sessionGroup;
}

function nextStepId(flow, base) {
  const existing = new Set((flow.steps || []).map((step) => step.id));
  if (!existing.has(base)) return base;
  let index = 2;
  while (existing.has(`${base}_${index}`)) index += 1;
  return `${base}_${index}`;
}

function lastStepId(flow) {
  const steps = flow && Array.isArray(flow.steps) ? flow.steps : [];
  return steps.length ? steps[steps.length - 1].id : null;
}

function defaultStepForKind(flow, kind, dependencyOverride) {
  const dependency = arguments.length >= 3 ? dependencyOverride : lastStepId(flow);
  if (kind === "capability") {
    return {
      id: nextStepId(flow, "invoke_capability"),
      type: "capability.task",
      from: dependency || undefined,
      params: {title: "Invoke a saved Capability"},
      prompt: "Invoke the selected Capability with the accepted upstream Context.",
      completion_policy: {type: "output_schema"},
      timeout_seconds: 120,
    };
  }
  if (kind === "llm") {
    return {
      id: nextStepId(flow, "write_report"),
      type: "llm.report",
      from: dependency || undefined,
      params: {report_type: "flow_report"},
      prompt: "请基于上游节点结果生成一份可读的 Markdown 报告，说明关键发现、边界和下一步建议。",
      completion_policy: {type: "output_schema", required_outputs: ["markdown"]},
      timeout_seconds: 120,
    };
  }
  if (kind === "normal") {
    return {
      id: nextStepId(flow, "analyze_data"),
      type: "data.price_summary",
      from: dependency || undefined,
      params: {price_field: "price"},
      prompt: "请对上游结构化数据做一次轻量整理，输出可供后续报告使用的摘要。",
      completion_policy: {type: "output_schema", required_outputs: ["summary"]},
      timeout_seconds: 30,
    };
  }
  if (kind === "sleep") {
    return {
      id: nextStepId(flow, "wait"),
      type: "time.sleep",
      from: dependency || undefined,
      params: {seconds: 10, reason: "等待对方回复或第三方应用完成状态变化。"},
      prompt: "等待 10 秒后继续执行后续节点。",
      completion_policy: {type: "output_schema", required_outputs: ["waited_seconds"]},
      timeout_seconds: 20,
    };
  }
  if (kind === "local_cli") {
    return {
      id: nextStepId(flow, "run_local_cli"),
      type: "rpa.local_cli.run_app",
      from: dependency || undefined,
      params: {
        app_uuid: "d96e903a-d1da-40f9-ac21-7d99f811bc13",
        app_name: "钉钉截图",
        mode: "macos_local",
      },
      prompt: "运行本机Local CLI应用：钉钉截图。该节点只记录第三方应用执行状态；业务产物由后续节点显式发现。",
      completion_policy: {type: "external_status", external_statuses: ["succeeded"]},
      timeout_seconds: 120,
    };
  }
  if (kind === "if") {
    return {
      id: nextStepId(flow, "check_condition"),
      type: "flow.if",
      from: dependency || undefined,
      params: {
        question: "上游结果是否满足继续条件？请只判断 true 或 false。",
        true_label: "yes",
        false_label: "no",
      },
      prompt: "调用 LLM 判断上游识别结果是否满足继续条件。",
      completion_policy: {type: "output_schema", required_outputs: ["condition_met"]},
      timeout_seconds: 60,
    };
  }
  if (kind === "end") {
    return {
      id: nextStepId(flow, "publish-article"),
      type: "artifact.task",
      from: dependency || undefined,
      params: {title: "Accept the final Markdown Artifact"},
      prompt: "Accept the upstream article_markdown as article.md.",
      completion_policy: {type: "artifact_exists"},
      timeout_seconds: 60,
    };
  }
  return {
    id: nextStepId(flow, "agent_step"),
    type: "agent.task",
    from: dependency || undefined,
    params: {capability: "agent.task"},
    prompt: "请Agent执行这个节点的任务。把当前节点是否完成判断为 succeeded、warning 或 failed，并说明原因。",
    completion_policy: {type: "external_status", external_statuses: ["succeeded", "warning"]},
    session_group: "",
    timeout_seconds: 90,
    retry: {max_attempts: 1, backoff_seconds: 0},
  };
}

function defaultIfBranchSteps(flow, dependencyOverride) {
  const pending = [];
  const dependency = arguments.length >= 2 ? dependencyOverride : lastStepId(flow);
  const ifId = nextStepIdWithPending(flow, pending, "check_condition");
  const trueId = nextStepIdWithPending(flow, pending, "if_true");
  const falseId = nextStepIdWithPending(flow, pending, "if_false");
  const ifStep = {
    id: ifId,
    type: "flow.if",
    from: dependency || undefined,
    params: {
      question: "上游结果是否满足继续条件？请只判断 true 或 false。",
      true_label: "yes",
      false_label: "no",
    },
    prompt: "调用 LLM 判断上游结果是否满足继续条件，并输出 condition_met=true/false。",
    completion_policy: {type: "output_schema", required_outputs: ["condition_met"]},
    timeout_seconds: 60,
  };
  pending.push(ifStep);
  pending.push({
    id: trueId,
    type: "agent.task",
    from: ifId,
    when: `steps.${ifId}.output.condition_met == true`,
    params: {capability: "agent.task"},
    prompt: "true 分支：请Agent在判断成立时执行这里的后续动作。",
    completion_policy: {type: "external_status", external_statuses: ["succeeded", "warning"]},
    timeout_seconds: 120,
    retry: {max_attempts: 1, backoff_seconds: 0},
  });
  pending.push({
    id: falseId,
    type: "agent.task",
    from: ifId,
    when: `steps.${ifId}.output.condition_met == false`,
    params: {capability: "agent.task"},
    prompt: "false 分支：请Agent在判断不成立时执行这里的后续动作。",
    completion_policy: {type: "external_status", external_statuses: ["succeeded", "warning"]},
    timeout_seconds: 120,
    retry: {max_attempts: 1, backoff_seconds: 0},
  });
  return pending;
}

function applyBranchCondition(step, sourceStepId, branch) {
  if (!branch || !sourceStepId) return;
  const normalizedBranch = branch === "false" ? "false" : "true";
  step.when = `steps.${sourceStepId}.output.condition_met == ${normalizedBranch}`;
}

function insertStepsIntoFlow(flow, steps, afterStepId) {
  if (!Array.isArray(flow.steps)) flow.steps = [];
  if (!steps.length) return;
  if (!afterStepId) {
    flow.steps.push(...steps);
    return;
  }
  const index = flow.steps.findIndex((step) => step.id === afterStepId);
  if (index < 0) {
    flow.steps.push(...steps);
    return;
  }
  const nextStep = flow.steps[index + 1];
  const nextDependencies = nextStep ? dependenciesForStep(nextStep) : [];
  flow.steps.splice(index + 1, 0, ...steps);
  if (nextStep && nextDependencies.length === 1 && nextDependencies[0] === afterStepId) {
    setStepDependencies(nextStep, [steps[steps.length - 1].id]);
  }
}

async function addNodeToCurrentFlow(kind, options = {}) {
  const flow = JSON.parse(JSON.stringify(state.flow || newBlankFlow()));
  if (!Array.isArray(flow.steps)) flow.steps = [];
  const afterStepId = options.afterStepId || null;
  const branch = options.branch || "";
  const dependency = afterStepId || lastStepId(flow) || undefined;
  const selectedMessageSuffix = afterStepId ? `，已接在 ${afterStepId} 后面` : "";
  if (kind === "if") {
    const steps = defaultIfBranchSteps(flow, dependency);
    if (branch && steps[0]) applyBranchCondition(steps[0], afterStepId, branch);
    insertStepsIntoFlow(flow, steps, afterStepId);
    state.currentSavedFlowId = state.currentSavedFlowId || null;
    state.flow = flow;
    state.selectedStepId = steps[0] ? steps[0].id : null;
    $("flow-json").value = JSON.stringify(flow, null, 2);
    await refreshPlanForFlow(flow, {silent: true});
    renderCanvas(flow, null);
    renderNodeDetail();
    renderHub();
    switchPage("flows");
    setNotice("validation-message", `已添加判断节点和 true/false 两条分支${selectedMessageSuffix}。点击保存当前 Flow 后持久化。`, "ok");
    return;
  }
  if (kind === "poll_reply") {
    const steps = defaultDingTalkReplyPollingSteps(flow, dependency);
    if (branch && steps[0]) applyBranchCondition(steps[0], afterStepId, branch);
    insertStepsIntoFlow(flow, steps, afterStepId);
    state.currentSavedFlowId = state.currentSavedFlowId || null;
    state.flow = flow;
    state.selectedStepId = steps[0] ? steps[0].id : null;
    $("flow-json").value = JSON.stringify(flow, null, 2);
    await refreshPlanForFlow(flow, {silent: true});
    renderCanvas(flow, null);
    renderNodeDetail();
    renderHub();
    switchPage("flows");
    setNotice("validation-message", `已添加 For 重复回复检测：${steps.length} 个节点${selectedMessageSuffix}。点击保存当前 Flow 后持久化。`, "ok");
    return;
  }
  const step = defaultStepForKind(flow, kind, dependency);
  applyBranchCondition(step, afterStepId, branch);
  if (!step.from) delete step.from;
  if (!step.session_group) delete step.session_group;
  insertStepsIntoFlow(flow, [step], afterStepId);
  state.currentSavedFlowId = state.currentSavedFlowId || null;
  state.flow = flow;
  state.selectedStepId = step.id;
  $("flow-json").value = JSON.stringify(flow, null, 2);
  await refreshPlanForFlow(flow, {silent: true});
  renderCanvas(flow, null);
  renderNodeDetail();
  renderHub();
  switchPage("flows");
  setNotice("validation-message", `已添加节点：${step.id}${selectedMessageSuffix}。点击保存当前 Flow 后持久化。`, "ok");
}

function defaultDingTalkReplyPollingSteps(flow, dependencyOverride) {
  const steps = [];
  let dependency = arguments.length >= 2 ? dependencyOverride : lastStepId(flow);
  const recognizeIds = [];
  for (let index = 1; index <= 20; index += 1) {
    const previousRecognizeId = recognizeIds[recognizeIds.length - 1];
    const continueWhen = previousRecognizeId ? `steps.${previousRecognizeId}.output.has_reply != true` : undefined;
    const local_cliId = nextStepIdWithPending(flow, steps, `run_local_cli_${index}`);
    const recognizeId = nextStepIdWithPending(flow, steps, `recognize_reply_${index}`);
    const waitId = nextStepIdWithPending(flow, steps, `wait_reply_${index}`);
    const local_cliStep = {
      id: local_cliId,
      type: "rpa.local_cli.run_app",
      from: dependency || undefined,
      params: {
        app_uuid: "d96e903a-d1da-40f9-ac21-7d99f811bc13",
        app_name: "钉钉截图",
        mode: "macos_local",
      },
      prompt: "运行本机Local CLI应用：钉钉截图。截图文件位置由后续Agent节点的 prompt 指定。",
      completion_policy: {type: "external_status", external_statuses: ["succeeded"]},
      timeout_seconds: 120,
    };
    if (continueWhen) local_cliStep.when = continueWhen;
    steps.push(local_cliStep);
    const recognizeStep = {
      id: recognizeId,
      type: "agent.task",
      from: local_cliId,
      params: {capability: "agent.task"},
      prompt: "请Agent读取固定截图文件夹中的最新钉钉截图，判断群里是否已有回复。请输出 has_reply=true/false；如果有回复，同时输出 reply_text、reply_image_path 或 reply_image_description。",
      completion_policy: {type: "external_status", external_statuses: ["succeeded", "warning"]},
      timeout_seconds: 120,
      retry: {max_attempts: 1, backoff_seconds: 0},
    };
    if (continueWhen) recognizeStep.when = continueWhen;
    steps.push(recognizeStep);
    recognizeIds.push(recognizeId);
    if (index < 20) {
      const waitStep = {
        id: waitId,
        type: "time.sleep",
        from: recognizeId,
        params: {seconds: 30, reason: "未识别到钉钉回复，等待后继续截图检查。"},
        prompt: "等待 30 秒后继续下一轮Local CLI截图和Agent识别。",
        when: `steps.${recognizeId}.output.has_reply != true`,
        completion_policy: {type: "output_schema", required_outputs: ["waited_seconds"]},
        timeout_seconds: 40,
      };
      steps.push(waitStep);
      dependency = waitId;
    } else {
      dependency = recognizeId;
    }
  }
  steps.push({
    id: nextStepIdWithPending(flow, steps, "send_reply_image_text"),
    type: "agent.task",
    from: recognizeIds,
    params: {capability: "agent.task"},
    prompt: "请Agent查看上游 20 轮识别结果，找到第一条 has_reply=true 的回复。如果回复里包含图片，请读取图片中的文字内容，并把图片文字内容发送到目标钉钉群；如果没有回复，则返回 warning 并说明未检测到回复。",
    session_group: "dingtalk_reply_followup",
    completion_policy: {type: "external_status", external_statuses: ["succeeded", "warning"]},
    timeout_seconds: 180,
    retry: {max_attempts: 1, backoff_seconds: 0},
  });
  return steps;
}

function nextStepIdWithPending(flow, pendingSteps, base) {
  const existing = new Set([...(flow.steps || []).map((step) => step.id), ...pendingSteps.map((step) => step.id)]);
  if (!existing.has(base)) return base;
  let index = 2;
  while (existing.has(`${base}_${index}`)) index += 1;
  return `${base}_${index}`;
}

function dependenciesForStep(step) {
  const deps = step.from || step.depends_on;
  if (!deps) return [];
  return Array.isArray(deps) ? deps : [deps];
}

function setStepDependencies(step, dependencies) {
  delete step.depends_on;
  delete step.from;
  if (!dependencies.length) return;
  step.from = dependencies.length === 1 ? dependencies[0] : dependencies;
}

async function deleteSelectedNode() {
  if (!state.flow || !state.selectedStepId) throw new Error("请先选择要删除的节点");
  const flow = JSON.parse(JSON.stringify(state.flow));
  const steps = Array.isArray(flow.steps) ? flow.steps : [];
  const index = steps.findIndex((step) => step.id === state.selectedStepId);
  if (index < 0) throw new Error("节点不存在");
  const removed = steps[index];
  const replacementDeps = dependenciesForStep(removed).filter((dep) => dep !== removed.id);
  flow.steps = steps.filter((step) => step.id !== removed.id).map((step) => {
    const dependencies = dependenciesForStep(step);
    if (!dependencies.includes(removed.id)) return step;
    const nextDeps = dependencies.flatMap((dep) => dep === removed.id ? replacementDeps : [dep]);
    setStepDependencies(step, Array.from(new Set(nextDeps)));
    if (String(step.when || "").includes(`steps.${removed.id}.`)) {
      delete step.when;
    }
    return step;
  });
  setStepSessionGroup(flow, removed.id, "");
  state.flow = flow;
  state.selectedStepId = flow.steps[index] ? flow.steps[index].id : (flow.steps[index - 1] ? flow.steps[index - 1].id : null);
  $("flow-json").value = JSON.stringify(flow, null, 2);
  await refreshPlanForFlow(flow, {silent: true});
  renderCanvas(flow, null);
  renderNodeDetail();
  renderHub();
  setNotice("validation-message", `已删除节点：${removed.id}。点击保存当前 Flow 后持久化。`, "ok");
}

function linearizeStepDependencies(flow) {
  const steps = Array.isArray(flow.steps) ? flow.steps : [];
  steps.forEach((step, index) => {
    setStepDependencies(step, index === 0 ? [] : [steps[index - 1].id]);
  });
}

async function moveNodeInCurrentFlow(stepId, direction) {
  if (!state.flow) throw new Error("请先创建或打开一个 Flow");
  const flow = JSON.parse(JSON.stringify(state.flow));
  const steps = Array.isArray(flow.steps) ? flow.steps : [];
  const index = steps.findIndex((step) => step.id === stepId);
  if (index < 0) throw new Error("节点不存在");
  const offset = direction === "up" ? -1 : 1;
  const nextIndex = index + offset;
  if (nextIndex < 0 || nextIndex >= steps.length) return;
  const [step] = steps.splice(index, 1);
  steps.splice(nextIndex, 0, step);
  flow.steps = steps;
  linearizeStepDependencies(flow);
  state.flow = flow;
  state.selectedStepId = stepId;
  $("flow-json").value = JSON.stringify(flow, null, 2);
  await refreshPlanForFlow(flow, {silent: true});
  renderCanvas(flow, null);
  renderNodeDetail();
  renderHub();
  setNotice("validation-message", `已调整节点顺序：${stepId}。点击保存当前 Flow 后持久化。`, "ok");
}

function nodeKindLabel(kind, nodeType = "") {
  if (nodeType === "capability.task" || kind === "capability") return "能力节点";
  if (nodeType === "flow.if") return "判断节点";
  if (kind === "agent") return "Agent节点";
  if (kind === "llm") return "LLM 节点";
  if (kind === "rpa") return "RPA 节点";
  return "普通节点";
}

function promptDetailTitle(kind) {
  if (kind === "agent") return "发送给Agent的提示词任务";
  if (kind === "llm") return "发送给 LLM 的提示词任务";
  return "节点任务说明";
}

function promptRuntimeHint(kind) {
  if (kind === "capability") return "运行时按保存的 Capability 合同执行固定 argv、MCP tool 或 HTTP endpoint，并记录真实证据。";
  if (kind === "agent") return "运行时只把节点提示词转发给Agent；具体工具动作是内部 capability，不作为节点类型暴露。";
  if (kind === "llm") return "运行时 LLM executor 会注入上游输出、artifact 摘要和报告输出契约。";
  if (kind === "rpa") return "运行时触发本机第三方 RPA 应用并记录执行状态；业务产物由后续节点显式发现。";
  return "普通节点由内部 executor 执行，提示词用于解释这个节点的业务目的。";
}

function sessionGroupOptions(activeSessionGroup = "") {
  const groups = new Set();
  if (state.flow && state.flow.execution && state.flow.execution.session_policy) {
    const policyGroups = state.flow.execution.session_policy.groups || [];
    policyGroups.forEach((group) => {
      if (group && group.id) groups.add(String(group.id));
    });
  }
  if (state.flow && Array.isArray(state.flow.steps)) {
    state.flow.steps.forEach((step) => {
      if (step && step.session_group) groups.add(String(step.session_group));
    });
  }
  if (activeSessionGroup) groups.add(String(activeSessionGroup));
  return Array.from(groups).sort();
}

function normalizeSessionGroupId(value) {
  const normalized = String(value || "").trim().replace(/\s+/g, "_");
  if (!normalized) return "";
  if (!/^[A-Za-z0-9_-]{1,64}$/.test(normalized)) {
    throw new Error("会话组只能包含字母、数字、下划线或短横线，最多 64 个字符");
  }
  return normalized;
}

function setStepSessionGroup(flow, stepId, groupId) {
  if (!flow.execution) flow.execution = {};
  if (!flow.execution.session_policy) flow.execution.session_policy = {default: "flow_session", groups: []};
  if (!Array.isArray(flow.execution.session_policy.groups)) flow.execution.session_policy.groups = [];
  const groups = flow.execution.session_policy.groups;
  groups.forEach((group) => {
    group.steps = Array.isArray(group.steps) ? group.steps.filter((item) => item !== stepId) : [];
  });
  const step = Array.isArray(flow.steps) ? flow.steps.find((item) => item.id === stepId) : null;
  if (step) {
    if (groupId) step.session_group = groupId;
    else delete step.session_group;
  }
  if (groupId) {
    let group = groups.find((item) => item.id === groupId);
    if (!group) {
      group = {id: groupId, policy: "group_session", steps: []};
      groups.push(group);
    }
    group.policy = group.policy || "group_session";
    if (!Array.isArray(group.steps)) group.steps = [];
    if (!group.steps.includes(stepId)) group.steps.push(stepId);
  }
  flow.execution.session_policy.groups = groups.filter((group) => Array.isArray(group.steps) && group.steps.length);
}

function sessionLabel(sessionGroup) {
  if (!sessionGroup) return "独立 Agent 会话";
  const conversationRef = state.run
    && state.run.session_state
    && state.run.session_state[sessionGroup]
    && state.run.session_state[sessionGroup].conversation_ref;
  return conversationRef ? `${sessionGroup} / 对话 ${conversationRef}` : `${sessionGroup} / 等待首个节点绑定对话`;
}

function completionSummary(policy) {
  if (!policy) return "-";
  if (policy.type === "artifact_exists") {
    return `artifact_exists: ${(policy.required_artifacts || []).join(", ") || "-"}`;
  }
  if (policy.type === "output_schema") {
    return `output_schema: ${(policy.required_outputs || []).join(", ") || "-"}`;
  }
  return policy.type || "-";
}

function pillKind(status) {
  if (status === "succeeded") return "ok";
  if (status === "failed" || status === "cancelled") return "err";
  if (status === "running" || status === "cancel_requested" || status === "warning" || status === "waiting_user") return "warn";
  return "";
}

function switchTab(tab) {
  document.querySelectorAll(".tab-button").forEach((button) => {
    button.classList.toggle("active", button.dataset.tab === tab);
  });
  document.querySelectorAll(".tab-content").forEach((content) => {
    content.classList.toggle("active", content.id === `${tab}-tab`);
  });
}

function formatJson() {
  state.currentSavedFlowId = null;
  setFlow(currentFlow());
  renderSavedFlows();
  updateDevSummary();
}

async function copyRuntime() {
  if (!state.runtimeCommand) return;
  await navigator.clipboard.writeText(state.runtimeCommand);
  setNotice("run-message", "runtime 命令已复制。", "ok");
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[ch]));
}

function formatDate(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString("zh-CN", {hour12: false});
}

function parseTargetUrls(value) {
  return String(value || "")
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean)
    .slice(0, 3);
}

function syncLegacyInputsFromMaterials() {
  const materials = $("supplemental-materials").value || "";
  const firstLine = firstMaterialLine(materials);
  if (inquiryTextTemplates.has(state.selectedTemplateId)) {
    $("inquiry-text").value = materials.trim();
    $("target-url").value = "";
    $("target-urls").value = "";
    $("keyword").value = "";
    return;
  }
  if (targetUrlsTemplates.has(state.selectedTemplateId)) {
    $("target-urls").value = parseTargetUrls(materials).join("\n");
    $("target-url").value = "";
    $("inquiry-text").value = "";
    $("keyword").value = "";
    return;
  }
  if (keywordTemplates.has(state.selectedTemplateId)) {
    $("keyword").value = normalizeKeyword(firstLine) || $("keyword").value;
    $("target-url").value = "https://www.taobao.com";
    $("target-urls").value = "";
    $("inquiry-text").value = "";
    return;
  }
  $("target-url").value = firstUrl(materials) || firstLine || $("target-url").value;
  $("target-urls").value = "";
  $("inquiry-text").value = "";
  $("keyword").value = "";
}

function firstMaterialLine(value) {
  return String(value || "")
    .split(/\r?\n/)
    .map((item) => item.trim())
    .find(Boolean) || "";
}

function firstUrl(value) {
  const match = String(value || "").match(/https?:\/\/\S+/);
  return match ? match[0] : "";
}

function normalizeKeyword(value) {
  return String(value || "").replace(/^关键词\s*[:：]\s*/, "").trim();
}

function updateDevSummary() {
  $("dev-flow-id").textContent = state.currentSavedFlowId || "-";
  $("dev-run-id").textContent = state.run ? state.run.run_id : "-";
  $("dev-runtime-command").textContent = state.runtimeCommand || "-";
}

function setCreationMode(mode) {
  state.creationMode = mode || "template";
  document.querySelectorAll(".creation-card[data-create-mode]").forEach((card) => {
    card.classList.toggle("active", card.dataset.createMode === state.creationMode);
  });
  if (state.creationMode === "ai") {
    setNotice("input-message", "描述业务目标和材料，系统会优先匹配模板并生成可校验 Flow。", "ok");
  }
}

async function guarded(action) {
  try {
    await action();
  } catch (error) {
    stopGenerationProgress({error: error.message || String(error)});
    const drawer = $("capability-drawer");
    if (state.activePage === "capabilities" && drawer && drawer.classList.contains("open")) {
      setNotice("capability-message", error.message || String(error), "err");
    } else if (state.activePage === "capabilities") {
      const scanMessage = $("capability-scan-message");
      if (scanMessage) scanMessage.textContent = error.message || String(error);
      const discoverButton = $("discover-capabilities");
      if (discoverButton) {
        discoverButton.disabled = false;
        discoverButton.innerHTML = '<span aria-hidden="true">⌁</span> 重新扫描';
      }
    } else {
      setNotice("validation-message", error.message || String(error), "err");
    }
    setStatus("出错", "err");
  }
}

bindClick("refresh-catalog", loadCatalog);
bindClick("new-blank-flow-top", openBlankFlow);
bindClick("save-flow-top", saveCurrentFlow);
bindClick("draft-flow", draftFlow);
bindClick("save-flow", saveCurrentFlow);
bindClick("validate-flow", validateFlow);
bindClick("render-plan", renderFlowPlan);
bindClick("ai-edit-flow", aiEditFlow);
bindClick("apply-ai-candidate", async () => applyAiCandidate());
bindClick("create-run", createRun);
bindClick("create-run-top", createRun);
bindClick("run-flow-top", createRun);
bindClick("refresh-run", async () => refreshRun());
bindClick("cancel-run", cancelRun);
bindClick("close-run", closeRunPanel);
bindClick("suggest-repair", suggestRunRepair);
bindClick("apply-repair-candidate", async () => applyRepairCandidate());
bindClick("poll-task", pollTask);
bindClick("mock-result", submitMockResult);
bindClick("mock-failure", submitMockFailure);
bindClick("format-json", async () => formatJson());
bindClick("copy-runtime", copyRuntime);
bindClick("delete-selected-node", deleteSelectedNode);
bindClick("discover-capabilities", discoverCapabilities);
bindClick("open-capability-drawer", openCapabilityDrawer);
bindClick("close-capability-drawer", closeCapabilityDrawer);
bindClick("capability-drawer-backdrop", closeCapabilityDrawer);
bindClick("validate-capability", validateCapabilityDraft);
bindClick("save-capability", async () => saveCapabilityDraft());

const capabilityKindSelect = $("capability-kind");
if (capabilityKindSelect) capabilityKindSelect.addEventListener("change", syncCapabilityForm);
const capabilitySearch = $("capability-search");
if (capabilitySearch) capabilitySearch.addEventListener("input", (event) => {
  state.capabilityQuery = event.target.value || "";
  renderCapabilities();
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && $("capability-drawer")?.classList.contains("open")) closeCapabilityDrawer();
});

document.addEventListener("click", (event) => {
  if (!(event.target instanceof Element)) return;
  const capabilityFilter = event.target.closest("[data-capability-filter]");
  if (capabilityFilter) {
    event.preventDefault();
    state.capabilityFilter = capabilityFilter.dataset.capabilityFilter || "all";
    document.querySelectorAll("[data-capability-filter]").forEach((button) => {
      button.classList.toggle("active", button === capabilityFilter);
    });
    renderCapabilities();
    return;
  }
  const blankFlow = event.target.closest("[data-new-blank-flow]");
  if (blankFlow) {
    event.preventDefault();
    guarded(openBlankFlow);
    return;
  }
  const saveDiscovered = event.target.closest("[data-save-discovered-capability]");
  if (saveDiscovered) {
    event.preventDefault();
    const candidate = state.discoveredCapabilities[Number(saveDiscovered.dataset.saveDiscoveredCapability)];
    if (candidate) guarded(() => saveCapabilityDraft(candidate));
    return;
  }
  const probeCapability = event.target.closest("[data-probe-capability]");
  if (probeCapability) {
    event.preventDefault();
    guarded(() => probeSavedCapability(probeCapability.dataset.probeCapability));
    return;
  }
  const deleteCapability = event.target.closest("[data-delete-capability]");
  if (deleteCapability) {
    event.preventDefault();
    guarded(() => deleteSavedCapability(deleteCapability.dataset.deleteCapability));
    return;
  }
  const addNode = event.target.closest("[data-add-node]");
  if (addNode) {
    event.preventDefault();
    const kind = addNode.dataset.addNode || "agent";
    guarded(() => addNodeToCurrentFlow(kind));
    return;
  }
  const addNodeAfter = event.target.closest("[data-add-node-after]");
  if (addNodeAfter) {
    event.preventDefault();
    const kind = addNodeAfter.dataset.addNodeAfter || "agent";
    const afterStepId = addNodeAfter.dataset.afterStep || state.selectedStepId || null;
    const branch = addNodeAfter.dataset.branch || "";
    guarded(() => addNodeToCurrentFlow(kind, {afterStepId, branch}));
    return;
  }
  const moveNode = event.target.closest("[data-move-node]");
  if (moveNode) {
    event.preventDefault();
    const stepId = moveNode.dataset.moveNode;
    const direction = moveNode.dataset.direction || "down";
    if (stepId) guarded(() => moveNodeInCurrentFlow(stepId, direction));
    return;
  }
  const openRun = event.target.closest("[data-open-run]");
  if (openRun) {
    event.preventDefault();
    const runId = openRun.dataset.openRun;
    if (runId) guarded(() => openRunFromHistory(runId));
    return;
  }
  const cancelRunButton = event.target.closest("[data-cancel-run]");
  if (cancelRunButton) {
    event.preventDefault();
    const runId = cancelRunButton.dataset.cancelRun;
    if (runId) guarded(() => cancelRunById(runId));
    return;
  }
  const applyNodeEdits = event.target.closest("#apply-node-edits");
  if (applyNodeEdits) {
    event.preventDefault();
    guarded(applySelectedNodeEdits);
    return;
  }
  const openFlow = event.target.closest("[data-open-flow]");
  if (openFlow) {
    event.preventDefault();
    const flowId = openFlow.dataset.openFlow;
    if (flowId) guarded(() => openSavedFlow(flowId));
    return;
  }
  const deleteFlow = event.target.closest("[data-delete-flow]");
  if (deleteFlow) {
    event.preventDefault();
    const flowId = deleteFlow.dataset.deleteFlow;
    if (flowId) guarded(() => deleteSavedFlow(flowId));
    return;
  }
  const templateNew = event.target.closest("[data-template-new]");
  if (templateNew) {
    const templateId = templateNew.dataset.templateNew;
    if (templateId) {
      state.selectedTemplateId = templateId;
      renderTemplates();
      applyTemplatePreset();
      switchPage("templates");
    }
    return;
  }
  const templateFlow = event.target.closest("[data-template-flow]");
  if (templateFlow) {
    const flowId = templateFlow.dataset.templateFlow;
    if (flowId) guarded(() => openSavedFlow(flowId));
    return;
  }
  const hubAction = event.target.closest(".hub-action[data-target-page], .hub-action-inline[data-target-page]");
  if (hubAction) {
    event.preventDefault();
    if (hubAction.dataset.newMode) setCreationMode(hubAction.dataset.newMode);
    switchPage(hubAction.dataset.targetPage);
    return;
  }
  const creationCard = event.target.closest(".creation-card[data-create-mode]");
  if (creationCard) {
    event.preventDefault();
    setCreationMode(creationCard.dataset.createMode);
    return;
  }
  const pageButton = event.target.closest(".nav-item[data-page], .section-tab[data-page]");
  if (pageButton) {
    event.preventDefault();
    switchPage(pageButton.dataset.page);
    return;
  }
  const tabButton = event.target.closest(".tab-button[data-tab]");
  if (tabButton) {
    event.preventDefault();
    switchTab(tabButton.dataset.tab);
  }
});

initFlowCanvasBridge();
guarded(loadCatalog);

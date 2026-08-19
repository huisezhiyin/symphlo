# Project Knowledge

## Durable Decisions

- Public identity: a slidable, observable outer loop for durable Agent work.
- Best-fit work: fixed orchestration, high repetition and long-running chains
  where durable handoffs, recovery, repeatability and maintenance outperform a
  loose Skill or one autonomous Agent session.
- Adoption: keep the default entrypoint as simple as a natural-language goal or
  one command; operational rigor must not require users to learn the Runtime.
- First-user path: bare `make` explains the choices, `make doctor` reports safe
  offline readiness, and `make desktop` opens the canonical task, Flow and Runs
  in an independent native window. `make app` remains a browser development
  surface.
- Golden Demo: a fresh App workspace uses deterministic Plan/Review boundaries
  around two separate Draft/Revise tasks in one `worker_loop`. The bundled
  fictional session fixture proves the public process protocol and persisted
  bind/reuse evidence without claiming a model or business workflow.
- Agent model: an Agent is a first-class Node and keeps its internal loop.
- Shared-session model: explicitly grouped Nodes may reuse one adapter-owned
  conversation within one Run; the opaque conversation/turn references are
  execution evidence, while accepted Context and Artifacts remain product truth.
- Product ownership: Symphlo owns observable task boundaries and durable truth,
  not the Agent's private session.
- Orchestration split: Flow controls `what / who / when / handoff`; an Agent
  controls `how`.
- Skill boundary: a Skill packages reusable execution knowledge inside a task;
  it is not the owner of durable Run state or accepted cross-Node handoffs.
- Core selling point: selectively externalize the meaningful high-level stages
  of an opaque Agent loop into an observable and orchestratable outer loop.
  Split semantic phases and handoffs, not model calls, tool calls or turns.
  Granularity can slide between one broad Agent Node and several durable
  boundaries when observation, recovery, replacement or maintenance value
  justifies the coordination cost.
- Open execution supply: an externalized boundary can independently bind an
  Agent, HTTP service, MCP tool, CLI, local script, compute task or Human.
  Multi-Agent and multi-capability collaboration comes from explicit contracts
  and inspectable handoffs, not from hoping one opaque Agent session improvises
  the whole chain.
- Control model: persistent input, executor, effects, events, result, handoff
  and Artifact evidence gives users and developers understandable,
  replaceable and maintainable control instead of hope-based orchestration.
- Public motivation: the external essay
  `general-purpose-agents-are-a-trap.md` explains why concrete, repeatable work
  should combine Agents, APIs and deterministic structure instead of treating
  one general-purpose Agent as the product. It is background context, not a
  protocol contract; Symphlo's narrower boundary-cost rule remains normative.
- Task granularity: a Flow may keep one broad Agent Node or slide toward finer
  semantic Nodes according to observation, recovery, replacement and
  maintenance value. Maximum decomposition is not the product goal.
- Evidence model: inputs, effects, executor identity, events, accepted results,
  Context and Artifacts must be inspectable and persistent.
- Live Run truth: Local creation durably admits one active Run and returns its
  identity before completion. `cancel_requested` is intent; `cancelled` is
  terminal only after the executor boundary closes and no later Node starts.
  Unconfirmed work found after restart is `failed/runtime_interrupted`, not a
  false cancellation success.
- Public UI: Home starts from goal and task, Flows shows selected semantic
  boundaries, and Runs exposes work, events, results and deliverables. Canvas
  and raw contracts remain projections or advanced capabilities, never sources
  of truth.
- Public source: the Runtime remains independently authored. The user explicitly
  authorized a reviewed transplant of App-owned Web source for A009B; Dify-derived
  vendor source, private adapters, generated bundles and old Git history remain excluded.
- Desktop product baseline: use the Aegis pre-Dify Flow Console at exact commit
  `21147b8d` for Hub/Canvas/Run interaction. `05d3d789` begins the Dify import
  and is excluded. The later Electron Monitor is only a lifecycle reference;
  its private endpoints, identity/device paths and adapters are excluded.
- First proof: the App opens the zero-credential Golden Flow; the terminal demo
  retains `compact`, `balanced` and `fine` Flow profiles over the same Runtime
  and `article.md` contract.
- Executor policy: deterministic offline evidence is mandatory; the optional
  stdio command path is explicitly labelled E2, fingerprint-bound, shell-free
  and not sandboxed.
- Live reference presets: Codex and OpenCode have completed the balanced writing
  Flow locally; they remain user-installed optional execution supply and do not
  own Symphlo task truth.
- Capability boundary: discovery never persists by itself. Explicitly saved
  `agent_cli`, `cli`, `mcp_stdio` and `http` definitions are immutable,
  fingerprinted execution supply behind Node contracts. The supported saved
  linear Canvas Flow is compiled and executed exactly; unsupported branches
  fail validation rather than falling back to a template.
- Local Agent extension: public code owns only the strict versioned descriptor
  loader and `symphlo.agent-session.v1`. Provider-specific names, App paths,
  commands and adapters stay in external Local state and never enter the public
  projection. The current workspace has completed real same-conversation
  Worker turns through this seam.
- Release policy: A011 published the reviewed exact public projection under
  Apache-2.0 as GreyChen's personal open-source project. A012 sharpened the
  public product identity without changing Runtime behavior. Future releases,
  packages, license/ownership changes and stable-version claims remain
  separately gated.
- Technical release candidate: A010 requires the public projection to install
  from the public npm registry with an isolated store, pass dependency/license
  review and survive a temporary first-commit rehearsal before any publication
  decision.
- Public-history policy: the first eventual commit is built from the exact
  `make public-tree` projection; local implementation ledgers and review packs
  never enter public Git history.

## Current Workspace Truth

- GitHub repository: `huisezhiyin/symphlo`.
- Local workspace: `/Users/wuyue/github_project/symphlo`.
- Git history: public `main` begins at
  `03227ade8bdd6a457715fbea9325a2e71bc778d0`; the mixed implementation
  workspace itself remains an uncommitted local source workspace.
- Product code: A012 slidable observable outer-loop positioning complete.
- Active Feature Spec: A012 is closed in
  `docs/features/a012-slidable-observable-outer-loop-positioning.md`.
- Public projection: 67 allowlisted files; 53 Python tests, 6 Web tests, 2
  Desktop launcher tests, enhanced native Golden Run/cancellation smoke and
  strict builds pass. The published exact tree at
  `/tmp/symphlo-a011-public.GOKwqB` independently installed 98 packages from
  the public npm registry with an empty store, passed zero-vulnerability and
  license review, `make doctor`, full `make check`, a two-Run demo, Desktop
  smoke and the exact 67-file first commit.
- App model: Home / Flow / Runs use the reviewed App-owned shell. The App-owned
  ReactFlow Canvas and Run evidence view project FlowDefinition, events, accepted
  results, Context and Artifacts; layout and selection remain disposable UI state.
- GitHub state: public, non-empty and default branch `main`; anonymous clone
  resolves the published source and passes the source boundary check. Public
  `main` includes A012 commit
  `a4b6d3200f1b2a8013a1f6e458ab6c9bcba7ba28`; the repository description uses
  the same slidable, observable outer-loop definition. No GitHub Release or
  package publication has occurred.

## Source Boundary

Never copy or import:

- Dify-derived files, vendor assets/styles, license/logo surface or generated bundles;
- private adapters or unreviewed App source outside the explicitly approved A009B Web cut;
- Wukong integration or any company-internal identity, endpoint or workflow;
- private Pilot material, handoffs, traces, local state, Artifacts or user data;
- credentials, provider configuration or model output;
- private repository Git history.

Approved product semantics may be reimplemented from the Project Spec, public
protocols and independently authored tests. The A009B App-owned transplant is a
specific user-approved exception and remains subject to the M0 ownership gate.

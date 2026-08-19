# Project Spec: Symphlo

## 0. Status

- Status: `open-source Local Alpha; A011 first public source release`
- Repository: `https://github.com/huisezhiyin/symphlo`
- Publication: `authorized for public main`
- Delivery focus: `cloneable, public-registry reproducible Local Alpha`
- License and copyright: `Apache-2.0; Copyright 2026 GreyChen`

## 1. Product Thesis

Symphlo is a slidable, observable outer loop for durable Agent work. It
selectively externalizes high-level phases that would otherwise remain inside
one opaque Agent session, turning them into versioned task boundaries with
durable state, observable handoffs and inspectable results.

This layer is most valuable for fixed orchestration, repeated execution and
long-running chains. In those cases, a reusable Flow can outperform a loose
Skill or one autonomous Agent session on repeatability, recovery, evidence and
maintenance while keeping the user entrypoint simple. Open-ended, disposable
work may still be better served by one autonomous Agent without an outer Flow.

For fixed orchestration, the high-level sequence has already been designed by
a human and encoded in the Flow. Reusing that structure avoids asking an Agent
to rediscover the orchestration through exploratory reasoning, temporary tools
and correction loops on every Run. That avoided orchestration-exploration work
is a design property and does not require provider token telemetry to establish.
It is distinct from a claim that every Flow uses fewer total provider tokens or
credits: overly fine Agent boundaries can repeat Context and cost more, so total
execution efficiency remains a task-granularity optimization problem.

Its primary design move is to externalize useful high-level phases of an
otherwise opaque Agent loop into an observable and orchestratable outer loop.
Task granularity can slide from one broad Agent Node toward more semantic
boundaries when observation, recovery, replacement, maintenance or explicit
handoff value earns the coordination cost. This is a design-time and
maintenance choice, not automatic decomposition, runtime graph rewriting or a
Loop-depth execution mode.

Externalization also makes each selected phase independently assignable to an
appropriate Agent, MCP tool, HTTP service, CLI, local script, compute step or
Human. Multi-Agent and multi-capability collaboration emerge from explicit
Node contracts and inspectable handoffs, not from putting several Agent names
on one opaque session. Users gain understandable control over steps, problems
and deliverables; developers gain versioned bindings, replaceable executors and
comparable evidence instead of hope-based orchestration.

Designers split semantic work such as `observe -> analyze -> challenge ->
deliver`, not individual model calls, tool calls or turns. Every Agent Node may
still run its own autonomous inner loop.

An Agent is a first-class Node executor. The Agent may decide that its task
requires one model call, many turns or its normal internal loop. Symphlo does
not replace or control that cognitive loop. It controls the external task
boundary:

- accepted input and Context;
- declared effects and authorization;
- resolved executor and version;
- task events and terminal state;
- accepted result and downstream handoff;
- produced Artifacts and comparable Run evidence.

Flow controls `what / who / when / handoff`. An Agent controls `how` inside its
Node. Flow definitions, Run state, Context, Artifacts and history are product
truth; private Agent sessions and conversations are not.

A Skill packages reusable execution knowledge. It may help an Agent perform a
Node, but it does not own durable task state, accepted cross-Node handoffs or
Run history. Symphlo complements Skills and Agents, and replaces loose session
orchestration only where explicit task operations create value.

## 2. Product Properties

1. **Externalized**: selected high-level phases become explicit task boundaries
   without exposing or controlling the Agent's private reasoning loop.
2. **Observable**: useful Node boundaries persist accepted input, executor,
   effects, events, results, handoffs and Artifacts.
3. **Sliding task granularity**: unlike an Agent's emergent and opaque inner-loop
   granularity, Flow task boundaries are explicit, observable, comparable and
   adjustable. Designers may keep one broad Agent Node or externalize more
   semantic phases when observation, recovery, replacement or maintenance value
   justifies the extra boundary. Maximum decomposition is not a goal and does
   not require a different Runtime.
4. **Open execution supply**: Agent, MCP, HTTP, CLI, local script, compute and
   Human executors collaborate behind explicit portable Node contracts.
5. **Controllable**: users see understandable steps, problems and deliverables;
   developers can inspect, replace and maintain exact executor bindings.
6. **Durable**: a task survives process, Agent and conversation boundaries.
7. **Repeatable**: one immutable task version can run again with new inputs.
8. **Maintainable**: comparable Runs identify unstable steps and affected work.
9. **Agent-agnostic**: capabilities and versioned adapters sit behind portable contracts.
10. **Evidence-first**: rendering, mocks and successful registration are not substitutes for accepted executor output and Artifacts.
11. **Explicit authority**: generated candidates do not save, run or escalate effects without validation and confirmation.

## 3. Public Experience

The normal user path starts from a goal and materials, not from YAML, a Canvas,
an Agent selector or runtime terminology. Advanced users may inspect portable
definitions, exact executors, Context and evidence.

The Local Alpha command path is progressive: bare `make` explains the choices,
`make doctor` checks offline readiness without requiring an Agent, `make
desktop` launches the complete product in an independent local window, and
`make demo` produces the canonical Article and evidence report. Expected
configuration failures are concise and actionable.

Canvas is an optional editor/projection. It is never product identity or
persistence truth. In Local Alpha it edits a supported linear Flow subset; the
saved DSL is compiled into the exact Runtime Flow and unsupported graph shapes
fail validation.

Local Run admission is asynchronous and durable. Create returns a readable Run
identity before execution completes, the App projects live Node states, and one
active Run per Local workspace can move through `running ->
cancel_requested -> cancelled`. Process-backed executors are terminated and
reaped at the Node boundary; HTTP cancellation is cooperative and
timeout-bounded. Cancellation stops orchestration and result acceptance, not
external effects that already occurred.

Selected same-Run Agent Nodes may declare one explicit `session_group` when
their exact capability implements the provider-neutral
`symphlo.agent-session.v1` contract. Runtime evidence then records one opaque
conversation reference and distinct turn references across those observable
Node boundaries. Ungrouped Nodes remain one-shot, incompatible grouped bindings
fail before Run admission, and private conversation state never replaces
accepted Context, Run state or Artifacts as product truth.

## 4. GitHub Local Alpha A1

A1 freezes one clean public-source candidate and one canonical technical
Golden Flow for the App:

```text
Start
  -> Plan Agent Node
  -> Draft Agent Node in worker_loop
  -> Review Agent Node
  -> Revise Agent Node in the same worker_loop conversation
  -> article.md Artifact
  -> End
```

The zero-credential Draft and Revise Nodes use a Runtime-owned fictional
process fixture implementing `symphlo.agent-session.v1`. Its
`E2_REAL_EXECUTOR` label proves an actual stdio/process boundary and same-Run
conversation reuse, not a model, provider or output-quality claim. Plan and
Review remain deterministic control boundaries, and accepted Context plus the
Artifact—not fixture conversation state—remain product truth.

The terminal demo retains compact, balanced and fine-grained writing profiles.
These explicit immutable definitions demonstrate sliding task granularity over
the same Runtime and Artifact contract. More Nodes are not inherently better.

The demo runs the selected immutable task version twice and exposes comparable
evidence. Its evidence levels are deliberately distinct:

- deterministic offline profile for clean-clone validation;
- an optional E2 stdio command profile invokes a user-installed executable.

Both profiles use the same public Flow, Context, Artifact and maintenance
semantics. Multiple role Nodes may resolve to the same Agent
executor; their persisted task boundaries and handoff are the product proof,
not a claim about heterogeneous providers. Executor binding remains explicit
and versioned.

The command profile is not a sandbox. It executes only explicitly configured
argument vectors without a shell, binds a command fingerprint into the Flow and
declares broad process/local/external effects. Credentials and environment
values are never persisted by Symphlo.

Codex and OpenCode are optional live-validated reference presets over this boundary. Codex
uses ephemeral read-only execution; OpenCode uses pure JSON events and may own
its own external session state. Neither is bundled, installed, authenticated or
required by the offline Quick Start.

Additional Agent CLIs may be described by a versioned user-local descriptor
outside the Git source tree. A descriptor can resolve explicit command names or
absolute executable paths and declare fixed execution, version and readiness
arguments. It cannot include environment values or credentials. Descriptor
discovery is optional and never makes an external Agent a Quick Start
dependency.

The Local Capability Catalog makes execution supply discoverable without
making any Agent, CLI or protocol the product owner. A saved
`CapabilityDefinition` is user-local, versioned and fingerprinted. It can bind
an `agent_cli` to `agent.task`, or bind `cli`, `mcp_stdio` and `http` to
`capability.task`. Discovery and validation do not persist; save is explicit.
Every execution still resolves to the same Flow, Node, effect, event, Result
and Artifact contracts. An `agent_cli` may declare bounded fixed `probe_args`
for a non-mutating readiness check; those arguments participate in its
immutable fingerprint and never receive Run input.

A user-local descriptor may instead bind an `agent_cli` through
`symphlo.agent-session.v1`. The generic public executor passes one canonical
JSON request over stdin and accepts bounded final text plus opaque conversation
and turn references. Provider-specific command translation, installation,
authentication and session storage stay outside the public source. Runtime
cancellation closes the adapter process boundary, whose protocol contract
requires cooperative external-turn abort.

The Local Runtime also owns one credential-free `source=sample`
`http.sample-json` definition. It performs a real loopback POST and deterministic
JSON context passthrough so users can verify the HTTP Capability contract
without depending on a temporary business Gate or public service. Its absolute
URL and fingerprint follow the Runtime's ephemeral port; only Runtime-owned
sample pins are refreshed across Desktop sessions. Manual and discovered
Capability fingerprints remain immutable.

## 5. Stable Architecture Boundary

```text
User experience
  -> Control Plane API
  -> Flow definition and Runtime
  -> Runner protocol
  -> capability / adapter contract
  -> Agent, MCP, API, CLI, script or local software
```

- Domain contracts do not import Web, database or concrete adapter code.
- Runtime state and accepted events are authoritative.
- Local execution uses the same register/lease/event/result path as other profiles.
- Adapters return versioned results; they do not mutate product state.
- Generated or repaired definitions remain candidates until validation and explicit Apply.

## 6. A1 Non-Goals

- GitHub Release, package publication or stable-version claim.
- Server-first deployment, SaaS, multi-tenancy or Remote operations.
- Desktop signing, notarization, self-contained installer or automatic updates.
- General graph-editor parity, branching, parallelism or automatic graph rewriting.
- Cross-Run or restart-time external conversation resume.
- Third-party-derived source, assets, backend, runtime, database, provider or design import.
- Internal integrations, Pilot material, company identity or private adapter publication.
- Bundling or managing an external Agent installation or credential.
- New DSL, Runtime, scheduler, database or Case-specific product path before the A1 contracts require it.

## 7. Publication Record

The owner approved the first personal open-source publication on 2026-07-24:

- independently authored and explicitly approved App-owned source;
- Apache-2.0 with copyright identity `GreyChen`;
- reviewed product name risk and third-party inventory;
- destination `huisezhiyin/symphlo`;
- exact clean-export validation and public release authority.

Future package publication, GitHub Releases, stable-version claims and changes
to license or ownership require their own review.

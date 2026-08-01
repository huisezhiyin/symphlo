# Project Spec: Symphlo

## 0. Status

- Status: `open-source Local Alpha; A018 Evaluation Gate And Explicit Repair Loop`
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

Its primary design move is to externalize useful high-level phases of an
otherwise opaque Agent loop into an observable and orchestratable outer loop.
Task granularity can slide from one broad Agent Node toward more semantic
boundaries when observation, recovery, replacement, maintenance or explicit
handoff value earns the coordination cost. This is a design-time and
maintenance choice, not automatic decomposition, runtime graph rewriting or a
Loop-depth execution mode.

Granularity also changes who owns the observable loop. With one broad Agent
Node, the Agent owns most adaptive iteration and the Flow owns only the durable
envelope. As semantic phases become separate Nodes, more of the high-level loop
becomes explicit Flow orchestration. Symphlo does not modify the Agent or
inspect private reasoning to make this happen. It shapes execution from the
outside through bounded tasks, accepted Context, result contracts, effects,
executor selection and state transitions.

At the deliberate fine-grained limit, the current Local Alpha can bind an
explicit `model.task` to a `model_cli`. The Runtime makes exactly one adapter
process invocation with one versioned model-inference request and accepts one
exact result. A truthful adapter can therefore let a linear Flow own a sequence
that might otherwise live inside an Agent Runtime. This is not decomposition
or surveillance of an existing Agent's private loop; it is a different,
explicit execution design.

The same fine-grained limit now includes an explicit `tool.task` bound to one
saved `cli`, `mcp_stdio` or `http` Capability. The Runtime invokes one fixed
semantic operation and accepts one result carrying
`symphlo.tool-call-evidence.v1`; the Capability fingerprint binds the operation
without persisting executable paths or URLs in Run output. MCP protocol setup
may use multiple wire messages around exactly one `tools/call`. General
branching model/tool graphs, dynamic tool selection and automatic granularity
conversion remain unimplemented.

Externalization also makes each selected phase independently assignable to an
appropriate Agent, MCP tool, HTTP service, CLI, local script, compute step or
Human. Multi-Agent and multi-capability collaboration emerge from explicit
Node contracts and inspectable handoffs, not from putting several Agent names
on one opaque session. Users gain understandable control over steps, problems
and deliverables; developers gain versioned bindings, replaceable executors and
comparable evidence instead of hope-based orchestration.

Designers normally split semantic work such as `observe -> analyze -> challenge
-> deliver`, not an Agent's private model calls, tool calls or turns. Every
Agent Node may still run its own autonomous inner loop. Atomic Model and Tool
Nodes are distinct truthful contracts rather than assumptions inferred from a
small task description. A Tool Node represents an explicit Flow-owned
operation; it does not expose tool calls that remain inside an Agent Node.

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
3. **Sliding task granularity**: designers may keep one broad Agent Node or
   externalize more semantic phases when observation, recovery, replacement or
   maintenance value justifies the extra boundary. Maximum decomposition is not
   a goal and does not require a different Runtime.
4. **Sliding loop ownership**: broad Nodes preserve more Agent autonomy; finer
   explicit boundaries give the Flow more orchestration, evidence and recovery
   responsibility without modifying private Agent cognition.
5. **Open execution supply**: Agent, MCP, HTTP, CLI, local script, compute and
   Human executors collaborate behind explicit portable Node contracts.
6. **Controllable**: users see understandable steps, problems and deliverables;
   developers can inspect, replace and maintain exact executor bindings.
7. **Debuggable from the boundary**: accepted Context, results, events,
   executors and Artifacts make Agent work replayable and comparable without
   exposing chain-of-thought.
8. **Durable**: a task survives process, Agent and conversation boundaries.
9. **Repeatable**: one immutable task version can run again with new inputs.
10. **Maintainable**: comparable Runs identify unstable steps and affected work.
11. **Agent-agnostic**: capabilities and versioned adapters sit behind portable contracts.
12. **Evidence-first**: rendering, mocks and successful registration are not substitutes for accepted executor output and Artifacts.
13. **Explicit authority**: generated candidates do not save, run or escalate effects without validation and confirmation.

## 3. Public Experience

The normal user path starts from a goal and materials, not from YAML, a Canvas,
an Agent selector or runtime terminology. Advanced users may inspect portable
definitions, exact executors, Context and evidence.

This is especially useful for non-technical office users whose work is
repetitive but not fully deterministic: a stable process receives changing
emails, documents or tables, uses bounded intelligence for classification,
extraction, drafting or review, and returns a familiar deliverable. The normal
operator should see tasks, materials, progress, exceptions, confirmations and
results. Flow internals remain progressive disclosure for authors, operators
and developers.

The same evidence supports an expert debugging path. A team can begin with one
broad black-box Agent Node, repeat the task, externalize a recurring failure or
review boundary, compare Runs and replace only the unstable executor. Symphlo
debugs observable Agent work rather than private cognition. The current
Runtime can fork a terminal Run from one failed Node when the saved Flow hash
still matches exactly: the accepted prefix is reused as evidence, while the
target and downstream Nodes execute in a new Run. An explicit read-only
Evaluation Node can now reject one accepted candidate, stop downstream
publication and project its producer as the repair fork target. Automated
diagnosis, automatic retry/repair and evaluator accuracy claims remain outside
the Alpha.

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

Node-level fork is an explicit new-Run mutation, never an in-place resume. The
parent remains immutable; the child records `parent_run_id`,
`forked_from_node_id` and ordered `reused_node_ids`. Reused Nodes have status
`reused` and `attempts=0`, and their executors and effects are not invoked
again. The target and downstream Nodes use the normal Runtime path, so their
effects may happen again. Fork admission requires a terminal parent, the exact
current Flow hash, a complete succeeded prefix and no `session_group` crossing
the fork boundary. Parent Artifacts are not copied, and fork Runs are excluded
from the fresh-execution stability read model.

Process-backed executors create an operating-system process group before work
begins. POSIX cancellation signals the group; Windows cancellation first sends
one cooperative `CTRL_BREAK_EVENT` and uses a bounded process-tree force
fallback. A cancelled Node never accepts late stdout. MCP stdio uses one
session-owned blocking reader thread and a bounded queue instead of assuming
that anonymous pipes are selectable sockets. These mechanisms preserve the
same public cancellation and result contracts across platforms; an external
adapter remains responsible for implementing its cooperative abort handler.

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
an `agent_cli` to `agent.task`, a `model_cli` to `model.task`, or bind `cli`,
`mcp_stdio` and `http` to `tool.task`. The former `capability.task` remains a
read/execute compatibility alias for already-saved non-Agent/non-Model Flows;
new authoring uses `tool.task`. Discovery and validation do not
persist; save is explicit.
Every execution still resolves to the same Flow, Node, effect, event, Result
and Artifact contracts. An `agent_cli` may declare bounded fixed `probe_args`
for a non-mutating readiness check; those arguments participate in its
immutable fingerprint and never receive Run input.

Saved Flows may declare typed input fields. Run admission resolves only those
declared fields from explicit values or defaults, validates their JSON types
and bounded aggregate size, rejects unknown fields and places the accepted
values in durable Context. Runtime-owned Context keys remain reserved. The
legacy `report_focus` field maps to the canonical writing topic; Case-specific
fields remain opaque to the Runtime. The Markdown publisher accepts either the
canonical `article_markdown` field or a generic Agent's bounded `agent_output`,
producing `article.md` or `result.md` respectively.

A `model_cli` declares `protocol=symphlo.model-inference.v1`. Each
`model.task` sends exact keys `contract_version, run_id, node_id, instruction,
context` once and accepts only `contract_version, output`. Runtime evidence
persists the accepted `model_output` wrapper and the same executor identity,
events and Context boundaries as other Nodes. Symphlo guarantees one adapter
request, not the internal behavior of an arbitrary third-party adapter; the
adapter owns the claim that this maps to one provider inference.

The Local Web Console MUST project the six supported JSON input types into a
generated Run form. It preserves declared description, required and default
metadata, parses values into their declared JSON types, and rejects missing or
invalid values before admission. Re-rendering an unchanged Flow schema MUST
not discard in-progress values. This is a provider-neutral projection of the
Flow contract, not a Case-specific form system.

External Agents may emit versioned execution recommendations derived from
observable task properties. Such a recommendation is advisory input only: it
MUST distinguish suggested granularity from an existing validated Flow, MUST
NOT return a runnable Flow id when that exact granularity is unavailable, and
MUST NOT imply execution or authority. Symphlo product truth starts with an
explicit saved Flow and admitted Run; recommendation scores, model profiles and
Case-to-Flow mapping remain outside the Runtime and scheduler.

The current companion Personal Assistant integration proves one balanced
Case-owned Flow without changing the Runtime: an evidence-backed candidate
extraction Agent Node hands its bounded `agent_output` to an independent review
Agent Node, which re-reads the original documents before the generic Markdown
publisher creates `result.md`. Both roles may resolve to the same one-shot
Capability. The proof is two accepted task boundaries, durable Context and an
Artifact, not heterogeneous provider identity or private-loop observation.

The companion also proves one fine Action Items Flow with two `model.task`
Nodes. Its `model-node` adapter performs exactly one `Model.complete` for the
candidate operation and exactly one for independent review, with the strict
candidate envelope as the durable handoff. The balanced two-Agent Flow remains
available and semantically distinct. Document Digest fine remains
design-required because it has no equivalent truthful stage contract yet.

An already-confirmed local client may submit a versioned
`symphlo.run-request.v1` to
`POST /api/v1/flows/{portable_flow_id}/runs`. The Control Plane resolves the
portable DSL id to exactly one saved local Flow resource, rejects missing or
ambiguous matches, validates declared inputs and admits the Run through the
same `ConsoleCompat -> LocalWorkspace -> Runtime` path. A successful response
is `symphlo.run-admission.v1` with a durable Run id. This contract does not
install or rewrite a Flow, infer authority from a recommendation, accept a
remote endpoint or bypass saved-Flow validation.

The companion Personal Assistant provides one concrete novice-facing authority
surface for this contract. Its loopback UI separates plan creation from
execution, displays exact inputs/effects/granularity, invalidates stale plans
after edits and submits a Run only after explicit confirmation. This behavior
belongs to the Case/client owner; it does not move office semantics, pending
plan state or confirmation policy into the Symphlo Runtime.

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

### 4.1 A014 Run Stability Read Model

A014 generalizes the canonical demo's two-Run comparison into one read-only
Local API report for any saved Task:

```text
GET /api/v1/tasks/{task_id}/stability?flow_hash=<64-hex-sha256>
```

Only terminal Runs with the exact requested `task_id` and immutable
`flow_hash` are comparable. Runs from edited definitions are never pooled.
The report orders Runs chronologically and classifies each Node from observable
execution status:

- `not_observed`: no comparable Run reached the Node;
- `insufficient_evidence`: exactly one comparable Run reached the Node;
- `stable_success`: at least two observed executions all succeeded;
- `repeated_failure`: at least two observed executions all failed or were
  cancelled;
- `unstable`: observed success and failure classes differ.

The read model may expose Run ids, counts, latest Node status, executor
identity/version and evidence levels. It MUST NOT expose Node input/output,
Prompt, event payload, Context value, Agent session reference, local path,
credential or Artifact content.

Operational stability does not mean byte-identical output. Repeated office
work may consume different materials and legitimately produce different
deliverables. The existing deterministic demo comparison remains a separate
evidence contract.

A014 adds no persistence table, Runtime transition, mutation, LLM, repair
candidate, automatic rerun, affected-subgraph logic, Web/Desktop surface or
Server behavior.

Implementation evidence:

- the pure read model and Local API tests cover chronological ordering,
  all five classifications, exact hash filtering, invalid and duplicate query
  rejection, restart persistence and response redaction;
- source and clean 69-file public export both pass 56 Python, 6 Web and 2
  Desktop tests through full `make check`;
- the unchanged deterministic two-Run demo still reports `stable_success`.

### 4.2 A015 Atomic Tool Node

A015 promotes fixed CLI, MCP stdio and HTTP execution from a generic
Capability Node to the explicit `tool.task` Flow boundary. Run admission
requires a saved non-Agent/non-Model Capability and pins its fingerprint into
the executor identity. Missing capabilities, fingerprint drift and
`agent_cli`/`model_cli` bindings fail before a Run is admitted.

Each Tool Node invokes one semantic operation:

- CLI: one child-process request with the accepted Context on stdin;
- HTTP: one fixed GET or POST request;
- MCP stdio: one bounded session with protocol initialization and exactly one
  `tools/call`.

The accepted output retains the tool's structured result for direct downstream
handoff and adds `symphlo.tool-call-evidence.v1` with exact fields
`contract_version, capability_id, capability_fingerprint, transport,
operation`. In v1, `operation` is the immutable Capability id. The envelope
does not copy executable paths, argument vectors or endpoint URLs into Run
output. Node input, executor identity, declared effects, events and accepted
result continue through the ordinary Runtime and Evidence Store; there is no
Tool-only scheduler or state path.

The Web Console creates and labels first-class Tool Nodes and only offers
compatible saved capabilities. `capability.task` remains executable for older
saved Flows but is not the new authoring contract. A cross-repository office
proof runs a read-only Personal Assistant document-inventory Tool before an
Agent digest and Artifact, with a call counter proving one tool operation and
without persisting document bodies in the inventory result.

### 4.3 A016 Effect-specific Run Authorization

A016 turns declared write effects from evidence-only metadata into a Runtime-owned
admission boundary. A Flow containing `write_local` or `write_external` cannot
create a Run until the caller presents `symphlo.effect-authorization.v1` for the
exact server-issued challenge. Missing, stale or tampered authorization returns
HTTP 428 through the Local API and creates zero Run, records zero executor call
and performs zero effect.

The authorization binds the Flow id, version and semantic hash, canonical accepted
input hash, ordered executable Node/effect scope and fork lineage. It is an explicit
intent token, not identity authentication or a cryptographic signature. The accepted
Run persists `run.effects_authorized`; a no-write Run persists
`run.effects_evaluated`. Neither event copies raw input, executable paths, endpoint
URLs or credentials.

Only the exact Runtime-owned `artifact.task -> builtin.markdown-publication` local
Artifact write is exempt. A different executor cannot gain the exemption by using
the same Node kind. Fork authorization is freshly computed for the target and
downstream suffix; reused-prefix effects are omitted because those Nodes do not
execute again.

The Web Console shows the challenged write effects and Node labels, requires an
explicit native confirmation and retries once with the exact authorization. CLI
live/command demos require `--authorize-write-effects` (or the corresponding Make
variable). Read-only, process-executing and external-reading Flows do not receive an
A016 prompt. General mid-Run approval, identity policy, remote approval and effect
rollback remain outside this milestone.

### 4.4 A017 Run Comparison And First Divergence

A017 makes two concrete terminal Runs directly comparable through durable Node
boundaries. The read-only Local API is:

```text
GET /api/v1/runs/{left_run_id}/comparison?other_run_id={right_run_id}
```

Both Runs must be distinct and terminal, and their immutable metadata must carry
the same Task id, Flow semantic hash and ordered Node ids. The comparison uses the
historical `app-run.json` plus SQLite Evidence rather than the current saved Flow,
so an older exact version remains debuggable after the author edits the Flow.

For each Node the report compares observation, accepted input, normalized outcome,
executor, effects, accepted output, evidence level and execution mode. Values are
compared only inside the process. The response exposes booleans, safe executor/effect
metadata and ordered reason codes; it MUST NOT expose accepted input/output, Context,
events, Artifact contents or paths, or payload hashes. `first_divergent_node_id`
means the earliest durable evidence boundary with a substantive difference. It is
not a semantic judgment or an automatic root-cause claim.

Fork lineage is explicit. A reused prefix has `execution_mode=reused` and a normalized
succeeded outcome; executed-versus-reused alone does not create a result divergence.
This lets a parent failed Run and its child fork identify the rerun target as the
first substantive difference while keeping the accepted prefix comparable.

The Web Runs page only offers other terminal Runs with the same Task id and Flow hash,
then renders the overall result, first divergence and per-Node reason codes without
payloads. The companion Personal Assistant verifier repeats a real compact
`Tool -> Agent -> Artifact` Digest Flow and consumes this public HTTP endpoint,
proving an equivalent three-Node comparison without database sharing.

### 4.5 A018 Evaluation Gate And Explicit Repair Loop

A018 adds one truthful quality-control boundary without modifying an Agent's
private loop. A portable `evaluation.task` must consume an immediate upstream
candidate and bind exactly one read-only `evaluator_cli`. The adapter receives
one `symphlo.evaluation-request.v1` and returns one exact
`symphlo.evaluation-result.v1` with `pass | fail`, a bounded summary and bounded
findings.

A pass persists an explicit Evaluation Node result and continues the linear
Flow. A valid fail is a control result rather than a transport exception: the
Runtime persists the candidate/evaluation envelope, marks the Evaluation Node
and Run failed, records `evaluation.rejected`, and never executes or publishes
the downstream Artifact. Event projection exposes safe finding codes and the
producer `repair_from_step_id`; detailed messages remain in Node evidence.

Repair remains user-controlled. The Console requires explicit confirmation and
uses the existing exact same-Flow fork API from the producer Node, so the safe
prefix is reused and candidate generation plus evaluation execute again. There
is no automatic retry, hidden prompt rewrite, evaluator-selected mutation or
changed-Flow replay. Evaluator output is bounded evidence for orchestration,
not verified truth, chain-of-thought or an automatic root-cause claim.

The companion Personal Assistant proves the contract with a balanced
`Tool -> Agent -> Evaluation -> Artifact` Document Digest. A real first Run is
rejected with no Artifact; an explicit producer fork reuses the inventory,
regenerates the digest, passes evaluation and publishes `result.md` through
public process and loopback HTTP contracts only.

### 4.6 A019 Companion Integration Bundle

A019 replaces manual Capability/Flow copying with a generic, versioned local
installation boundary. `POST /api/v1/integration-bundles/preview` accepts one
exact `symphlo.integration-bundle.v1`, normalizes every Capability, prepares
every portable Flow against the proposed post-install Capability view and
returns a canonical hash, exact confirmation phrase and per-resource
`create | reuse | conflict` plan without writing state.

`POST /api/v1/integration-bundles` accepts only the same canonical hash and
server-derived phrase. It recomputes the complete plan under the workspace
mutation lock; a blocked or changed plan creates nothing. Equal operational
Capability identities and equal pinned canonical Flows are reusable. Same-id
differences and ambiguous existing portable Flow ids are conflicts. V1 never
overwrites, updates or deletes user resources.

All Flow/Capability references are validated before the first write. A handled
failure rolls back only the resources created by that request, in reverse
dependency order. This is not a cross-process transaction: automatic update,
uninstall, remote discovery, signature trust and crash-journal recovery remain
outside A019. The companion owns bundle content and consent UX; Symphlo owns
generic validation, collision policy and persistence and contains no office
Case semantics.

### A020: redacted Run outcome handback

`GET /api/v1/runs/{run_id}/outcome` projects immutable Run metadata and current
Evidence into exact `symphlo.run-outcome.v1`. The projection contains Run/Flow
identity, active or terminal status, timestamps, settled/total progress, ordered
Node ids/types/statuses, accepted Artifact references and only the bounded failure
codes `evaluation_rejected | node_failed | run_failed`.

This is a companion read model, not a second Runtime. It creates no persistence or
mutation and never returns accepted payloads, Context, event bodies, failure text,
Artifact bytes or local paths. Artifact references remain bound to the existing
versioned content endpoint and SHA-256. Unknown, malformed, duplicated or
inconsistent internal evidence fails closed. The current pending/skipped suffix
projection is explicitly linear-Flow semantics and must be versioned or redesigned
before branching is introduced.

The Personal Assistant companion proves the complete public loop: confirmed Run
admission, active/terminal outcome reads, ordered Node progress, bounded failure,
and successful verified `result.md` retrieval without database or source-path
coupling.

### A021: exact Run cancellation handback

`POST /api/v1/runs/{run_id}/cancellations` accepts only exact
`symphlo.run-cancellation-request.v1` with the expected portable `flow_id` and
returns exact `symphlo.run-cancellation.v1`. The route binds both identities,
rejects query/schema/version drift, and reuses `LocalWorkspace.cancel_run` plus
the existing Runtime cancellation token and durable Evidence transitions.

Only a real transition from `running` into `cancel_requested | cancelled`
returns HTTP 202 with `accepted=true`. Repeats, terminal Runs and
natural-completion races return HTTP 200 with `accepted=false` and the actual
status. A terminal Run is immutable. This makes cancellation observable and
controllable by a local companion without exposing Console-private routes or
introducing a second scheduler, controller or persistence model.

### A022: redacted Run history handback

`GET /api/v1/run-history` accepts only 1..32 unique exact `flow_id` query values
and one `limit` in 1..100. It returns newest-first exact
`symphlo.run-history.v1` summaries containing Run/Flow identity, status,
timestamps, settled/total Node counts and optional fork lineage.

The projection scans existing durable Run metadata and Evidence, validates every
matching item through `build_run_outcome`, and creates no new history store. It
never returns task title/topic, accepted payloads, Flow hash, executor, Node
identity/type, Artifact references, failure data, event bodies or local paths.
The PAA companion restricts the query to its canonical packaged Flow ids and
opens a selected item through the existing outcome/result/cancellation contracts;
history lookup never admits or reruns work.

### A023: installable Local App assets

A locally built Python wheel carries the reviewed Vite `flow-console`, the
deterministic `symphlo.agent-session.v1` fixture and a `symphlo` command. Local
App asset resolution is explicit and deterministic: an explicitly injected
Web root is authoritative, a valid source-checkout `apps/web/dist` is preferred
for development, and the installed package is the final fallback. A clean
installed process therefore needs only an existing workspace directory; it
does not need the source repository, Node.js or pnpm at runtime.

Wheel construction remains a release-engineering check rather than package
publication authority. It requires a fresh locked Web build and fails closed
when any required page asset or the session fixture is missing. Package
publication, GitHub Release creation, signing and stable-version claims remain
explicit non-goals without a separate owner review.

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
- A general branching atomic LLM-call graph or replacement for every Agent Runtime.
- Automatic retry/repair, changed-Flow replay, automated failure localization or a complete Agent debugger beyond the implemented Evaluation gate and exact same-Flow Node fork.
- Cross-Run or restart-time external conversation resume.
- Third-party-derived source, assets, backend, runtime, database, provider or design import.
- Internal integrations, Pilot material, company identity or private adapter publication.
- Bundling or managing an external Agent installation or credential.
- Remote bundle discovery, automatic bundle update/uninstall, overwrite install or a package-signature trust chain.
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

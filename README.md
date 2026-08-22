# Symphlo

> Open-source Local Alpha under the Apache License 2.0.

[![CI](https://github.com/huisezhiyin/symphlo/actions/workflows/ci.yml/badge.svg)](https://github.com/huisezhiyin/symphlo/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-local%20alpha-orange.svg)](#current-local-alpha-boundary)

## Durable Flow for multi-Agent and multi-application collaboration

Symphlo coordinates durable work across Agents, applications, tools and Humans.
It provides explicit task ownership, accepted Context, effects, handoffs,
evaluation, recovery and Artifacts without taking over how each participant
does its work.

Fixed, repeated and long-running processes are important uses, but not the
whole product. Symphlo is equally about multi-Agent and multi-application
collaboration when work must cross executor or session boundaries and remain
observable, replaceable and maintainable.

Agents are good at looping: inspect, reason, use tools, revise and continue.
Symphlo can externalize selected high-level phases of that loop when the added
boundary has collaboration or operational value.

Symphlo lets you **externalize selected high-level phases of an Agent's inner
loop** into a durable outer loop. Its task granularity can slide from one broad
Agent Node to multiple observable boundaries when recovery, replacement,
maintenance or explicit handoff makes the extra coordination worthwhile:

```text
One autonomous Agent session          A Symphlo outer loop

  research                              Research Agent Node
  plan                                     ↓ accepted Context
  draft            ───────────▶          Writer Agent Node
  review                                   ↓ accepted Context
  revise                                 Reviewer Agent Node
  deliver                                  ↓ accepted Context
     ...                                  article.md Artifact
```

Granularity is also a slider between Agent autonomy and Flow orchestration:

```text
Broad Agent Node                         Explicit semantic boundaries

Flow -> [ autonomous Agent loop ]        Flow -> Research -> Draft -> Review
          Agent owns most iteration               Flow owns more handoffs

high Agent autonomy  <-------------------------------->  high Flow orchestration
```

Symphlo does not modify the Agent to move along this spectrum. It shapes work
from the outside through bounded tasks, accepted Context, result contracts,
effects, executor selection and state transitions.

This is not chain-of-thought tracing. The current Local Alpha does not split an
Agent Node into its private model calls, tool calls or turns. Each Agent Node
keeps its normal, opaque inner loop and decides **how** to finish its task.

`Slidable` does not mean automatic decomposition or a runtime Loop-depth mode.
It is a design and maintenance choice about how much of the high-level Agent
Loop is worth externalizing. Every externalized boundary persists accepted
input, executor, effects, events, result, handoff and Artifacts.

At the deliberate fine-grained limit, a Flow can now bind an explicit
`model.task` to a saved `model_cli`. Each such Node sends exactly one bounded
`symphlo.model-inference-request.v1` to one adapter process and accepts one
exact `symphlo.model-inference-result.v1`. This lets a linear Flow own the
sequence and handoffs between model calls without inspecting or decomposing an
existing Agent's private loop. The adapter remains responsible for truthfully
mapping that one request to one provider inference.

An explicit `tool.task` can similarly bind one saved `cli`, `mcp_stdio` or
`http` Capability. It executes one fixed semantic operation and persists a
`symphlo.tool-call-evidence.v1` envelope with the Capability identity,
fingerprint and transport. MCP still performs its required handshake around one
`tools/call`; the contract promises one semantic tool operation, not one wire
message. General branching model/tool loops, dynamic tool selection and
automatic granularity conversion are not implemented in this Local Alpha.

Externalization also opens execution supply. Each boundary can deliberately
bind the right Agent, application, HTTP service, MCP tool, CLI, local script or
Human. Different participants can therefore collaborate through explicit,
inspectable handoffs instead of relying on one opaque session or several
disconnected applications.

This gives users understandable steps, live state, problems and deliverables.
It gives developers versioned contracts, replaceable executors and comparable
Run evidence. Symphlo rejects hope-based orchestration. It provides
maintainable control instead of merely waiting for an Agent or LLM to work
everything out.

**Flow controls `what / who / when / dependencies / authority / handoff`.
Each Agent or application controls `how`.**

Symphlo is developed alongside
[Clerklet](https://github.com/huisezhiyin/clerklet), the separate standalone
Agent. Clerklet is an optional reference participant, not a bundled prerequisite
or the owner of Symphlo state. The historical `huisezhiyin/agent-flow` project
is retired.

## Run it in five minutes

You need Git, `make`, [`uv`](https://docs.astral.sh/uv/), Python 3.12,
Node.js 24 and pnpm 11.6.0. You do not need Docker, a model account or an API
key. `make desktop`
installs the locked dependencies, builds the App and opens a native Symphlo
window with its own Local Runtime.

```bash
git clone https://github.com/huisezhiyin/symphlo.git
cd symphlo
make help
make doctor
make desktop
```

`make help` is a zero-dependency command map. `make doctor` checks Python,
Node.js, pnpm, temporary-state access and whether optional Codex/OpenCode
executables are discoverable; missing Agents do not block the offline demo.

`make desktop` opens the complete Local product as an independent Desktop App.
The Desktop process owns an ephemeral IPv4 loopback Runtime, invokes the
selected deterministic/Codex/OpenCode executor, and terminates the Runtime when
the App exits. Start from the canonical task on Home. Its zero-credential
Golden Flow is:

```text
Plan
  -> Draft in worker_loop
  -> Review as a durable outer-loop boundary
  -> Revise in the same worker_loop conversation
  -> article.md
```

Draft and Revise are separate Agent Nodes backed by a bundled fictional process
fixture. Runs proves that they share one opaque conversation reference while
keeping distinct turn references and accepted Context. The fixture proves the
real `symphlo.agent-session.v1` process boundary; it is deterministic and does
not claim model quality or a bundled AI provider.

Inspect the Flow and Canvas, run it, then open Runs. Select Draft and Revise to
compare their session evidence, select Review to see the durable handoff between
them, and open `article.md`. Every Run persists accepted Node results and the
Artifact outside the repository beneath the App's user-data directory.

For Web-only development, `make app` serves the same Console and Runtime at
`http://127.0.0.1:8765`. It is a development profile, not a different product.

To verify the installable Python distribution locally, run `make wheel`. This
first builds the reviewed Vite App, then creates `dist-python/*.whl` with the
complete `flow-console`, the deterministic session-protocol fixture and a
`symphlo` command. After installing that wheel, an existing empty directory is
enough to start the loopback App:

```bash
symphlo app --workspace /path/to/local-workspace
```

The installed App does not need the source checkout, Node.js or pnpm at
runtime. Building the wheel still requires the locked Web toolchain. This is a
local distribution verification path, not a published package, signed
installer, stable-version claim or bundled external Agent.

The native Desktop acceptance target is currently macOS on Apple silicon.
The Runtime, terminal demo and Web App use portable contracts, and CI targets
Ubuntu 24.04. The full Python Runtime suite, including Agent process-tree and
session cancellation plus MCP stdio, also passes on a Windows local checkout;
native Windows Desktop and native Linux package acceptance remain unvalidated.
`make desktop-package` produces an unsigned macOS App; signing, notarization,
installers and automatic updates are outside this Alpha.

Prefer a terminal-only proof of task granularity and repeatability? `make demo`
runs a balanced deterministic writing Flow twice and prints two useful local
URLs:

```text
article=file:///.../artifacts/<run-id>/article.md
report=file:///.../evidence/index.html
```

Use `make demo-open` to open the read-only file version automatically. Its
Canvas shows the outer Agent loop, its Timeline replays persisted events, and
its Evidence Panel exposes every accepted input, result, executor, effect,
handoff and Artifact without exposing private Agent reasoning. Creating a new
Run from the read-only file report requires `make desktop` or
`make app` because a `file://` page has no Runtime host.

For the first run, inspect four things:

1. open `article` to see the accepted deliverable;
2. open `report`, press **Replay**, and watch the accepted Run move across the Canvas;
3. select a Node to inspect its input, effects, executor, result and events;
4. switch Run 1 and Run 2 to see what the Runtime, rather than a conversation,
   owns as durable truth.

All generated state stays in a temporary directory outside the repository. To
keep it, provide an empty directory:

```bash
make demo STATE_DIR=/tmp/symphlo-demo
```

Symphlo refuses to overwrite a non-empty state directory.

## Slide the Agent-task granularity

The same writing goal can use three immutable Flow definitions over the same
Runtime and `article.md` contract:

| Profile | Observable Agent-role Nodes | Use it when |
| --- | --- | --- |
| `compact` | Writer | one executor can own the entire inner loop |
| `balanced` | Planner → Writer → Editor | plans and drafts are useful handoff boundaries |
| `fine` | Researcher → Planner → Writer → Reviewer → Reviser | each phase needs separate evidence, recovery or replacement |

Try them:

```bash
make demo GRANULARITY=compact
make demo GRANULARITY=balanced
make demo GRANULARITY=fine TOPIC="Why long-running Agent work needs durable state"
```

This is **sliding task granularity**, not “the more Nodes, the better.” Add a
boundary when it improves observation, recovery, executor replacement or
maintenance. Keep work inside an Agent's inner loop when an extra handoff would
only add ceremony.

A boundary must earn its coordination cost. It creates another contract,
handoff and failure surface, so externalize a phase only when its independent
evidence, recovery, replacement or maintenance value is greater than that cost.

## Where Symphlo is stronger

One autonomous Agent session is often the simplest answer for open-ended,
exploratory or disposable work. A Skill is excellent for packaging reusable
execution knowledge. Neither is automatically a durable operating model for a
task that must run again and again.

Symphlo becomes valuable when work has one or more of these properties:

- **fixed orchestration** — known phases, approvals, effects or deliverables;
- **multi-participant collaboration** — Agents, applications, tools or Humans
  must consume each other's accepted output;
- **high repetition** — the same work must run consistently with new inputs;
- **long chains** — work crosses many steps, executors, failures or conversations;
- **important handoffs** — an accepted result must be inspected before the next phase;
- **maintenance pressure** — teams need to compare Runs and replace unstable steps.

In these scenarios, an explicit outer Flow can be more reusable and operable
than a loose Skill invocation or one long autonomous Agent session. The user
entrypoint can still remain simple: a natural-language goal or one command.

### Bounded intelligence for repetitive office work

Many useful tasks need less autonomy than a general-purpose Agent and more
judgment than a deterministic script: classify changing emails, extract fields
from documents, draft a response, assemble a report or flag an exception. The
best shape is often a deterministic process skeleton with bounded Agent or
Capability Nodes only where interpretation is valuable.

An ordinary operator should be able to choose a proven task, provide materials,
confirm sensitive effects and receive a familiar deliverable. Flow authors and
developers can inspect the deeper contracts and evidence. The goal is not a
cheaper low-quality Agent; it is repeatable intelligent work with predictable
boundaries.

### Bounded evidence with QwenWork

A small, unscored development evaluation tested this positioning with QwenWork
on synthetic, sandboxed office tasks:

- ordinary-task acceptance was direct 3/4, Skill available 4/4 and Symphlo 4/4;
- on three paired inputs for one fixed 18-Node expense procedure, both direct
  and Symphlo accepted 3/3, while median elapsed time was 136.729s versus
  22.073s and median Agent operational calls were 24 versus 2;
- two later frozen nominal/fault families completed all 12 Native,
  Skill-available and Symphlo positions with one task per position and zero
  provider retry; Symphlo used a median one Agent operational call in both
  families versus 14/12 Native/Skill calls for periodic business and 9/8 for
  expense audit;
- one successful conversation was converted into a reviewed Flow and accepted
  2/2 live replays, including one bounded read-timeout recovery.

These are case-bounded engineering observations, not an official benchmark or
a population-level superiority claim. Raw provider evidence remains private,
task-scoped token telemetry was unavailable, and the sample is small. The
[report](docs/vision/qwenwork-bounded-evaluation.md),
[methodology](docs/vision/qwenwork-bounded-evaluation-methodology.md) and
[sanitized per-Run data](docs/vision/qwenwork-bounded-evaluation-summary.json)
make the supported claims, exclusions and limitations explicit. Recompute the
published aggregates from a clean checkout:

```bash
python3 scripts/recalculate_qwenwork_evaluation.py
```

### Debug Agent work from the outside

Symphlo can also wrap one existing Agent as a broad black box, persist its
accepted input and output, and then externalize recurring failure or review
points into narrower Nodes. Context snapshots, executor identity, events,
Artifacts and comparable Runs make it possible to isolate an unstable phase,
replace its Agent or tool and measure the result without exposing private
reasoning.

The current Alpha provides the evidence foundation, cross-Run comparison, an
explicit Evaluation gate and an exact same-Flow Node-level fork. A read-only
evaluator can reject one accepted candidate, stop downstream publication and
point repair at the candidate producer. The user can then create a child Run
that reuses its accepted prefix and re-executes generation, evaluation and
downstream work. Automatic retry, automatic repair and full failure
localization remain future debugger capabilities.

The Runs page can now compare two distinct terminal Runs from the same Task and
exact Flow hash. It shows whether each Node changed in accepted input, outcome,
executor, effects, accepted result, evidence level or execution/reuse mode, then
identifies the first durable boundary with a substantive difference. The report
contains no accepted payload, payload hash, Context, event body or Artifact path.
It tells you where observable evidence first diverged—not why an Agent reasoned a
certain way and not an automatically proven root cause.

The same read-only contract is available to local clients:

```text
GET /api/v1/runs/{left_run_id}/comparison?other_run_id={right_run_id}
```

Parent/fork comparisons treat a reused prefix as the same accepted outcome while
still showing its changed execution mode, so the rerun target can become the first
substantive divergence instead of falsely blaming the reused prefix.

### Choose the right operating model

| Use | Best when | Owns durable cross-step truth? |
| --- | --- | --- |
| One Agent | work is open-ended, exploratory or disposable | usually no |
| A Skill | an Agent needs reusable instructions, tools and conventions | no; it improves `how` |
| A Symphlo Flow | phases repeat, handoffs matter or work must survive sessions | yes; Flow, Run, Context and Artifacts |

These layers compose. A Symphlo Node may invoke a Skill inside an Agent's normal
loop. The distinction is ownership: execution knowledge can remain inside the
Node while accepted task state remains outside it.

An Agent or another client may recommend one of these operating models, but a
recommendation is not Run truth. It must identify observable task properties,
distinguish a suggested granularity from an actually available Flow, and never
silently execute or label a compact Flow as balanced/fine. Symphlo begins owning
truth only when an explicit saved Flow is validated and a Run is admitted.

### Admit a confirmed client handoff

A local client may turn its already-confirmed plan into a real Run through the
generic versioned endpoint:

```text
POST /api/v1/flows/{portable_flow_id}/runs
{
  "contract_version": "symphlo.run-request.v1",
  "executor": "deterministic",
  "inputs": { ... }
}

202 Accepted
{
  "contract_version": "symphlo.run-admission.v1",
  "flow_id": "<portable_flow_id>",
  "run_id": "<durable-run-id>",
  "status": "running"
}
```

This route does not install, generate or select a Flow by similarity. It
requires exactly one saved Flow whose portable DSL `id` matches the request;
zero matches return not found and multiple matches fail as ambiguous. Declared
inputs are still validated by the existing saved-Flow compiler and the same
Runtime admission path. The HTTP request is the caller's explicit execution
action—not proof that an earlier recommendation had authority—and the Local
API remains loopback-only.

The companion Personal Assistant now exposes this boundary through its own
loopback plan UI: it renders the exact task inputs, suggested granularity,
effects and Flow availability, invalidates the plan when form inputs change,
and submits this endpoint only after an explicit checkbox and button action.
That UI remains a client-owned authority surface; Symphlo still receives only
the generic versioned request and admits it through the normal saved-Flow path.

After admission, a companion that already owns the exact `run_id` can track the
Run without consuming full Evidence:

```text
GET /api/v1/runs/{run_id}/outcome
```

The exact `symphlo.run-outcome.v1` response contains only Run/Flow identity,
terminal or active status, settled/total progress, ordered Node status, accepted
Artifact references and a bounded failure classification. It never returns
accepted input/output, Context, event bodies, error messages or local paths.
Successful clients may fetch the referenced Artifact from the existing versioned
content endpoint and verify its declared SHA-256. The Personal Assistant uses this
contract to show Node progress and a verified `result.md` in its own page; it does
not read Symphlo storage or reconstruct Runtime state.

The same exact identity can request cancellation without using the Console's
private route:

```text
POST /api/v1/runs/{run_id}/cancellations
{ "contract_version": "symphlo.run-cancellation-request.v1", "flow_id": "<portable_flow_id>" }
```

The exact `symphlo.run-cancellation.v1` receipt binds `run_id` and `flow_id` and
reports the actual status. A newly accepted durable transition returns HTTP 202
with `accepted=true`; repeats, natural-completion races and terminal Runs return
HTTP 200 with `accepted=false`. Terminal state is never rewritten. This public
route reuses the existing Runtime cancellation token and Evidence transitions;
it is not a second controller.

A companion can also recover a bounded, redacted history for exact portable Flow
identities:

```text
GET /api/v1/run-history?flow_id=<portable_flow_id>&limit=20
```

Repeated `flow_id` values query up to 32 exact Flows and the limit is 1..100.
The exact `symphlo.run-history.v1` response is newest first and contains only
Run/Flow identity, status, timestamps, settled/total Node counts and optional
fork lineage. It excludes task title/topic, inputs, Flow hash, executor, Node
identity, Artifacts, failures, events and local paths. Each item is validated
through the same outcome projection; malformed matching history fails closed.

If the resolved Flow contains `write_local` or `write_external`, the first request
does not create a Run. The Local API returns HTTP 428 with
`symphlo.effect-authorization-required.v1`, binding the exact Flow semantic hash,
accepted input hash and pending Node/effect scope. A local client must show that
scope to the user and retry with `symphlo.authorized-run-request.v1` plus the exact
server-issued `symphlo.effect-authorization.v1`. Stale inputs, changed Flows and
tampered scopes fail closed with zero Run.

This token records explicit intent; it is not login, identity or a signature. The
Web Console performs the challenge/confirm/retry interaction automatically. The
terminal command profile is equally explicit:

```bash
make demo AGENT_COMMAND="..." AUTHORIZE_WRITE_EFFECTS=1
```

Runtime-owned Markdown Artifact publication remains exempt; arbitrary Agent, Tool
or Model executors cannot claim that exemption. Read-only Personal Assistant Flows
declare exact non-write effects and therefore keep their existing one-confirmation
client experience.

### Fork a failed Run from one Node

The Runs page exposes this action only for a failed Run and requires an effects
confirmation. The same strict loopback contract is available to local clients:

```text
POST /api/v1/runs/{parent_run_id}/forks
{
  "contract_version": "symphlo.run-fork-request.v1",
  "from_node_id": "failed-node-id"
}

202 Accepted
{
  "contract_version": "symphlo.run-fork-admission.v1",
  "parent_run_id": "<immutable-parent>",
  "run_id": "<new-child-run>",
  "from_node_id": "failed-node-id",
  "status": "running"
}
```

Forking is fail-closed: the parent must be terminal, the current saved Flow
must have the exact parent semantic hash, every prefix Node must have succeeded,
and an Agent session group may not cross the fork boundary. Prefix Nodes appear
as `reused` with zero attempts. Their effects do not repeat; the selected Node
and downstream effects do. The parent Run and its Artifacts are never changed
or copied.

### Gate a candidate without changing its Agent

An explicit Evaluation Node lets a Flow control whether one accepted candidate
may continue:

```text
producer Agent or Model
  -> evaluation.task bound to read-only evaluator_cli
       pass -> downstream Node / Artifact
       fail -> durable evidence + stopped suffix
              -> user-confirmed fork from producer
```

The evaluator receives the immutable Flow input and immediate candidate through
`symphlo.evaluation-request.v1`, then returns exact
`symphlo.evaluation-result.v1` evidence. A pass must have no findings; a fail
must have one or more bounded, uniquely coded findings. Evaluator capabilities
cannot declare local or external write effects.

A valid fail does not publish an Artifact and does not trigger an automatic
loop. The Runs page says that evaluation was rejected, shows a bounded summary,
and targets the producer rather than merely rerunning the evaluator. The
evaluator's judgment is orchestration evidence, not proven truth or root cause.

## Multi-executor collaboration without theatre

An Agent is a first-class Node executor. Different Nodes may resolve to
different Agents, or to the same Agent with different task contracts. The
same contracts also admit applications, MCP, HTTP, CLI, scripts, compute and
Humans. The product proof is not the number of Agent logos or connected apps.
It is the durable boundary:

- accepted input and Context;
- declared effects and authorization;
- exact executor id and version;
- ordered events and terminal state;
- accepted Result and downstream handoff;
- inspectable Artifacts and comparable Run evidence.

A session-capable Agent adapter may also bind selected Nodes to one explicit
`session_group`. The Runtime then proves that those separate task boundaries
used the same opaque external conversation and different turn references.
Nodes without a group remain one-shot, and a grouped Node bound to a one-shot
executor fails validation. Conversation continuity is executor evidence, not a
replacement for accepted Context, Run state or Artifacts.

A concrete companion integration now uses the same saved one-shot
`agent_cli` Capability for two different Action Items roles. The first Node
accepts documents and returns a strict, evidence-backed candidate envelope;
the second receives that durable `agent_output` handoff, re-reads the original
documents and publishes a reviewed `result.md`. This proves that role-specific
Agent Nodes and inspectable handoffs can externalize `extract -> review`
without changing either Agent's private loop or adding Case semantics to the
Runtime. It does not claim heterogeneous providers or real-model quality.

The same companion also provides a fine-grained alternative with two explicit
`model.task` Nodes. Its adapter handles one candidate operation or one review
operation per request and calls its configured `Model.complete` exactly once.
The balanced Flow remains the autonomous two-Agent option; the fine Flow moves
the observable `extract -> review` sequence into Flow ownership. They are two
truthful operating modes, not aliases.

The terminal demo uses deterministic role simulators and labels every Node
`E1_DETERMINISTIC`. The Desktop Golden Flow additionally invokes the fictional
session protocol fixture as `E2_REAL_EXECUTOR`; that label proves a real process
boundary, not a real model. Neither path pretends that several heterogeneous
Agents collaborated.

## Run with a real Agent CLI

Two reference presets have completed the real balanced Planner → Writer →
Editor Flow locally:

```bash
# Requires an installed and authenticated Codex CLI.
make demo-codex

# Requires an installed OpenCode CLI with a working provider.
make demo-opencode
```

Live presets default to one Run to keep time and model usage bounded. Set
`LIVE_RUNS=2` to produce cross-Run comparison evidence. Codex defaults to the
live-validated `gpt-5.4` model on Codex CLI 0.133.0; override it when your CLI
supports a different model:

```bash
make demo-codex CODEX_MODEL=your-supported-model LIVE_RUNS=2
```

The Codex preset is ephemeral and requests a read-only sandbox. The OpenCode
preset starts one authenticated loopback server per Node, sends the Prompt only
in an HTTP JSON body, disables discovered tools and runs in a disposable task
workspace. OpenCode still owns provider configuration and local state, and its
permission system is not a security sandbox. Symphlo persists the exact CLI
version, adapter protocol, workspace profile and fingerprint with every accepted
Node result.

If a live command fails, run `make doctor` first. It proves executable discovery
and the offline path, not provider authentication or model availability.

## Discover and bind local capabilities

Open **Capabilities** in the Desktop App to turn local execution supply into
versioned Node bindings:

1. discover installed Codex/OpenCode CLIs and user-local Agent descriptors, or add a trusted capability;
2. validate and probe it without saving;
3. explicitly save it into the user-local Capability Catalog;
4. add or select a Node on Canvas and bind a compatible capability;
5. save and run the Flow, then inspect the executor identity, effects, result
   and events in Runs.

An optional `agent-cli-descriptors.json` in the Local App's external state
directory can describe another installed Agent without adding provider names,
paths or credentials to the Git source tree. Discovery proves executable
identity and version only. After saving, **Test connection** runs any fixed
non-mutating readiness probe declared by that descriptor. The external Agent,
account, daemon and provider configuration remain user-owned state.

Descriptors may opt into the provider-neutral
`symphlo.agent-session.v1` protocol through a user-local adapter. Such an
adapter receives a bounded JSON request over stdin and returns final text plus
opaque conversation and turn references. Provider commands and credentials
remain outside the public source tree.

The Local Alpha supports five kinds:

| Kind | Node | Contract |
| --- | --- | --- |
| `agent_cli` | `agent.task` | bounded stdin/argv/session adapter, or pinned managed OpenCode loopback protocol |
| `model_cli` | `model.task` | one exact model-inference request/result over stdin |
| `cli` | `tool.task` | one JSON request on stdin; JSON or text on stdout |
| `mcp_stdio` | `tool.task` | MCP initialize and one `tools/call` in a bounded session |
| `http` | `tool.task` | one fixed GET/POST request and bounded JSON response |

`capability.task` remains a compatibility alias for previously saved non-Agent,
non-Model Flows. New Canvas Nodes and public examples use `tool.task` so the
Flow and Run Evidence identify the tool boundary directly.

A saved Flow may declare typed `inputs`. At Run admission, Symphlo resolves
declared defaults and caller-supplied values, rejects undeclared or mismatched
values, and adds the accepted values to durable Node Context. The historical
`report_focus` input still maps to the writing demo's `topic`; other declared
inputs remain provider-neutral Context fields.

The Runs page turns those declarations into a generated form for `string`,
`number`, `integer`, `boolean`, `object` and `array` values. It shows each
field's description and required/default state, parses JSON fields locally and
blocks invalid input before Run creation. This lets a Case-owned Flow expose a
small, office-friendly task form without adding its business semantics to
Symphlo.

The built-in Markdown publisher preserves the canonical writing contract as
`article.md`. For a generic Agent Node that returns only `agent_output`, it
publishes the accepted text as `result.md`. This lets user-local Agents prove a
non-demo Flow without adding their Case semantics to the Runtime.

Every Local Runtime also exposes a credential-free `http.sample-json`
Capability. It sends accepted context through a real loopback POST and returns
deterministic JSON, making it suitable for testing the HTTP Capability
boundary. It is a transport sample, not an article-quality or policy Gate. Its
loopback URL and sample fingerprint are refreshed when Desktop starts on a new
ephemeral port; normal saved Capability fingerprints do not change.

CLI and MCP use fixed argument vectors with no shell. Saved definitions pin an
immutable fingerprint. Secrets, automatic installation, remote MCP and
arbitrary shell commands are intentionally outside this Alpha. A saved Flow
that references a Capability prevents its deletion.

Most importantly, the Canvas is executable rather than decorative. Symphlo
compiles the exact saved linear Flow and Node bindings into the canonical
Runtime contracts. Unsupported branches or Node types fail validation instead
of silently running a different built-in Flow.

The repository includes credential-free CLI and MCP fixtures documented in
[`examples/capabilities/README.md`](examples/capabilities/README.md) for contract testing.

### Install a companion integration bundle

A trusted local companion can install a reviewed set of Capabilities and portable
Flows without copying JSON by hand. Symphlo first returns a read-only plan that
classifies every resource as `create`, `reuse` or `conflict`:

```text
POST /api/v1/integration-bundles/preview
POST /api/v1/integration-bundles
```

The install request must repeat the canonical bundle hash and the exact
server-derived confirmation phrase. Symphlo recomputes the whole plan while
holding the local mutation boundary, refuses blocked plans, and never overwrites,
updates or deletes an existing resource in v1. Compatible definitions are reused
idempotently; the first conflicting Capability or Flow keeps the install blocked.

Preview validates Flows against the proposed post-install Capability set before
anything is saved. If a handled install request fails after creating resources,
Symphlo rolls back the resources created by that request. This is request-level
rollback, not a crash-recovery journal or a remote package marketplace. The API
remains loopback-only and the companion remains responsible for the bundle's
publisher, contents and user-facing consent surface.

### Bind another command executor

The optional E2 profile can run one user-installed Agent command at every
Agent-role Node. The command reads a bounded UTF-8 task prompt from stdin and
writes its accepted text result to stdout:

```bash
make demo \
  GRANULARITY=balanced \
  AGENT_COMMAND='your-agent-command --read-prompt-from-stdin'
```

Use `AGENT_TIMEOUT=300` to change the per-Node timeout. Symphlo fingerprints the
argument vector into the immutable Flow identity, executes it with `shell=False`
and records accepted Node output as `E2_REAL_EXECUTOR`. It does not store the raw
command arguments, stderr content, credentials or environment values.

The repository includes a deterministic external-process fixture to verify the
stdio protocol without installing an Agent:

```bash
make demo AGENT_COMMAND="$(uv python find 3.12) examples/agents/stdio_fixture_agent.py"
```

E2 means a real child process produced the accepted output. It does not by
itself prove that the command is an AI Agent or that its output is high quality.

**Security boundary:** the command inherits the current environment and runs in
the selected workspace. Symphlo does not sandbox it. Agent Nodes therefore
declare broad `execute_process`, local/external read and local/external write
effects. Bind only an executable you trust, and never place credentials directly
in the command string.

## What gets persisted

Each demo produces:

```text
evidence.sqlite3
artifacts/<run-id>/article.md
evidence/
  flow.json
  run-<n>.json
  comparison.json
  index.html
```

Flow definitions, Run state, Node evidence, Context, events and Artifacts are
the task's source of truth. Conversations and private Agent sessions are
execution details.

Desktop and Web admit one active Local Run asynchronously, show its live Step
states immediately and keep polling durable evidence. **Stop** first records
`cancel_requested`; a process-backed executor is terminated and reaped before
the Run becomes `cancelled`, while an in-flight HTTP call remains bounded by
its timeout. Cancellation prevents later Nodes and unaccepted results from
progressing—it does not undo external effects that already happened.

## Current Local Alpha boundary

Implemented now:

- Python 3.12 clean-room Local Runtime;
- immutable linear Flow and exact executor resolution;
- SQLite Run, Node, Context, Event and Artifact evidence;
- asynchronous live Run admission, durable cancellation and process-boundary cleanup;
- exact same-Flow Node-level fork with immutable lineage and reused-prefix evidence;
- exact same-Flow terminal Run comparison with redacted per-Node differences and first-divergence location;
- exact redacted `symphlo.run-outcome.v1` tracking for companion-owned Runs and accepted Artifact references;
- explicit `evaluation.task -> evaluator_cli` pass/fail control with durable rejection evidence and producer-targeted repair;
- optional same-Run Agent session groups with persisted bind/reuse evidence;
- explicit atomic `model.task` and `tool.task` boundaries with versioned accepted evidence;
- Runtime-owned pre-admission authorization for exact `write_local | write_external` scopes, including fork suffixes;
- compact, balanced and fine multi-Agent writing profiles;
- deterministic offline executors, live-validated Codex preset, managed OpenCode loopback preset and generic E2 stdio commands;
- a user-local Capability Catalog with Agent CLI discovery and manual CLI, MCP stdio and HTTP bindings;
- exact loopback integration-bundle preview/install with create/reuse/conflict planning, explicit confirmation and request-failure rollback;
- an App-owned React Home / Flow / Runs product with a versioned loopback Local API;
- a ReactFlow Canvas whose supported saved linear graph is the exact Runtime Flow, plus a real evidence workspace for Run switching, ordered events, Context, Node results and Artifacts;
- zero-dependency command help, safe readiness checks and concise expected-error output;
- a locally buildable Python wheel carrying the complete Local App assets and
  deterministic session fixture, with an installed `symphlo` entry point;
- zero-credential Quick Start plus Python and strict TypeScript tests.

Not implemented yet: provider SDK adapters, automatic retries/repair, branching,
parallelism, general mid-Run or remote approvals, a general graph builder, remote Control Plane
or Server deployment. General atomic model/tool decision loops, dynamic tool
selection, automatic granularity conversion, changed-Flow replay and a complete Agent
debugging suite are also outside this Alpha. The current Local API is versioned
but loopback-only.
The Canvas is an App-owned editor for the supported linear subset of a portable
Flow contract; persisted Flow DSL and Runtime evidence, not React state, remain
the source of truth.

Validate everything locally:

```bash
make check
```

## Read next

- [`docs/vision/observable-outer-agent-loop.md`](docs/vision/observable-outer-agent-loop.md) — the complete viewpoint.
- [Why General-Purpose Agents Are a Trap](https://github.com/huisezhiyin/sdd-riper/blob/main/docs/general-purpose-agents-are-a-trap.md) — the Chinese-language background essay behind the product motivation.
- [`docs/demo/README.md`](docs/demo/README.md) — demo and evidence guide.
- [`PROJECT_SPEC.md`](PROJECT_SPEC.md) — durable product and architecture contract.
- [`LICENSE`](LICENSE) — Apache License 2.0 terms.
- [`NOTICE`](NOTICE) — Symphlo copyright notice.
- [`PUBLIC_SOURCE_MANIFEST.md`](PUBLIC_SOURCE_MANIFEST.md) — exact public source boundary.
- [`THIRD_PARTY.md`](THIRD_PARTY.md) — dependency and optional executor inventory.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — contribution scope and validation.
- [`SECURITY.md`](SECURITY.md) — vulnerability reporting and security boundary.

Symphlo is an Apache-2.0 open-source Local Alpha. Passing the demo and source
checks proves the tested technical boundary; it does not imply a stable API,
signed installer, production support or bundled model/provider.

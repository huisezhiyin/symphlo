# Symphlo

> Open-source Local Alpha under the Apache License 2.0.

## A slidable, observable outer loop for durable Agent work

Agents are good at looping: inspect, reason, use tools, revise and continue.
That autonomy is exactly what makes them useful—and what makes fixed, repeated
or long-chain work difficult to operate when everything stays inside one Agent
session.

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

This is not chain-of-thought tracing. Symphlo does not split model calls, tool
calls or turns. Each Agent Node keeps its normal, opaque inner loop and decides
**how** to finish its task.

`Slidable` does not mean automatic decomposition or a runtime Loop-depth mode.
It is a design and maintenance choice about how much of the high-level Agent
Loop is worth externalizing. Every externalized boundary persists accepted
input, executor, effects, events, result, handoff and Artifacts.

Externalization also opens execution supply. Each boundary can deliberately
bind the right Agent, HTTP service, MCP tool, CLI, local script or Human.
Different Agents and capabilities can therefore collaborate through explicit,
inspectable handoffs instead of leaving one opaque Agent session to improvise
the entire chain.

This gives users understandable steps, live state, problems and deliverables.
It gives developers versioned contracts, replaceable executors and comparable
Run evidence. Symphlo rejects hope-based orchestration. It provides
maintainable control instead of merely waiting for an Agent or LLM to work
everything out.

**Flow controls `what / who / when / handoff`. The Agent controls `how`.**

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

The native Desktop acceptance target is currently macOS on Apple silicon.
The Runtime, terminal demo and Web App use portable contracts, and CI targets
Ubuntu 24.04, but Windows and a native Linux package have not been validated.
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
- **high repetition** — the same work must run consistently with new inputs;
- **long chains** — work crosses many steps, executors, failures or conversations;
- **important handoffs** — an accepted result must be inspected before the next phase;
- **maintenance pressure** — teams need to compare Runs and replace unstable steps.

In these scenarios, an explicit outer Flow can be more reusable and operable
than a loose Skill invocation or one long autonomous Agent session. The user
entrypoint can still remain simple: a natural-language goal or one command.

### Choose the right operating model

| Use | Best when | Owns durable cross-step truth? |
| --- | --- | --- |
| One Agent | work is open-ended, exploratory or disposable | usually no |
| A Skill | an Agent needs reusable instructions, tools and conventions | no; it improves `how` |
| A Symphlo Flow | phases repeat, handoffs matter or work must survive sessions | yes; Flow, Run, Context and Artifacts |

These layers compose. A Symphlo Node may invoke a Skill inside an Agent's normal
loop. The distinction is ownership: execution knowledge can remain inside the
Node while accepted task state remains outside it.

## Multi-Agent without theatre

An Agent is a first-class Node executor. Different Nodes may resolve to
different Agents, or to the same Agent with different task contracts. The
product proof is not the number of Agent logos. It is the durable boundary:

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
preset uses `--pure --format json` and accepts only text events; OpenCode still
owns any provider configuration and session data it creates. Symphlo persists
the exact CLI version and command fingerprint with every accepted Node result.

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

The Local Alpha supports four kinds:

| Kind | Node | Contract |
| --- | --- | --- |
| `agent_cli` | `agent.task` | bounded prompt over stdin or final argv |
| `cli` | `capability.task` | one JSON request on stdin; JSON or text on stdout |
| `mcp_stdio` | `capability.task` | MCP initialize, `tools/list`, `tools/call`, shutdown |
| `http` | `capability.task` | fixed GET/POST URL and bounded JSON response |

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
- optional same-Run Agent session groups with persisted bind/reuse evidence;
- compact, balanced and fine multi-Agent writing profiles;
- deterministic offline executors, live-validated Codex/OpenCode presets and generic E2 stdio commands;
- a user-local Capability Catalog with Agent CLI discovery and manual CLI, MCP stdio and HTTP bindings;
- an App-owned React Home / Flow / Runs product with a versioned loopback Local API;
- a ReactFlow Canvas whose supported saved linear graph is the exact Runtime Flow, plus a real evidence workspace for Run switching, ordered events, Context, Node results and Artifacts;
- zero-dependency command help, safe readiness checks and concise expected-error output;
- zero-credential Quick Start plus Python and strict TypeScript tests.

Not implemented yet: provider SDK adapters, retries, resume/repair, branching,
parallelism, approvals, a general graph builder, remote Control Plane
or Server deployment. The current Local API is versioned but loopback-only. The
Canvas is an App-owned editor for the supported linear subset of a portable
Flow contract; persisted Flow DSL and Runtime evidence, not React state, remain
the source of truth.

Validate everything locally:

```bash
make check
```

## Read next

- [`docs/vision/observable-outer-agent-loop.md`](docs/vision/observable-outer-agent-loop.md) — the complete viewpoint.
- [`docs/vision/qwenwork-bounded-evaluation.md`](docs/vision/qwenwork-bounded-evaluation.md) — bounded evidence for fixed, repeated office work and generated-Flow reuse.
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

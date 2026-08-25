# Project Knowledge: Symphlo

## Active Product Portfolio

Symphlo is one of two active, separate open-source products:

- [Symphlo](https://github.com/huisezhiyin/symphlo) is the durable Flow and
  collaboration control plane.
- [Clerklet](https://github.com/huisezhiyin/clerklet) is the standalone Agent.

The historical `huisezhiyin/agent-flow` project is retired. It
is not an active implementation, integration target or product truth source.
New Flow work belongs in Symphlo; new Agent work belongs in Clerklet. Historical
material may be consulted only under the repository's provenance rules and must
not be copied into either active repository by default.

## Product Identity

Symphlo makes work performed by multiple independent executors durable,
observable, controllable and maintainable. It is not limited to fixed
orchestration and it is not limited to Agents.

Fixed, repeated and long-running processes remain strong use cases, but the
broader product idea is **durable collaboration**. A Flow may coordinate:

- several Agents with different roles, tools, providers or autonomy levels;
- one Agent across several bounded task turns, using fresh conversations or an
  explicit same-Run session group according to the handoff contract;
- applications and services connected through MCP, HTTP, CLI or other adapters;
- deterministic tools, model calls, scripts, compute and local software;
- Human review, approval, exception handling and handoff.

These participants collaborate through versioned Node contracts, accepted
Context, declared effects, durable state, explicit handoffs and inspectable
Artifacts. An Agent-to-Agent conversation or an application session may help
execution, but it is not the durable source of collaboration truth.

## Flow Thesis

Flow controls `what / who / when / dependencies / authority / handoff`. Each
executor controls `how` inside its assigned boundary.

The topology may be simple or complex. It may begin as one broad Agent Node,
use a known fixed sequence, or evolve toward richer multi-participant
coordination. Runtime-effective structure and changes must remain explicit,
validated, versioned and observable; model improvisation and private sessions
do not silently become Flow truth.

Node granularity is chosen for collaboration value. Make a boundary explicit
when it creates useful ownership, observation, authorization, handoff,
recovery, replacement, evaluation or maintenance. Do not split private model
turns or tool calls merely to make a graph look sophisticated.

The turn topology is deliberately slidable and assignable. A designer may
merge semantic work into one broad Agent Node or split a long chain into
bounded task turns. Each boundary may keep or switch the Agent, application,
Capability or Skill; accepted Context, Results, handoffs and Artifacts preserve
the complete task outside every private conversation.

The current Local Alpha implements a deliberately bounded linear subset. That
implementation boundary must be stated honestly, but it does not narrow the
long-term product identity to fixed linear automation.

## Relationship With Clerklet

Clerklet remains independently useful as an Agent and does not require Symphlo.
Symphlo remains executor-agnostic and does not require Clerklet. When composed,
Clerklet participates through the same reviewed Capability, Adapter, Runner and
API contracts as any other executor.

The integration is intentionally asymmetric:

- Clerklet owns its Agent loop, tools, task interpretation and standalone user
  experience.
- Symphlo owns Flow definitions, Run state, accepted Context, effects,
  collaboration handoffs, evaluation decisions, Artifacts and history.
- Neither repository imports the other's database, runtime internals, local
  state, credentials or source path as a runtime shortcut.

Clerklet is an important reference participant for Symphlo, not the exclusive
Agent, bundled prerequisite or owner of Symphlo product semantics.

## Reference Executor Boundary

OpenCode is the first provider-specific reference executor behind the generic
Capability/Adapter boundary. Its managed v1 transport starts one authenticated
loopback server in a disposable task workspace per Node, keeps Prompt content
out of process arguments and maps cancellation to session abort plus process
cleanup. These details are executor concerns and do not enter Flow/Run truth.

OpenCode permissions are a fail-closed tool policy, not a security sandbox.
Symphlo therefore preserves truthful external effects and treats container/VM
isolation as a separate future deployment profile rather than claiming that a
temporary directory provides host security isolation.

## Durable Decision Rules

- Treat multi-Agent and multi-application collaboration as a core product
  scenario, not an optional extension to fixed workflows.
- Keep fixed orchestration as one valuable shape rather than the definition of
  Flow.
- Keep execution supply open and replaceable behind versioned contracts.
- Keep Flow/Run/Context/Artifact history as durable product truth.
- Keep turn granularity, same-Run session continuity and executor assignment
  explicit in the Flow and Capability contracts.
- Keep Canvas and private executor sessions as projections or implementation
  details, never the source of truth.
- Distinguish product direction from current Alpha claims: future collaboration
  goals do not imply that branching, parallelism or dynamic routing is already
  implemented.

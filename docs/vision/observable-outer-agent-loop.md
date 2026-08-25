# The Slidable, Observable and Assignable Outer Agent Loop

## The missing layer is not more intelligence

An Agent is useful because it can loop. It can inspect a task, call tools,
notice that an approach failed, revise its plan and continue. That internal loop
is not a defect to engineer away. Reducing an Agent to one model call would
remove the autonomy that made it valuable.

But intelligence inside a session does not automatically create an operable
task. When important recurring work lives entirely inside one conversation or
Agent session, a team cannot reliably answer basic operational questions:

- Which input was accepted?
- Which executor acted, with what authority?
- What result crossed the handoff?
- Where did a long chain stop?
- Which part can resume without replaying everything?
- Did the next Run behave like the previous one?

Symphlo exists for that gap. It is a slidable, observable and assignable outer
loop for durable Agent work. It selectively externalizes useful high-level
phases while leaving each Agent's private inner loop autonomous. Its central
separation is:

> Flow controls what, who, when and handoff. The Agent controls how.

The Agent keeps its opaque inner loop. The outer task loop makes selected
semantic phases durable, observable and orchestratable.

The outer granularity can slide. One broad Agent task turn may own the complete
inner loop, or a long chain may become several bounded Agent task turns when
their observation, recovery, replacement, maintenance or handoff value earns
the coordination cost. Sliding is a design and maintenance decision—not
automatic decomposition, runtime graph rewriting or a Loop-depth mode.

## One durable task, many bounded Agent turns

An external Agent Node is a bounded task invocation, not a model-reasoning
step. Splitting a long chain into Nodes lets a designer choose the execution
topology at each durable handoff:

- start a fresh conversation with only accepted Context;
- reuse one explicit same-Run conversation when continuity matters;
- keep the same Agent, switch Agents or applications, or bind another Capability;
- invoke a Skill inside one turn and invoke it again in a later turn;
- persist the accepted Result and Artifact outside every conversation.

The complete task therefore no longer depends on one turn retaining every
intermediate fact, instruction, effect and correction. Turn boundaries, session
continuity and executor assignment can change while accepted task truth remains
stable.

## Externalization opens execution supply

An externalized phase is not merely visible. It becomes an independently
assignable task boundary. One Node may use an Agent with its own inner loop,
the next an HTTP service or MCP tool, and another a CLI, local script, compute
step or Human. Different Agents can collaborate because accepted Context,
results and Artifacts cross explicit handoffs rather than depending on one
conversation to remember and improvise the whole chain.

This is where observability becomes control. Users can see understandable
steps, current state, problems and deliverables. Developers can inspect exact
executor versions, replace an unstable capability and compare Runs after the
change. The system does not promise that an Agent or LLM will somehow work
everything out; it makes responsibility, evidence and maintenance explicit.

## Two loops operate on different clocks

The inner Agent loop operates on a problem-solving clock. Seconds or minutes
may contain model calls, tool use, retries and local discoveries. Its purpose is
to find a good way to complete one bounded task.

The outer task loop operates on an operational clock. It may survive hours,
days, people, executors, failures and conversations. Its purpose is to preserve
the accepted state of the work and control how responsibility moves.

Trying to make either loop own both jobs creates familiar failure modes. If the
Flow micromanages model calls and tool calls, it turns an Agent into a brittle
script. If the Agent session owns every long-lived handoff, operational truth
becomes entangled with transient conversation state.

The layers should meet at a bounded Agent Node:

```text
durable input + accepted Context + declared effects
                         |
                         v
              Agent Node: private inner loop
                         |
                         v
accepted Result + events + Context update + Artifact
```

Symphlo observes the envelope. It does not need private chain-of-thought or a
microscope over every internal action.

## Loop ownership slides without intrusion

Task granularity changes more than the number of boxes on a Canvas. It changes
who owns the observable loop.

```text
Broad Agent Node                         Explicit semantic boundaries

Flow -> [ autonomous Agent loop ]        Flow -> Observe -> Draft -> Review
          Agent owns most iteration               Flow owns more handoffs

high Agent autonomy  <-------------------------------->  high Flow orchestration
```

Symphlo does not need to modify an Agent to move along this spectrum. It can
shape work from the outside by controlling the bounded task, accepted Context,
result contract, effects, executor binding and state transition. The Agent
remains free inside its declared Node boundary, while the Flow determines what
responsibility exists before and after that boundary.

At the deliberate fine-grained limit, a different Flow design may bind
explicitly atomic model-inference and tool-invocation contracts. The Flow
Runtime can then own a decision loop that might otherwise be implemented inside
an Agent Runtime:

```text
Observe -> Model decision -> Tool -> Evaluate -> Model response -> Deliver
```

That is not surveillance or decomposition of an existing Agent's private loop.
It is a different execution contract in which the model or tool is atomic by
design. A small prompt does not prove that an `Agent Node` performs only one
model call. An atomic Model or Tool Node must say so truthfully and enforce the
contract.

The current Local Alpha stays on the semantic-task portion of this spectrum. It
supports linear Agent, Capability and Artifact tasks. It does not yet provide a
general atomic model-call graph, branching decision loop, retry/resume graph or
automatic conversion between granularities.

## Magnification, not microscopic surveillance

Imagine one writing Agent that researches, plans, drafts, criticizes, revises
and publishes. That can remain one broad Node. Or a designer can manually
externalize selected high-level phases:

```text
Research -> Plan -> Draft -> Review -> Revise -> Publish
```

The loop has been magnified into semantic boundaries that an operator can see.
The existing Agent's private activity has not been decomposed into token
windows, model calls, turns or individual tool invocations.

This distinction protects both autonomy and privacy. Observability means
accepted task evidence, not exposure of hidden reasoning. Orchestration means
reliable responsibility and handoff, not remote control of cognition.

At each external boundary, the runtime can persist what the product actually
needs to know:

- accepted input and Context;
- declared effects and authorization;
- resolved executor identity and version;
- ordered events and terminal state;
- accepted Result and downstream handoff;
- Artifact identity, location and integrity hash.

Conversation transcripts and Agent sessions may help an executor work, but they
are not the task's source of truth.

## A debugger for Agent work, not private cognition

The same granularity slider provides a practical debugging method. Begin with
one broad Agent Node and persist its accepted envelope. When repeated Runs fail
or require the same manual correction, externalize one meaningful boundary:
research, planning, review, approval or delivery. The new boundary acts like an
operational breakpoint.

This makes useful debugging evidence explicit:

- accepted Context behaves like inspectable intermediate state;
- ordered events show where durable execution stopped;
- executor identity and version reveal what actually ran;
- effects show what authority was available;
- Results and Artifacts show what crossed the boundary;
- comparable Runs reveal whether a replacement improved the task.

The operator can narrow the unstable phase, change its instructions or
executor, and compare another Run. If the boundary no longer earns its cost, it
can be merged back into a broader Agent task. The objective is not maximum
decomposition. It is the smallest observable boundary that explains and fixes
the operational failure.

This does not reveal why a model formed a private thought. It answers the more
operable questions: what input was accepted, which responsibility failed, what
output crossed the handoff and whether the repaired task now behaves better.
Node-level fork/rerun, automated evaluators, failure localization and repair are
natural extensions of this model, not claims about the current Local Alpha.

## Granularity is a design decision with an economic test

There is no universally correct Agent-task size. Symphlo therefore treats
granularity as a slider across explicit design-time Flow definitions, not as an
automatic graph-rewriting trick.

A compact Flow can assign the whole article to one Agent. This is appropriate
when the executor is trusted, failure is cheap and only the final Artifact
matters. A balanced Flow can expose planning, drafting and editing when those
handoffs deserve inspection. A fine Flow can isolate research, outline, draft,
review and revision when different executors, recovery rules or maintenance
histories justify them.

Every boundary creates value and cost.

Potential value:

1. **Observation** — the phase needs its own accepted evidence.
2. **Recovery** — later work can restart without replaying earlier phases.
3. **Replacement** — the executor may change independently.
4. **Maintenance** — comparing this phase across Runs will improve the task.
5. **Authority** — the phase needs a distinct effect or approval boundary.

Coordination cost:

1. another input/result contract must be maintained;
2. another handoff can lose information;
3. another state transition can fail;
4. another Artifact or Context entry must be inspected;
5. the Flow becomes harder for a human to understand.

Externalize a phase when its operational value is greater than this coordination
cost. If none of the value questions has a strong answer, keep the work inside
the Agent's inner loop. Maximum decomposition is not sophistication; it is often
ceremony.

## Agent, Skill and Flow own different things

The three are complementary layers:

| Layer | Primary job | Appropriate source of truth |
| --- | --- | --- |
| Agent | adaptively complete a bounded task | private working state inside the Node |
| Skill | package reusable instructions, tools and conventions | versioned execution knowledge |
| Symphlo Flow | operate work across durable semantic boundaries | Flow, Run, Context, events and Artifacts |

A Skill may make a Writer Agent much better at research or editing. It still
does not need to own the accepted draft handed to another Node, the terminal
state of the Run or the history used to compare repeated executions. Those are
outer-loop responsibilities.

A concise boundary is: **a Skill makes an Agent better inside a task turn;
Symphlo makes bounded turns, sessions, Agents, applications and capabilities
operate as one durable task.**

Likewise, a Flow should not absorb everything a Skill or Agent knows. It should
describe stable responsibility and handoff while leaving execution technique
behind the Node boundary.

This is why Symphlo can outperform a loose Skill invocation or one autonomous
session in fixed, repeated and long-chain scenarios without claiming that every
task needs a workflow.

## Multi-Agent is a contract, not a logo wall

A Flow may bind different Nodes to different Agents. It may also bind several
roles to the same Agent executable with different bounded tasks. The number of
provider logos proves nothing.

The meaningful evidence is that a Planner produced an accepted plan, a Writer
consumed that exact handoff, an Editor accepted a revised article, and the final
Artifact can be traced to its Run. Heterogeneous executors can be introduced
later where replacement or specialization has real value.

This gives teams a practical migration path. Start with one capable Agent. Make
the task boundaries durable. Observe which phases are unstable or expensive.
Replace only those executors. The task definition survives while execution
supply evolves.

## Where the outer loop wins

Symphlo is strongest when several of these conditions are present:

- **Fixed orchestration**: the high-level phases and deliverable are known.
- **High repetition**: the same operating model runs with new materials.
- **Long chains**: work spans failures, people, sessions or significant time.
- **Important handoffs**: one accepted result constrains the next phase.
- **Selective authority**: effects or approvals differ by phase.
- **Maintenance pressure**: teams need comparable Runs and replaceable steps.

In these cases, reuse means more than reusing a prompt. The system reuses the
task definition, authority model, evidence contract and maintenance history.

Consider a monthly research publication. The topic and materials change, but
evidence collection, planning, drafting, review and publication recur. A single
Agent may complete one issue brilliantly. The outer loop matters when the team
must explain which evidence was accepted, resume after an editorial rejection,
replace a weak research executor, or compare six months of Runs.

The same pattern appears in ordinary office work. An inbox triage, invoice
review, document extraction, customer-response draft or weekly report often has
a stable process, changing materials and a few places where interpretation is
valuable. These users do not need maximum Agent autonomy. They need a
deterministic skeleton with bounded intelligence, clear exceptions, human
confirmation for sensitive effects and a familiar deliverable.

This is an important product discipline. The normal operator should see the
task, materials, progress, questions and result. Flow internals, schemas,
executor fingerprints and evidence remain available to the people authoring,
operating or debugging the task.

## Where it does not win

A credible philosophy needs stop rules.

### Open-ended, disposable exploration

If a person is brainstorming once and will discard the process, one autonomous
Agent session is usually simpler. Durable intermediate boundaries add little.

### A deterministic script is already enough

If inputs, transformations and errors are fully specified, a normal program,
job queue or state machine may be the right tool. Adding Agents would introduce
uncertainty without useful adaptation.

### A Skill solves the real problem

If the only missing piece is a repeatable method inside one task, package that
method as a Skill. Do not create a Flow merely to store instructions.

### Boundaries imitate internal traces

Turning every model call or tool call into a Node produces fragile graphs and
confuses debugging telemetry with product semantics. Keep those details inside
the executor unless an operator truly needs to own the handoff.

### The process is not stable enough yet

Premature orchestration freezes guesses. Let an Agent and human explore the work
first; externalize phases after recurring responsibilities and failure points
become visible.

## Adoption should move from broad to selective

The easiest adoption path does not begin with a perfect graph:

1. **Run one broad Agent Node.** Persist its input, effects, executor, accepted
   output and Artifact.
2. **Repeat the task.** Observe where failures, reviews or manual recovery
   repeatedly occur.
3. **Externalize one valuable phase.** Give that handoff an explicit contract
   and accepted evidence.
4. **Compare Runs.** Decide whether the new boundary improves recovery,
   replacement or maintenance enough to keep it.
5. **Open execution supply gradually.** Bind another Agent, Skill, CLI, API or
   human only where the stable Node contract makes substitution useful.

This is manual separation of the original Agent loop, guided by operational
evidence. It is intentionally less magical than automatic decomposition and
more maintainable because each boundary has a reason to exist.

## Simple on the outside, rigorous underneath

Operational rigor should not force ordinary users to learn Nodes, Context,
semantic hashes or executor fingerprints. The normal entry can remain a goal,
materials and one command. People should see familiar concepts: work, steps,
executors, problems and deliverables.

The deeper evidence exists for the moments when it matters: a failure must be
recovered, a result audited, an executor replaced, or a repeated task improved.
A visual Canvas may project that truth, but it must never own it.

The ambition is narrow and practical: preserve Agent autonomy where it earns
its freedom, make durable work observable, and let teams choose exactly how much
of the loop they need to operate. Broad Nodes favor autonomous execution. Finer
boundaries favor orchestration, debugging and repeatability. The inner loop
supplies adaptive intelligence; the outer loop supplies continuity,
responsibility, evidence and bounded control.

## Background essay

The product motivation is explored more directly in the Chinese-language essay
[Why General-Purpose Agents Are a Trap](https://github.com/huisezhiyin/sdd-riper/blob/main/docs/general-purpose-agents-are-a-trap.md).
It argues for solving concrete, repeatable work with the right mix of Agents,
APIs and deterministic structure instead of treating one general-purpose Agent
as the whole product.

The essay is context, not a protocol contract. Symphlo's narrower engineering
rule remains: externalize a phase only when its observation, recovery,
replacement or maintenance value earns the coordination cost.

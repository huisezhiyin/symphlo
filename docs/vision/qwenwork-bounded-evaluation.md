# When a Flow Is More Useful Than a Skill

## A bounded QwenWork evaluation for repeated office work

General-purpose Agents are excellent at discovering how to complete a new task.
They are less attractive when the same known procedure must be rediscovered,
re-orchestrated and re-verified on every Run.

Skills help by packaging reusable instructions and tools. But a Skill still
lives inside an Agent's execution loop: the Agent decides whether and how to use
it, while the conversation usually remains the operating context. A durable
Flow owns a different layer. It makes the known steps, effects, handoffs,
accepted state and recovery policy explicit, while leaving genuine semantic
judgement inside a bounded Agent Node.

We ran a small development evaluation with QwenWork to test three practical
questions:

1. Does adding Symphlo degrade ordinary office-task quality?
2. Does it help when the procedure is long, fixed and repeated?
3. Can a user create and reuse the Flow without hand-authoring a traditional
   task-specific Skill?

The short answer is: in this bounded sample, ordinary-task quality did not
degrade; one fixed 18-step procedure became substantially faster and required
far less Agent tool work; and one successful conversation was converted into a
reviewed Flow that ran correctly on a changed input and a bounded failure.

This is development evidence, not an official benchmark score or a claim about
every Agent task. The sanitized aggregate data is available in
[the public evaluation summary](qwenwork-bounded-evaluation-summary.json).

## The result in one table

| Question | Evidence | Result |
| --- | --- | --- |
| Ordinary-task quality | Four bounded office-task cases | Direct 3/4, Skill available 4/4, Symphlo 4/4 |
| Fixed long-chain execution | Three paired synthetic expense inputs | Direct 3/3 and Symphlo 3/3 accepted |
| Speed on the fixed procedure | Same selected Agent, inputs, tools and acceptance contract | Median 136.729s direct vs 22.073s with Symphlo |
| Agent operational work | Median observed operational tool calls | 24 direct vs 2 with Symphlo |
| Generated-Flow reuse | Changed input plus bounded read timeout | 2/2 live replay accepted, zero provider retry |

## No observed degradation on ordinary office work

The ordinary-task development set contained four bounded cases. QwenWork direct
completed three, QwenWork with its task Skill available completed four, and
QwenWork with Symphlo completed four.

That result is deliberately modest. It supports case-bounded non-degradation;
it does not show that Symphlo was faster than or higher quality than a Skill on
short ordinary tasks. It also demonstrates the intended routing rule: Symphlo
does not need to win everywhere. On work where durable orchestration adds
little value, matching the existing Agent experience is enough.

## A clear advantage on fixed long-chain work

The stronger case was a synthetic expense-review procedure with 18 observable
Nodes, six business-tool kinds, intermediate Artifacts and approval effects.
Only one Node required semantic judgement from QwenWork. Flow-owned Nodes
handled the known reads, validation, reconciliation, approval package,
submission and notification.

QwenWork direct and QwenWork with Symphlo were evaluated on the same three
inputs under the same acceptance contract. Every position used one provider
task and allowed no provider retry.

| Metric | QwenWork direct | QwenWork + Symphlo |
| --- | ---: | ---: |
| Accepted | 3/3 | 3/3 |
| Median elapsed time | 136.729s | 22.073s |
| Mean elapsed time | 136.975s | 23.430s |
| Median Agent operational calls | 24 | 2 |
| Duplicate critical effects | 0 | 0 |

Across the three paired inputs, Symphlo reduced elapsed time by
79.9%–84.8%. Both configurations completed the same business-tool contract,
but the Agent no longer had to rediscover and personally orchestrate the fixed
parts of the procedure.

This is the product advantage in its proper scope:

> Agent judgement stays flexible. Repeated business structure stops being
> improvised.

## Why this can be simpler than a procedural Skill

A traditional task-specific Skill is useful reusable knowledge, but it has two
practical limitations for deterministic repeated work:

1. it is usually authored as instructions and tool guidance rather than an
   applied, observable Run contract;
2. making the Skill available does not itself make cross-step state, effects,
   recovery and accepted handoffs durable.

Symphlo does not solve this by asking office users to draw a large workflow. In
the evaluated path, QwenWork converted one successful visible conversation
into a staged FlowDraft. Symphlo then:

- validated the portable Node and capability contracts;
- supplied deterministic dependency order from Flow-owned configuration;
- showed an exact review boundary;
- required explicit Human Apply;
- reused the unchanged applied Flow on new Runs.

The generated 18-Node Flow completed two live replays:

| Replay | Result | Elapsed | What changed |
| --- | --- | ---: | --- |
| Changed business input | accepted | 28.313s | New expense content |
| Bounded read timeout | accepted | 27.028s | First read timed out, Flow recovered on the bounded second attempt |

Both Runs completed all 18 Nodes. Approval, submission and notification each
occurred exactly once. The Agent remained responsible for the bounded semantic
classification; the Flow remained responsible for order, tools, recovery and
evidence. No manual Flow edit or provider retry was used between generation and
replay.

For this type of deterministic procedure, the result is meaningfully more than
a reusable prompt: it is an applied operating model. It can replace a manually
maintained procedural Skill while remaining easier to create from a successful
conversation.

This does **not** mean every Skill should become a Flow. Knowledge Skills,
tool-specific expertise and methods that belong entirely inside one bounded
Agent task remain good Skills. Flow becomes the better abstraction when the
procedure itself must be operated repeatedly.

## What “more stable” and “less expensive” mean here

The evaluation does not claim that an external Agent provider can never fail.
The stability gain comes from reducing what must be improvised and from making
failure behaviour explicit:

- known steps and effects are versioned in the Flow;
- a bounded failure can resume at its owning step;
- duplicate critical effects are rejected;
- accepted Context and Artifacts survive the Agent conversation;
- each Run can be inspected and compared with earlier Runs.

Likewise, the cost result is operational rather than financial. Median Agent
operational calls fell from 24 to 2 and median elapsed time fell by 83.9% on the
fixed procedure. Task-scoped token telemetry was unavailable, so this report
does not estimate token, credit or currency savings.

## The practical adoption rule

Use the simplest operating model that fits the work:

| Work | Recommended model |
| --- | --- |
| New, exploratory or disposable | Use the Agent directly |
| One bounded task needs reusable expertise | Use a Skill |
| A known procedure repeats across inputs, failures or handoffs | Use a Flow with bounded Agent Nodes |
| A successful Agent task is becoming recurring work | Generate a FlowDraft, review it and Apply |

Symphlo is not a more general Agent and does not need to enter the Agent's
private reasoning loop. It is a lightweight operational layer for the part of
work that has already become known.

## Evidence boundary

All evaluation inputs were synthetic and all business effects were sandboxed.
The public summary contains aggregate results only; it intentionally excludes
provider task identifiers, transcripts, private adapters, traces and fixtures.

The evidence supports:

- case-bounded non-degradation on ordinary office tasks;
- descriptive speed and Agent-work reduction on one fixed long-chain
  procedure;
- one end-to-end conversation-to-reusable-Flow result;
- replacement of a hand-authored procedural Skill for that evaluated task.

It does not support:

- population-level statistical non-inferiority;
- superiority on open-ended exploration;
- provider-wide reliability;
- measured token or currency savings;
- universal replacement of knowledge or tool Skills.

The conclusion is intentionally narrow and useful: for deterministic repeated
office work, a generated and reviewed Flow can preserve Agent capability while
making execution faster, more explicit, recoverable and reusable.

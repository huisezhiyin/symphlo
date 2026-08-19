# Multi-Agent Writing Room Demo

The canonical Local Alpha proof turns a writing Agent loop into an inspectable
outer task without exposing any Agent's inner reasoning.

## Run

```bash
make help
make doctor
make app
```

`make app` installs the locked Web dependencies, builds the React product and
opens Home / Flow / Runs at `http://127.0.0.1:8765`. Create or select a durable
task on Home, inspect its semantic Agent boundaries on the Flow Canvas, choose
the deterministic, Codex or OpenCode executor, and run it. Runs exposes the
persisted Node results, Context, ordered events and `article.md` Artifact.

The default App workspace is stable and user-local, outside the checkout. Use
`STATE_ROOT=/path` when you want an isolated App workspace.

### Zero-credential Golden Flow

An untouched fresh workspace opens one technical proof rather than a business
template:

```text
Plan
  -> Draft in worker_loop
  -> Review
  -> Revise in the same worker_loop conversation
  -> article.md
```

Plan and Review are deterministic control boundaries. Draft and Revise invoke
the bundled fictional session protocol fixture as two separate tasks. In Runs,
select those two Nodes and verify:

- the same `conversation_ref`;
- two distinct `turn_ref` values;
- Draft reports first bind and Revise reports reuse;
- Review remains accepted Context between the two turns;
- `article.md` is persisted independently of the conversation.

This is a real stdio/process and `symphlo.agent-session.v1` proof labelled
`E2_REAL_EXECUTOR`. The fixture is deterministic; it is not an AI model,
provider simulation or model-quality claim.

For a terminal-only or static-file proof:

```bash
make demo
```

`make doctor` reports whether the offline path is ready and discovers optional
Codex/OpenCode executables. It does not inspect credentials or promise provider
authentication. Missing optional Agents do not block `make demo`.

Optional inputs:

```bash
make demo \
  GRANULARITY=fine \
  TOPIC="Why repeated Agent work needs explicit handoffs" \
  STATE_DIR=/tmp/symphlo-writing
```

`GRANULARITY` accepts `compact`, `balanced` or `fine`. `STATE_DIR` must be absent
or empty. Without it, the demo uses a temporary directory outside the source
tree.

## What happens

The default `balanced` Flow runs these semantic boundaries:

```text
Flow input
  -> Planner Agent Node
  -> Writer Agent Node
  -> Editor Agent Node
  -> article.md Artifact
```

The Runtime executes the same immutable Flow twice. `comparison.json` verifies
that each Run used the same executor identity and accepted the same output at
every Node.

The shortest first-user inspection path is:

1. read the printed `article=file://...` deliverable;
2. open the printed `report=file://...` read-only App;
3. press **Replay** to watch ordered persisted events change Node state;
4. select a Node and inspect its input, effects, executor, result and events;
5. switch between Run 1 and Run 2 to compare the same immutable Flow.

## Compare granularity profiles

| Profile | Agent-role Nodes | Total Nodes including publication |
| --- | ---: | ---: |
| `compact` | 1 | 2 |
| `balanced` | 3 | 4 |
| `fine` | 5 | 6 |

All profiles use the same persisted Flow, Run, Node, Context, Event and Artifact
contracts. Selecting a profile does not change the Runtime. The profile is
chosen before execution; A1 does not claim automatic graph rewriting.

## Evidence guide

- `flow.json` is the exact selected definition.
- `run-1.json` and `run-2.json` contain Node inputs/results, Context and events.
- `comparison.json` compares accepted outputs and executor identities.
- `index.html` is the standalone evidence report produced by the terminal demo.
- Browser-created tasks and Runs are available through the React product hosted
  by `make app`; the static report remains a read-only execution proof.
- `article.md` is the accepted output Artifact; its SHA-256 is in SQLite and JSON.

The Canvas answers where work is, the Timeline answers when accepted state
changed, and the Evidence Panel answers why a handoff is trusted. Layout,
selection and replay position are UI projections; Flow and Run evidence remain
the source of truth.

Every terminal-demo writing role is visibly labelled `E1_DETERMINISTIC`. The
generated article is useful demo output, but the evidence proves
orchestration—not LLM quality or real multi-provider collaboration. The
Desktop Golden Flow separately proves the session-capable process boundary.

## Optional E2 command profile

### Live Agent presets

```bash
make demo-codex
make demo-opencode
```

Both presets run the balanced Planner → Writer → Editor Flow by default and
have completed it against installed CLIs. They default to one Run; use
`LIVE_RUNS=2` for cross-Run evidence. Codex uses ephemeral/read-only execution.
OpenCode uses pure JSON-event output but may retain its own provider/session
state outside Symphlo.

Codex model compatibility varies by CLI version:

```bash
make demo-codex CODEX_MODEL=your-supported-model
```

### Generic stdio command

Bind any trusted executable that reads its task prompt from stdin and returns
non-empty text on stdout:

```bash
make demo AGENT_COMMAND='your-agent-command --read-prompt-from-stdin'
```

The same command handles each role; the Node-specific prompt and accepted
Context distinguish planning, drafting, review and revision. A command-backed
Flow includes the command fingerprint in its id, and Agent-role results are
labelled `E2_REAL_EXECUTOR`.

Protocol-only validation is available without an Agent installation:

```bash
make demo AGENT_COMMAND="$(uv python find 3.12) examples/agents/stdio_fixture_agent.py"
```

The fixture proves a real subprocess boundary but is not represented as a real
AI model. External commands inherit the environment, run in the workspace and
are not sandboxed. Bind only trusted executables.

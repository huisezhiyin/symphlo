# A018: OfficeBench-Derived QwenWork Value Evaluation

## 0. Status

- Status: `E2 four-domain smoke complete; E3 intervention design checkpoint`
- Evaluation target: `QwenWork native vs reusable procedure vs Symphlo`
- Source pool: `40 publicly visible OfficeBench ob-agent samples`
- Data location: private Local workspace only
- Result claim: `OfficeBench-derived private evaluation`, never an official
  OfficeBench score

## 1. Goal

Produce a boss-readable, evidence-backed answer to one bounded question:

> For fixed, repeatable and strongly orchestrated office tasks executed through
> QwenWork, does a frozen Symphlo Flow improve accepted-result quality,
> stability, operational speed, reproducibility and failure observability over
> QwenWork alone or the same reusable procedure expressed as instructions?

The evaluation is a system comparison, not a claim that Symphlo makes the base
model intrinsically smarter. Symphlo is allowed to externalize deterministic
work and durable handoffs because that is the product intervention being
tested. All arms must nevertheless receive the same business input, available
tool contracts, sandbox state, effect limits and acceptance oracle.

Avoided orchestration exploration is a design conclusion. Provider token or
credit telemetry is retained when available but is not a completion gate and
must not be estimated from prompts, Context bytes or account-level credits.

## 2. Frozen Source Pool And Rights Boundary

The private snapshot is:

- snapshot: `2026-08-19-all-40`;
- track: `ob-agent`;
- cases: 40 public samples;
- domains: 7 planning, 13 tool-use, 10 cross-app and 10 error-handling;
- difficulty: 31 basic and 9 hard;
- private `index.json` SHA-256:
  `177ae6eb7a1e7e99cca78518f23fc92322aa35de81d2418788183de124655fd3`;
- ordered case-ID SHA-256:
  `f797f4ee069a328925d6ba89eaa4488c2af50ad6a680d92c991c898bde82ca90`.

The source site did not expose a reusable dataset licence when the snapshot was
captured. Raw cases, mock state, scoring payloads, provider-specific adapters
and Run evidence remain outside the Git repository. No private sample, model
output, model score or leaderboard payload is part of the snapshot.

## 3. Pre-Registered Case Split

The split is frozen before any three-arm result is observed. A case must never
move from reserve to primary because another primary case produced an
unfavourable result.

### Development set: 8 cases

These cases may be used to build and debug the shared mock tool gateway, the
reusable procedure and the four Symphlo family templates. Their scores are not
included in the headline result.

- cross-app: `os_agent_0001`, `os_agent_0007`;
- error-handling: `os_agent_0011`, `os_agent_0014`, `os_agent_0019`,
  `os_agent_0041`;
- planning: `os_agent_0028`;
- tool-use: `os_agent_0034`.

This set contains four basic and four hard cases.

### Primary holdout set: 24 cases

- planning: `os_agent_0022`, `os_agent_0023`, `os_agent_0029`,
  `os_agent_0030`;
- tool-use: `os_agent_0031`, `os_agent_0032`, `os_agent_0035`,
  `os_agent_0037`, `os_agent_0038`, `os_agent_0040`, `os_agent_0042`,
  `os_agent_0044`;
- cross-app: `os_agent_0002`, `os_agent_0003`, `os_agent_0004`,
  `os_agent_0005`, `os_agent_0008`, `os_agent_0009`;
- error-handling: `os_agent_0012`, `os_agent_0013`, `os_agent_0015`,
  `os_agent_0016`, `os_agent_0018`, `os_agent_0020`.

This set contains nineteen basic and all five hard cases not used in
development. Near-duplicate variants are preferentially held in reserve so the
primary set measures family transfer rather than repeated wording.

### Reserve set: 8 cases

- planning: `os_agent_0026`, `os_agent_0027`;
- tool-use: `os_agent_0033`, `os_agent_0036`, `os_agent_0039`,
  `os_agent_0043`;
- cross-app: `os_agent_0006`, `os_agent_0010`.

Reserve cases are used only for a pre-declared invalid-case replacement or a
later transfer study. A replacement requires a harness or source defect that
affects every arm, a written reason and retention of the invalid evidence.

## 4. Compared Arms

### N: QwenWork native

- one fresh QwenWork task or session per case repetition;
- only the common system boundary, user rounds and available business tools;
- no family procedure, expected call sequence or scoring information.

### P: reusable procedure

- the same QwenWork execution surface as N;
- one frozen family-specific procedure derived only from the development set;
- the procedure may describe planning, verification and recovery practices but
  cannot carry executable state, expected answers, case IDs or scorer details.

The E1 feasibility checkpoint proved that local QwenWork exposes native
`SKILL.md` storage, create/patch/edit/delete management and query/enable/disable
controls. This arm may therefore be labelled `QwenWork + Skill`. The current
task-create surface does not expose per-task Skill binding, so the evaluation
Skill is application-global: it must be enabled only for P attempts, disabled
for N and S attempts, and its exact state must be captured before every task.

### S: QwenWork as a Symphlo Node

- one frozen Flow template per domain family;
- deterministic Nodes may inventory inputs, validate parameters, execute
  mechanical tool operations, enforce effect limits and validate accepted
  state;
- bounded QwenWork Agent Nodes handle only the semantic or ambiguous work
  declared by the template;
- Flow, Capability, procedure, prompt and fixture identities are persisted.

The Flow cannot receive expected answers, objective checks, mock match rules or
reference state through Agent Context. The mock gateway and oracle may use
those fields only as hidden environment and scoring truth.

## 5. Fairness And Harness Conformance

Shared across N, P and S:

- exact QwenWork executable, version, account profile and declared provider
  state;
- exact user rounds, source state, available tool schemas and mock responses;
- exact effect sandbox, timeout, cancellation and maximum provider-turn policy;
- exact objective oracle and critical-failure semantics;
- fresh isolated case state and unique submission/Run identity;
- serial arm execution, because QwenWork Skill configuration is
  application-global rather than task-scoped;
- pre-attempt fingerprints for the model selector, enabled Skills, MCP config,
  plugins and relevant QwenWork settings;
- no real email, IM, approval, sharing, deletion or source-system mutation.

The business tool gateway must expose the same observable operations to every
arm. Symphlo may decide that a deterministic Node, rather than QwenWork, should
invoke an operation; the accepted final state and prohibited effects remain
identical.

Before the first scored Run, the harness must pass:

1. schema validation for all 40 cases;
2. positive and deliberately wrong negative oracle fixtures for every checker
   type used by the primary set;
3. one unscored end-to-end development case in every domain and arm;
4. proof that mock rules and scorer configuration never enter Agent-visible
   Context;
5. provider readiness, version and supported reusable-procedure-surface audit;
6. deterministic capture of tool calls, state transitions, final response,
   elapsed time, intervention and terminal status.

Any harness change after scoring starts creates a new cohort. Old and new
cohorts must not be aggregated silently.

## 6. Run Protocol

After all assets are frozen, execute the 24 primary cases three times in every
arm:

`24 cases × 3 arms × 3 repetitions = 216 scored attempts`.

- use blocked randomization: for each case and repetition, randomize arm order;
- persist the random seed and schedule before execution;
- keep every failure, cancellation, timeout and invalid attempt;
- do not retry a failed scored attempt except as a separately labelled
  recovery experiment;
- stop the cohort if the QwenWork version, account profile, tool gateway, Flow,
  procedure, prompt, oracle or source fixture changes;
- run a small checkpoint batch first, then inspect only harness validity, not
  comparative winners, before releasing the remaining schedule.

The initial checkpoint batch is four primary cases, one from each domain, with
one repetition in every arm. If valid, those twelve attempts remain part of
the final cohort; if invalid, the cohort is discarded and restarted after the
fix.

## 7. Measures

### Headline measures

1. strict objective acceptance rate;
2. critical-check pass rate;
3. stable success: a case passes all three repetitions;
4. first-attempt accepted result without manual intervention;
5. wall-clock time to accepted result, reported as median and p90;
6. tool-call and accepted-state variance across repetitions;
7. exact failure attribution to a visible task boundary and handoff;
8. family-template reuse without asset modification on primary cases.

### Experience and sharing measures

- number of frozen family assets reused unchanged;
- case-onboarding configuration fields and human preparation time;
- number of case-specific code or Flow changes after the development freeze;
- whether another fresh task can reproduce the Run from the same versioned
  assets and fixture identity;
- maintenance delta after one pre-declared input change, without claiming
  native partial resume unless the Runtime actually supports it.

### Diagnostic measures

- QwenWork turns, external tool calls and phase timing;
- Agent-visible input and accepted Context bytes;
- provider-reported task tokens or task-scoped credits when available.

Context bytes, turn count and shared-account credits are diagnostic proxies and
must not be relabelled as measured tokens.

## 8. Analysis And Reporting

The report publishes the full case-by-arm attempt table, not only averages.

- compute paired arm differences at the case level;
- report absolute percentage-point improvement and a case-clustered bootstrap
  95% interval for pass and stable-success differences;
- report median paired time difference only on accepted attempts, alongside
  timeout/failure counts so speed cannot hide quality loss;
- report primary results overall and by domain/difficulty, while marking small
  strata as descriptive;
- retain development and reserve results in separate appendices;
- include representative success and failure traces selected by a
  pre-declared rule, not by narrative convenience.

The conclusion may claim value for this QwenWork, harness version and
OfficeBench-derived fixed-orchestration sample. It must not claim universal
Agent superiority, official OfficeBench ranking or general office-worker
demand validation.

## 9. E1 Feasibility Audit Result

E1 completed as a read-only audit on 2026-08-19. Private structured evidence is
stored under `private-cases/a018-officebench-derived-qwenwork` and is excluded
from the public source projection.

Confirmed execution identity:

- running App: `QwenWorkCN.app` version `0.1.8`, build `26081406`;
- bundled/local `qwenwork` CLI: `0.1.0-2f629b8-client` at commit
  `2f629b8d297c7938f501c169631a048f5ff7ab43`;
- private Symphlo adapter: `1.0.1`;
- live local MCP: protocol `2025-03-26`, server `qw-builtin/1.0.0`;
- opaque active model selector: `mode-d98246c0ef8840b399161f798f5831b1`
  in scene `qwork`.

The standalone `qwenwork` CLI exposes server-managed tools and user/account
commands but no task/session execution command. The valid automation boundary
is the running Desktop App's local MCP task lifecycle. It supports fresh task
creation, detail, continuation and cancellation and has already produced live
A016/A017 accepted Runs.

Session evidence remains adequate for the comparison:

- four retained completed direct records have four distinct Run IDs, QwenWork
  chat IDs and turn references;
- one retained five-turn Flow is still readable as five user plus five
  assistant messages in one QwenWork chat, with ten unique message IDs and
  nineteen tool calls.

QwenWork has a genuine native Skill surface:

- `qwenwork_skill_manage` creates, patches, edits and deletes reusable Skills;
- user Skills live at `~/.qwenworkcn/skills/{name}/SKILL.md`;
- the Connector exposes query, enable, disable and remove actions;
- the current profile has one user Skill and eleven enabled built-in Skills;
- the bundled market snapshot contains 31 entries.

QwenWork also exposes custom MCP registration and lazy tool discovery/call.
The current profile reports one connected custom MCP. E2 deliberately did not
register another application-global MCP: a private per-Run Unix-socket gateway
was invoked through a narrow CLI instead. Task detail retains the CLI's `Bash`
call, while the hidden gateway journal provides the objective business-tool
oracle. This preserves equal observable tool contracts without introducing
another mutable global registration.

Available metrics are wall time, terminal status, message/turn count, tool-call
count/name/input/state and session/turn identity. Task detail still exposes no
provider token fields. `qwenwork.usage` exposes account credits only; snapshots
remain shared-account-window diagnostics rather than task-scoped cost.

E1 was accepted with five E2 gates. The first gate proposed a private mock MCP,
but E2 replaced that transport with a per-Run CLI gateway after review; the
observable contract and hidden oracle requirements are unchanged:

1. live-smoke one private OfficeBench tool through a development case;
2. prove the evaluation Skill is visible when enabled and absent when disabled;
3. capture model-selector, Skill, MCP, plugin and settings fingerprints before
   each attempt;
4. execute arms serially and restore the pre-evaluation global state;
5. retain the existing missing-token boundary unless QwenWork adds explicit
   task-level usage.

No Skill, MCP, settings, task or provider state was mutated during E1.

## 9.1 E2 One-Tool Checkpoint Result

The first E2 checkpoint completed on 2026-08-19 using development case
`os_agent_0019`. It is an unscored harness smoke test, not part of the primary
cohort and not evidence for a comparative winner.

The private harness now has:

- a per-Run Unix-socket gateway with isolated state and a `0600` socket;
- a narrow CLI that invokes only the declared business tool contract;
- an append-only hidden call journal and deterministic timeout-then-success
  fixture;
- an objective scorer plus positive and deliberately wrong negative fixtures;
- an Agent-visible contract that excludes mock rules, expected calls, mock
  results and scorer configuration.

Offline gateway/scorer tests passed. Two fresh live QwenWork tasks then used the
same public user input and tool contract:

- native: completed in 24.68 seconds, with two gateway calls and three
  QwenWork-visible tool calls (`Bash` 2, `Write` 1);
- QwenWork + Skill: completed in 51.63 seconds, with two gateway calls and
  eleven QwenWork-visible tool calls (`Bash` 3, `Skill` 1, `Thinking` 6,
  `Write` 1).

Both attempts correctly produced one retryable timeout, repeated the exact
same arguments once, succeeded on the second call and mentioned the required
business result. The Skill attempt's retained task detail contains an actual
`Skill` call, proving invocation rather than merely enabled configuration.
Skill inventory fingerprints were unchanged within each attempt. The dedicated
evaluation Skill remains installed but was restored to disabled after the
checkpoint. No mock MCP was registered.

Both strict objective scores are nevertheless `false`. The published scorer
requires `limit=200`, while the published user prompt requires only a `SELECT`
query and one retry, and the published tool schema describes `limit` without a
default or required value. Native omitted `limit`; Skill chose `LIMIT 100` in
SQL. Supplying `200` only through hidden harness context would leak scorer truth
and invalidate the comparison, so the failures are retained unchanged.

This checkpoint accepts the execution transport, isolation, journaling,
recovery trace and genuine Skill invocation. It does not yet accept the 40-case
scoring contract. Before expanding E2, every public case must be audited so each
objective requirement is classified as:

1. declared in the public prompt or tool contract;
2. a documented benchmark-wide default supplied identically to every arm; or
3. unavailable from the public sample and therefore excluded, reformulated or
   reported as a source limitation before any primary schedule is frozen.

No further live comparative run should start until that classification and the
common policy are frozen.

## 9.2 E2 Forty-Case Source-Contract Audit

The private, reproducible source-contract audit completed on 2026-08-19. It
compares every canonical objective requirement with the public prompt, tool
schema, prior tool results and deterministic mock effects. Human decisions are
stored as a versioned policy rather than embedded as ad hoc scorer exceptions.

Across all 40 cases, the audit found 573 objective requirements:

- 425 values are literal in the public prompt;
- 36 are deterministic semantic translations of the prompt and public schema;
- 34 are derivable from a prior tool result;
- 14 are deterministic tool effects;
- 64 are not derivable from Agent-visible public input.

Only eight cases are directly source-eligible. Thirty-two cases require a
common normalization before any comparative run. By frozen split, the counts
are two eligible and six normalization-required in development, five and
nineteen in primary, and one and seven in reserve. This is a source-contract
finding, not an Agent failure rate.

The 64 unavailable requirements are fully assigned to six normalization rules:

- 26 exact company-email checks accept the public person name as the same
  sandbox identity;
- 22 unrequested optional/default checks are removed from the derived oracle;
- three defaults are published identically to every arm: end-of-business is
  18:00 Asia/Shanghai and omitted workflow initiator is `current`;
- nine internal template/workflow/category/status wire values are exposed with
  business descriptions in the common public tool schema;
- two approval reasons use a semantic budget-verification check rather than one
  hidden phrase;
- two conditional-edit cases receive the missing latest-progress text as an
  explicit read-only business input Artifact shared by every arm.

Three cases (`os_agent_0034`, `os_agent_0037`, `os_agent_0040`) also omit
`doc_edit` from `required_tools` while including it in `expected_calls`, making
it available, and explicitly requesting the edit in the public prompt. The
derived oracle treats `expected_calls` as canonical and retains the source
warning.

The normalization does not copy raw expected calls, mock matching rules, state
assertions or response keywords into Agent Context. The original public scorer,
the normalized derived oracle and every Agent-visible contract must retain
separate hashes. The same normalized contract is supplied to N, P and S.

Private evidence hashes at this checkpoint:

- audit implementation:
  `63cd6703709313e551caec4848653ff187eb39ca7dab1a2fe769bafe59a0c256`;
- human audit policy:
  `de0c59bd043911006368a34c973cd25a39170a1d287bde4fca80e2b6f456f286`;
- full JSON report:
  `d1a8b28cd0841b25f4bf20c9f400f5156ea93d4befbed4aae3042ea47808e69d`;
- normalization manifest:
  `53fd3b57e6ae87fd9513724c45af914ad7688413798f8694ca5375dce83462fe`.

The source-contract audit gate is accepted. The next E2 gate is implementation:
generate normalized Agent-visible contracts and independent derived oracles,
then prove by tests that all 64 decisions are applied once, equally across arms
and without scorer leakage. No new live comparative task should run before that
proof passes.

## 9.3 E2 Normalized Bundle Result

The private `a018.normalized-bundle.v1` completed on 2026-08-19. It contains 40
Agent-visible contracts, 40 physically separate derived oracles and 40
three-arm input manifests. The generator applied all 64 frozen normalization
decisions exactly once.

The Agent-visible contract contains only:

- original public user rounds;
- public tool definitions plus the approved enum/default/identity/folder-alias
  annotations;
- a common sandbox, clarification and effect-conflict policy;
- the three explicitly promoted business-input Artifacts.

It contains no objective, expected calls, mock rules, state assertions,
response keywords, match modes, critical flags, exact tool-call budget, split,
difficulty or domain metadata. The derived oracle references the Agent contract
by SHA-256 but remains a separate hidden file. N, P and S have the same
contract hash for every case; Skill and Flow are measured interventions outside
the common business input.

Bundle conformance passed for all 40 cases:

- 40/40 Agent contracts passed forbidden-key leakage scanning;
- 40/40 contract-to-oracle hash chains matched;
- 40/40 N/P/S input manifests had one identical contract hash;
- 40/40 synthesized positive fixtures were accepted;
- 40/40 deliberately wrong negative fixtures were rejected;
- all 67 normalization decisions were covered exactly once;
- the three source `required_tools` warnings were retained while `doc_edit` was
  restored from canonical `expected_calls`.

Specific regression proof confirms that `os_agent_0019` no longer exposes or
scores hidden `limit=200`, while `os_agent_0013` and `os_agent_0018` receive a
complete latest-progress sentence as a shared business Artifact rather than a
truncated scorer fragment. These are harness-conformance checks, not model
quality results.

Private evidence hashes:

- normalized generator:
  `d072629f08534e0d6b0ce9803b23df2af24c462c5984b53f54253de6fbc7e8f8`;
- independent derived scorer:
  `123b91e6615ff20bffba5e6ee697e32a880c5f4e3e9c5936ebdb12d7921b657b`;
- bundle verifier:
  `235d75c6f72818ccd1332c383cf632d95255da7703d05f2ce9d97fe138d05e65`;
- normalization manifest:
  `a3222e2cc60478b0cfbee02ff2225732ba48362452a2f55529784f37a80c11dd`;
- normalized bundle index:
  `cadde92b635adb952919a5c343cd36ceeea2259ab43625fab92980109d44c89d`;
- conformance report:
  `0fb01d6a2092a62a72bb590877052165a078cecf6ad735742763801f5af63309`.

The normalization implementation gate is accepted. The next checkpoint is one
unscored normalized development case per domain and arm. Those twelve smoke
attempts must remain serial, preserve profile fingerprints and restore the
evaluation Skill after every P attempt. They are not part of the primary
cohort.

The four-domain smoke selection is frozen before execution:

- cross-app: `os_agent_0001`, a two-round email-to-sheet-to-document-to-IM
  handoff;
- error-handling: `os_agent_0019`, one retryable timeout followed by one exact
  retry;
- planning: `os_agent_0028`, a two-round onboarding task/calendar/document and
  notification chain;
- tool-use: `os_agent_0034`, a two-round sheet/chart/report/export/email chain.

Each case runs in order N, P, S. P uses one frozen domain-family Skill with no
case ID, fixture value, expected call or scorer detail. S must enter a real
Symphlo Run and persist Node-level accepted inputs, executor identity, events,
results and terminal state; a longer QwenWork prompt is not sufficient proof.
Every attempt is retained whether it passes or fails. A transport or harness
defect may stop the smoke sequence, but an unfavourable model result may not be
deleted or rerun as replacement evidence.

The smoke completed on 2026-08-19. It detected two equal-arm contract defects
before the valid cohort was frozen: exact-only scoring rejected the public
`收件箱` / `inbox` alias, and a planning scorer bound `李明` to the task assignee
role although the source prompt named him only as training mentor. The bundle
now publishes those two common semantics to every arm. Six model attempts made
under the superseded contracts and two pre-model Runtime configuration failures
remain retained and are excluded explicitly, not deleted or counted.

The resulting twelve valid development attempts are:

| Arm | Strict pass | Attempts | Mean elapsed | Median elapsed |
| --- | ---: | ---: | ---: | ---: |
| QwenWork native | 3 | 4 | 99.191 s | 69.598 s |
| QwenWork + Skill | 4 | 4 | 120.709 s | 136.883 s |
| QwenWork as Symphlo Node | 4 | 4 | 114.454 s | 130.394 s |

All four S attempts entered genuine terminal `succeeded` Runs with deterministic
preflight and acceptance-gate Nodes, one or two real QwenWork Agent Nodes,
accepted inputs/results, executor identities and 15 or 20 durable events. The
four S Run IDs are retained in the private aggregate evidence. Every P attempt
restored all four evaluation Skills to disabled. The local QwenWork task detail
surface exposed no token usage, so the aggregate records telemetry as
unavailable and does not estimate it.

This unscored smoke proves harness validity and the real Node evidence path. It
does **not** prove a speed advantage: both intervention arms were slower than
native in aggregate, and P matched S on strict acceptance. The current S
implementation externalizes round boundaries, session identity and the gate but
still delegates each business round to an Agent loop. E3 must therefore build
Flow-owned deterministic business steps and bounded semantic Agent Nodes on
development cases before any formal claim that Symphlo reduces exploration or
outperforms QwenWork Skill.

Private aggregate evidence hashes:

- four-domain aggregate:
  `a3f36959b524906c5d5258e432f23407e96e819d1a73dd91feb47a8a0a58f7fb`;
- deterministic aggregate builder:
  `6715a313b93e4df5490fefcae2549c9fd67d8827fc610cc3cb33e2cf57aebc5d`.

## 10. Execution Phases

1. **E0 — source and split freeze:** completed by this Spec and the private
   40-case snapshot.
2. **E1 — feasibility audit:** completed; native Skill, custom MCP, task/session
   isolation and trace surfaces are feasible with the global-state gates above.
3. **E2 — harness conformance:** one-tool CLI gateway, native/Skill live smoke,
   the 40-case source-contract audit, normalized bundle and four-domain N/P/S
   smoke are complete.
4. **E3 — development freeze:** build N/P/S assets using only the eight
   development cases, then freeze hashes and the randomized schedule.
5. **E4 — 12-attempt validity checkpoint:** run four primary cases once in all
   three arms and inspect only cohort validity.
6. **E5 — formal cohort:** complete all 216 scored attempts without changing
   frozen assets.
7. **E6 — report:** generate raw tables, evidence index, statistical summary,
   limitations and a boss-readable conclusion.

## 11. Done Contract

A018 is complete only when:

1. the 8/24/8 split, fixtures, oracle, arm definitions, provider profile and
   run schedule are frozen before primary results;
2. the harness proves equal input/tool/state/oracle boundaries and blocks
   answer leakage;
3. all 216 scheduled attempts have a retained terminal record, including
   failures and invalidations;
4. strict acceptance, stable success, elapsed time, variance, intervention,
   observability and reuse measures are computed from raw evidence;
5. the report distinguishes native Skill support from an injected procedure
   prompt and OfficeBench-derived results from official OfficeBench scores;
6. provider-specific code, source data and evidence remain private;
7. findings and deviations are reverse-synced into this Spec before any public
   product conclusion changes.

## 12. Non-Goals And Risks

- no comparison against free-form or disposable tasks;
- no real company data or external side effects;
- no requirement to prove total provider-token savings;
- no tuning on the 24 primary cases after scoring starts;
- no silent case replacement, retry deletion or invalid-attempt deletion;
- no claim that more Flow Nodes are inherently better;
- no simulated resume, retry or recovery capability;
- no provider-specific adapter, OfficeBench payload or Run evidence in the
  public source projection.

The main risks are unequal tool access between arms, scorer requirements not
derivable from the published prompt/tool contract, answer leakage,
provider-version changes during 216 attempts and a primary sample too small
for strong subgroup claims. E2 must resolve the first three risks before any
scored Run.

## Recap Checkpoint

- Core goal: measure whether frozen executable orchestration adds value to
  QwenWork on fixed office tasks, not whether it wins free-form Agent work.
- Completed: 40 public samples are stored privately and split 8/24/8 before
  comparative results.
- Completed: E1 proved the live Desktop MCP task boundary, native Skill control,
  custom MCP feasibility, session identity and available metric surface.
- Completed: E2 proved a private per-Run CLI gateway, objective journaling,
  timeout/retry behavior and genuine Skill invocation on one development case.
- Completed: all 40 public contracts were audited; 573 objective requirements
  were classified, including 67 unavailable requirements across 32 cases, and
  every gap now has one frozen equal-arm normalization rule.
- Completed: 40 Agent contracts and 40 independent derived oracles were
  generated; 40/40 passed leakage, hash-chain, equal-arm and positive/negative
  conformance checks, with 67/67 normalization coverage.
- Completed: twelve valid four-domain N/P/S development attempts and eight
  explicit exclusions are retained; native passed 3/4, P 4/4 and S 4/4.
- Current boundary: no formal scored Run has started. E2 establishes the harness
  but does not establish a speed or Symphlo-over-Skill advantage.
- Next task: implement Flow-owned deterministic business steps and bounded
  semantic Agent Nodes on development cases, then freeze E3 assets and schedule.
- Stop condition: do not start E4/E5 until the stronger S intervention passes a
  new development-only conformance checkpoint without changing common inputs or
  the derived oracle.

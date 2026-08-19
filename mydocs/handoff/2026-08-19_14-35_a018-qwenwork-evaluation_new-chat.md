# New Chat Handoff: A018 QwenWork Evaluation

- Created: 2026-08-19 14:35 CST
- Workspace: `/Users/wuyue/github_project/symphlo`
- Active Skill / Workflow: `new-chat-ready`; A018 evaluation Spec
- Recovery Sources: current chat
- New Chat Capability Check: direct task created via Codex `create_thread`
- Git Protection: `local snapshot verified`; no remote push authorized
- Snapshot Ref: original unborn `main` -> `codex/new-chat-snapshot-20260819-1435-a018-qwenwork-eval` @ source snapshot `202fce7`
- Remote Protection: `not requested`
- Remaining Dirty State: `.cache/`, all `node_modules/`, generated `dist/` and `artifacts/`, bytecode, historical feature/local docs, `uv.lock` and other unrelated local records intentionally excluded from the reviewed snapshot
- Delivery Mode: direct Codex task `01a018be-43cf-7762-a39d-968399e58b11`; prompt is also portable below
- Current Goal: prove that QwenWork + Symphlo is non-inferior on normal office work and materially better for repeatable, long, complex, checkpointed work at office-worker scale.
- Status: `in-progress; E2 complete, E3 design checkpoint`
- Confidence: `high`; Spec, private evidence and validation are current.

## 1. Sources

| Source | Role | Status |
| --- | --- | --- |
| `AGENTS.md` | repository, public-source and workflow rules | confirmed |
| `PROJECT_SPEC.md` | product boundary: slidable observable outer loop | confirmed |
| `PROJECT_KNOWLEDGE.md` | durable local architecture decisions | confirmed |
| `docs/features/a018-officebench-derived-qwenwork-value-evaluation.md` | active evaluation source of truth | confirmed |
| `~/Library/Application Support/Symphlo/workspace/private-cases/a018-officebench-derived-qwenwork/four-domain-smoke-summary.json` | frozen 12-attempt aggregate and exclusions | confirmed, private |
| `~/Library/Application Support/Symphlo/workspace/private-cases/a018-officebench-derived-qwenwork/four-domain-smoke-report.md` | compact private checkpoint report | confirmed, private |

## 2. Current State

### Confirmed

- E2 produced 12 valid development smoke attempts: native 3/4, Skill 4/4, Symphlo 4/4.
- Mean elapsed time was native 99.191s, Skill 120.709s, Symphlo 114.454s; no speed advantage is proven.
- Four S attempts are real terminal Symphlo Runs with deterministic preflight/gate Nodes, QwenWork Agent Nodes, accepted inputs/results, executor identity and durable events.
- Eight excluded attempts remain retained: six used superseded contracts and two failed before model execution.
- The smoke exposed and fixed two equal-arm contract defects: `收件箱/inbox` alias scoring and the hidden planning task-assignee role binding.
- The normalized bundle now has 40 contracts, 67 normalization decisions and 18 passing private tests.
- QwenWork task detail exposes no provider token usage; evidence records unavailable and does not estimate it.
- All four temporary A018 QwenWork Skills are disabled after evaluation.
- `make check` passed, including public-source boundary and project tests/builds.

### Inferred

- Current S proves observability and non-degradation direction, but it cannot yet prove the core economic advantage because each business round remains a QwenWork Agent loop.
- The strongest product claim should be non-inferiority on ordinary work plus superiority on at least one operational dimension for long, repeatable and checkpointed work.

### Unknown

- Which real office-worker case family will yield the clearest boss-readable advantage over both native and Skill.
- Whether deterministic Flow-owned business steps will improve accepted-result speed/cost without introducing too much boundary overhead.
- Cross-Agent portability and LLM-generated/optimized Flow performance have not yet been measured.

## 3. Decisions And Constraints

- Reposition current OfficeBench-derived cases as parity/non-inferiority and harness conformance, not the main advantage proof.
- Add orchestration cases with 8-30 steps, 3-6 tools, explicit intermediate destinations, repeat runs, injected failures and local recovery.
- Add platform cases for heterogeneous Agents, executor replacement, cross-conversation continuation, and LLM-generated/optimized Flow.
- Quality is a non-inferiority gate; the main differentiators are stable success, reduced exploration/rework, recovery, reproducibility, reuse, observability and population-scale sharing.
- Symphlo is not anti-LLM: models may generate, control and optimize Flow, while Runtime validates contracts, effects, state and accepted results.
- Keep provider-specific harness, source cases, QwenWork adapters, Skills, traces and results private. Do not push or publish without explicit authorization.

## 4. Files And Changes

| Path | State | Notes |
| --- | --- | --- |
| `docs/features/a018-officebench-derived-qwenwork-value-evaluation.md` | changed | E2 results, exclusions, hashes and E3 boundary recorded |
| `mydocs/handoff/2026-08-19_14-35_a018-qwenwork-evaluation_new-chat.md` | new | this continuation pack; local-only |
| `~/Library/Application Support/Symphlo/workspace/private-cases/a018-officebench-derived-qwenwork/` | generated/changed | private gateway, runner, normalized bundle, 20 retained attempts, aggregate |

## 5. Validation

| Command / Evidence | Result | Coverage |
| --- | --- | --- |
| private `python3 -m unittest discover .../tests -v` | pass, 18 tests | audit, normalization, scorer, gateway |
| `make check` | pass | 67-file public boundary, Python/Web/Desktop checks and builds |
| live QwenWork Skill query | pass | all four A018 Skills disabled |
| `four-domain-smoke-summary.json` | pass | exactly 12 current-contract attempts + 8 explicit exclusions |

## 6. Open Risks

- Four cases are too small for a superiority claim.
- Skill matched S at 4/4 in E2; the next S intervention must own deterministic business work, not merely wrap Agent rounds.
- Provider token telemetry is absent; use tool calls, rework, elapsed time and bounded work as operational measures without inventing token counts.
- The local repository began with no commits and many unrelated untracked paths; snapshot scope must remain reviewed and local-only.

## 7. Next Action

1. Update A018 E3 design with three cohorts: parity, orchestration advantage and Agent-agnostic/LLM-generated Flow.
2. Select 3-5 realistic office-worker development cases and define intermediate destinations, failure injection, repeated-run and recovery metrics.
3. Implement one stronger S case where deterministic Nodes own mechanical effects and QwenWork handles only bounded semantic work; checkpoint before expanding.
4. Rerun development-only N/P/S and decide whether evidence supports freezing E4/E5.

## 8. Project MD Sync

| Candidate | Target | Status | Evidence |
| --- | --- | --- | --- |
| E2 result and next evaluation boundary | A018 feature Spec | synced | current chat + private aggregate |
| Slidable Agent/Flow/Skill boundary | `PROJECT_SPEC.md`, `PROJECT_KNOWLEDGE.md` | already present; no duplicate write | existing product thesis and decisions |
| Mass office-worker adoption claim | root project docs | proposed/skipped for now | needs stronger E3 evidence before promotion |

## 9. Paste-Ready New Chat Prompt

默认用中文交流。请接着 A018 继续，不要从零开始。

Workspace: `/Users/wuyue/github_project/symphlo`

Read first:
- `AGENTS.md`
- `PROJECT_SPEC.md`
- `PROJECT_KNOWLEDGE.md`
- `docs/features/a018-officebench-derived-qwenwork-value-evaluation.md`
- `mydocs/handoff/2026-08-19_14-35_a018-qwenwork-evaluation_new-chat.md`

Goal: 证明 QwenWork + Symphlo 对普通办公任务不劣化，并在长、复杂、可重复、有中间终点的任务上体现稳定性、速度/成本、恢复、复现、复用或协作优势，最终适合海量办公室文员使用。

Confirmed state:
- E2 有效结果：native 3/4、Skill 4/4、S 4/4；S 未证明更快，也未胜过 Skill。
- 当前 S 只外部化轮次、会话和 gate，业务步骤仍由 Agent loop 完成。
- 私有完整结果在 `~/Library/Application Support/Symphlo/workspace/private-cases/a018-officebench-derived-qwenwork/`。
- 正式 scored cohort 尚未开始；QwenWork token telemetry 不可用且不得估算。

Constraints:
- 当前 OfficeBench case 定位为 parity/non-inferiority，不是核心优势证明。
- 新 case 要覆盖 8-30 步、3-6 工具、中间终点、重复运行、故障恢复、跨用户复用、多 Agent，以及大模型生成/优化 Flow。
- provider-specific assets 和证据保持私有；不提交私有数据，不推送或发布。

Next:
1. 先把 E3 三类 cohort 与判定指标回写 A018 Spec。
2. 选择 3-5 个真实办公室文员开发 case。
3. 实现一个 Flow-owned deterministic steps + bounded QwenWork Node 的强 S case，并用开发集验证后再申请 E4/E5 checkpoint。

继续使用受保护的本地 snapshot 分支，保留现有改动，不创建或删除 worktree/branch，不从头重做。

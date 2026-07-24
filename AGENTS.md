# AGENTS

默认用中文交流；公共 API、协议字段、代码标识符和对外开发者文档使用英文。

## Read First

进入 workspace 后按顺序阅读：

1. `PROJECT_SPEC.md`
2. `README.md`
3. `PUBLIC_SOURCE_MANIFEST.md`
4. 当前 task 对应的代码和测试

## Owner Model

- 主 Agent 是 owner / decider / implementer / verifier。
- 中等及以上任务先明确 goal、scope、affected contracts、validation、risks 和 non-goals，获得 checkpoint 后再实现。
- 一次只推进一个最小可验收 task；每次收敛都回写受影响的 public contract、tests 和 release evidence。
- 保留用户已有改动；不重置、不清理、不顺手修无关文件。

## Product Boundaries

- Symphlo is a durable task runtime above Agent loops, not a general low-code platform and not an Agent UI shell.
- An Agent is a first-class Node executor. It may keep its internal loop, while Symphlo owns observable inputs, effects, executor identity, events, accepted results, Context and Artifacts.
- Flow controls `what / who / when / handoff`; an Agent controls `how` inside its Node boundary.
- Flow definitions, Run state, Context, Artifacts and history are product truth. Agent sessions and conversations are not.
- The public product must remain agent-agnostic and capability/adapter-driven.
- Canvas is optional infrastructure and must not define product identity or become the source of truth.

## Provenance And Public-Source Rules

- This repository starts from an empty Git history. Source from another workspace requires explicit owner authorization, a reviewed file-level provenance boundary and the public ownership gate; never import its Git history.
- Do not copy source, styles, assets or generated bundles from third-party, restricted or unclear-provenance repositories.
- Product semantics may be reimplemented from approved specifications and public protocols.
- Do not add third-party-derived source/assets/design, internal integrations, Pilot material, company identity, internal endpoints, handoffs, local state, traces, Artifacts or user data.
- Do not add `.env`, credentials, keys, cookies or tokens.
- Do not create or claim a final `LICENSE`, public release or M0 completion until ownership, license, name, notices, destination and publication authority have explicit human sign-off.
- Do not change repository visibility, push, publish packages or create releases without explicit user authorization.

## Architecture Rules

- Stable public contracts precede implementation.
- DSL and public contracts are portable truth; visual editor state is not.
- Runtime owns durable state transitions, retries, timeout, cancellation and audit.
- Adapters return versioned results and events; they never mutate Flow or Run truth directly.
- Local Alpha must not create a Local-only execution shortcut.
- Case-specific semantics belong in Flow, Prompt, Capability, schema and eval, not in Runtime, scheduler, database or product-page forks.

## Validation

- New contracts require fixtures and tests before runtime implementation.
- Every task runs its focused static, unit and contract checks.
- Local-profile changes require a clean-checkout lifecycle test.
- Public-source changes require manifest, provenance, secret, prohibited-source and exported-tree checks.

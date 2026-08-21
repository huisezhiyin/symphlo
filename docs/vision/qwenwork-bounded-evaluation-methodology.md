# QwenWork Bounded Evaluation Methodology

This document explains how to audit, recalculate and independently repeat the
public claims in [When a Flow Is More Useful Than a Skill](qwenwork-bounded-evaluation.md).
It separates three different meanings of reproducibility:

1. **Metric reproducibility** — anyone can recompute the published aggregates
   from the sanitized per-Run rows.
2. **Protocol reproducibility** — another evaluator can apply the same arms,
   schedule, acceptance rules and stop conditions.
3. **Outcome reproducibility** — another live QwenWork environment may repeat
   the protocol, but exact latency and Agent behaviour can change with provider,
   model, client and infrastructure versions.

The public pack fully supports the first level, documents the second, and does
not promise identical third-level outcomes. Because the exact private fixtures,
adapter and raw provider events are not redistributed, the public repository
supports an analogous protocol repetition rather than a byte-for-byte replay
of the original live evaluation.

## Evaluation classification

- Date closed: 2026-08-21.
- Classification: unscored development evidence.
- Inputs: synthetic office-task inputs.
- Effects: sandboxed business gateways only.
- Provider: QwenWork used as the external Agent executor.
- Model control: the same selected model binding was required across compared
  arms and verified before each retained position.
- Formal holdout cohort: not started.
- Task-scoped token telemetry: unavailable and not estimated.

This is not an official OfficeBench score. The ordinary cases were derived into
private normalized contracts and independently scored by case-specific oracles;
the public pack does not redistribute source benchmark material.

## Public and private evidence boundary

The public JSON contains every retained row used for the reported ordinary and
fixed-orchestration aggregates, with scenario labels sanitized. It excludes:

- provider task and conversation identifiers;
- raw transcripts and internal reasoning events;
- private adapters, prompts, fixtures and provider configuration;
- local paths, credentials, traces and business-state files.

The raw terminal records remain private. Therefore a public reader can verify
the arithmetic and protocol, but cannot independently authenticate every
provider event from the public repository alone. No independent external audit
has been performed. This limitation is explicit rather than hidden behind the
word “reproducible.”

## Cohort A: ordinary office tasks

### Purpose

Test whether adding Symphlo causes an obvious quality regression on bounded
ordinary work. This cohort is a parity smoke, not the primary advantage case.

### Arms

- `qwenwork_direct`: QwenWork receives the bounded task without an evaluation
  Skill or Symphlo Flow.
- `qwenwork_skill_available`: exactly one task-specific procedure Skill is
  available. This is an intent-to-treat arm; availability does not imply that
  the Agent invoked the Skill.
- `qwenwork_symphlo`: QwenWork runs inside the case's observable outer Flow.

### Retained sample

Four scenarios × three arms = 12 current-contract terminal positions. The
public JSON includes accepted status and elapsed seconds for all 12.

Eight earlier development attempts are excluded from the current cohort: six
used superseded contracts with known conformance defects, and two stopped in
harness startup before model execution. They remain retained privately. This
is why the cohort is labelled development evidence rather than a preregistered
benchmark.

### Acceptance

A position passes only when the current normalized input contract, arm binding,
provider result and case oracle agree. Harness startup or superseded-contract
attempts cannot be relabelled as current-contract model outcomes.

### Supported conclusion

Direct accepted 3/4, Skill-available accepted 4/4 and Symphlo accepted 4/4. The
sample supports “no observed degradation.” It does not support a speed or
quality superiority claim over Skill.

## Cohort B: fixed expense orchestration

### Purpose

Test the intended advantage position: a known, repeated, long-chain procedure
with multiple tools, intermediate endpoints and business effects.

### Common contract

Both arms receive the same synthetic expense input, six business-tool kinds,
semantic oracle and effect budget. A valid result must show:

- correct semantic dispositions and balanced reconciliation;
- successful completion of all six business-tool kinds;
- exactly one approval, submission and notification;
- no duplicate or prohibited critical effect;
- the expected selected-model binding;
- one provider task for the position and zero provider retry.

### Arms

- `qwenwork_direct`: QwenWork owns the complete procedure and may use its normal
  operational tools.
- `qwenwork_symphlo`: an 18-Node Flow owns deterministic reads, validation,
  reconciliation, approval and notification. One bounded Agent Node owns only
  ambiguous-item semantic classification.

### Frozen v3 schedule

| Position | Scenario | Arm |
| ---: | --- | --- |
| 1 | finance | direct |
| 2 | finance | Symphlo |
| 3 | sales | Symphlo |
| 4 | sales | direct |
| 5 | operations | direct |
| 6 | operations | Symphlo |

Each position allowed one provider task, zero retry, five-second observation
polling and stop-on-first-invalid behaviour. The batch required a 600-second
initial provider cooldown and at least 300 seconds between provider tasks.

Two earlier stopped development batches exposed harness and operational-tool
contract defects. Their three invalid positions remain private and were not
reclassified. The six published rows belong to a prospectively frozen corrected
v3 contract; no failed position was replaced within v3. This history materially
limits the result: it is product-development evidence, not an untouched holdout.

### Metrics

- `elapsed_seconds`: wall-clock attempt time recorded by the arm runner,
  excluding inter-position cooldown.
- `Agent operational calls`: retained operational tool events attributed to
  the Agent. Pseudo-events such as internal “Thinking” observations are
  excluded.
- `elapsed reduction`: `(direct - Symphlo) / direct × 100` for each paired
  scenario.

The public test recomputes accepted counts, mean, median, operational-call
median and the paired reduction range from the six per-Run rows.

## Cohort C: conversation to reusable Flow

### Purpose

Test whether the usability story requires a user to hand-author a procedural
Skill or large workflow.

### Protocol

1. One bounded Agent task extracts a macro blueprint from a sanitized successful
   conversation.
2. A second bounded Agent task maps every required portable Capability to a
   semantic instruction and visible source reference.
3. A versioned Flow-owned dependency contract deterministically assembles the
   execution order. The Agent-generated semantic content is preserved by
   Capability id.
4. Portable schema, capability fingerprints, declared effects, provenance and
   the case oracle are reviewed before execution.
5. Exact review hash plus explicit Human Apply is required. Generation cannot
   apply or run the Flow.
6. The unchanged applied Flow is replayed on a changed business input and a
   bounded read-timeout input.

The first one-shot generation attempt and the first staged contract were
invalid and remain retained privately. The accepted staged-v2 artifacts were
new prospectively frozen attempts, not silent retries or repaired outputs.

### Live replay acceptance

Each replay allowed one provider task and zero retry. All 18 applied Nodes,
semantic outputs and effect checks had to pass. The timeout scenario additionally
required the exact read outcome sequence `timeout`, then `success`, with no
duplicate approval, submission or notification.

Both public replay rows passed. This establishes one case-bounded generated
procedural Flow. It is not evidence that every Skill can or should be replaced.

## Recalculate the public metrics

From a clean checkout:

```bash
python3 scripts/recalculate_qwenwork_evaluation.py
```

The script reads
`docs/vision/qwenwork-bounded-evaluation-summary.json` and derives the reported
metrics from the per-Run rows. The public contract test independently checks the
same calculations and the redaction policy:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python3 -m unittest -v tests.test_public_evaluation_summary
```

Validate the complete public source projection:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python3 scripts/check_public_source.py
```

To verify that the evaluation files survive the fail-closed public export, use
an empty destination:

```bash
make public-tree PUBLIC_DIR=/tmp/symphlo-public
```

## Repeat the protocol with another Agent environment

The public repository provides Symphlo's Agent CLI and session protocol, but it
does not publish the private QwenWork adapter or raw evaluation fixtures. An
independent repetition should:

1. implement or select an Agent adapter compatible with the public Agent CLI
   contract;
2. choose synthetic inputs and freeze them before dispatch;
3. bind the same Agent/model configuration to every compared arm;
4. freeze arm prompts, tools, effects, scorer and schedule before results;
5. allow one provider task per position and retain every terminal outcome;
6. report excluded or superseded development attempts separately;
7. publish per-Run sanitized rows so aggregates can be recomputed.

Exact QwenWork outcomes may change over time. A repetition is successful when
it follows the same protocol and reports all outcomes honestly, not when it is
forced to reproduce the same headline numbers.

## Threats to validity

- Four ordinary cases and three paired strong-case inputs are small samples.
- The evidence was produced during harness development, not on a pristine
  preregistered holdout.
- Strong-case performance compares direct and Symphlo, not a matched Skill arm.
- The Skill comparison combines ordinary-task parity with a demonstrated
  generated-Flow replacement path; it is not a Skill latency leaderboard.
- There were no repeated seeds or independent evaluators.
- Raw provider evidence is private and has not received external audit.
- Provider/model/client changes may affect latency and tool behaviour.
- No task-scoped token or currency measurement is available.
- Cross-user import and a second Agent product have not been tested.

These limitations prevent a universal superiority claim. They do not erase the
bounded observation that explicit Flow ownership substantially reduced Agent
work on the evaluated fixed procedure while preserving accepted outcomes.

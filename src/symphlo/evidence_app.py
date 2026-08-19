"""Self-contained clean-room Local App for the Symphlo canonical task."""

from __future__ import annotations

import html
import json
import os
from pathlib import Path
from typing import Any

from .contracts import FlowDefinition, JsonObject


def _safe_json(value: Any) -> str:
    """Serialize a JSON data island without allowing a script close token."""

    return (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )


def _pretty(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


def _artifact_href(
    artifact: JsonObject,
    state_dir: Path,
    report_dir: Path,
) -> str:
    artifact_path = state_dir / artifact["relative_path"]
    return Path(os.path.relpath(artifact_path, report_dir)).as_posix()


def _payload(
    flow: FlowDefinition,
    evidence: tuple[JsonObject, ...],
    comparison: JsonObject,
    state_dir: Path,
    report_dir: Path,
    granularity: str,
    executor_profile: str,
) -> JsonObject:
    runs: list[JsonObject] = []
    for run in evidence:
        runs.append(
            {
                **run,
                "artifacts": [
                    {
                        **artifact,
                        "href": _artifact_href(artifact, state_dir, report_dir),
                    }
                    for artifact in run["artifacts"]
                ],
            }
        )
    return {
        "flow": flow.as_dict(),
        "semantic_hash": flow.semantic_hash,
        "granularity": granularity,
        "executor_profile": executor_profile,
        "runs": runs,
        "comparison": comparison,
    }


def _canvas(flow: FlowDefinition, first_run: JsonObject) -> str:
    evidence_by_id = {node["node_id"]: node for node in first_run["nodes"]}
    parts: list[str] = []
    for index, node in enumerate(flow.nodes):
        if index:
            parts.append(
                '<div class="handoff" aria-hidden="true">'
                '<span>accepted handoff</span><i></i></div>'
            )
        persisted = evidence_by_id[node.node_id]
        role = node.title.split(":", 1)[0]
        parts.append(
            f"""
            <button class="flow-node is-{html.escape(persisted['status'])}"
                    type="button" data-node-id="{html.escape(node.node_id)}"
                    aria-label="Inspect {html.escape(node.title)}">
              <span class="node-index">{index + 1:02d}</span>
              <span class="node-copy">
                <span class="node-role">{html.escape(role)}</span>
                <strong>{html.escape(node.title.split(':', 1)[-1].strip())}</strong>
                <span class="node-executor">{html.escape(node.executor.executor_id)}</span>
              </span>
              <span class="node-state" data-node-state>{html.escape(persisted['status'])}</span>
            </button>
            """
        )
    return "".join(parts)


def _run_buttons(evidence: tuple[JsonObject, ...]) -> str:
    return "".join(
        f'<button type="button" class="run-button{" is-active" if index == 0 else ""}" '
        f'data-run-index="{index}">Run {index + 1}</button>'
        for index, _ in enumerate(evidence)
    )


def _design_canvas(flow: FlowDefinition) -> str:
    parts: list[str] = []
    for index, node in enumerate(flow.nodes):
        if index:
            parts.append('<div class="design-handoff" aria-hidden="true"><i></i></div>')
        role, _, task = node.title.partition(":")
        parts.append(
            f"""
            <article class="design-node">
              <span>{index + 1:02d}</span>
              <div><small>{html.escape(role)}</small><strong>{html.escape(task.strip() or role)}</strong>
              <code>{html.escape(node.executor.executor_id)}</code></div>
            </article>
            """
        )
    return "".join(parts)


def render_evidence_app(
    flow: FlowDefinition,
    evidence: tuple[JsonObject, ...],
    comparison: JsonObject,
    state_dir: Path,
    report_dir: Path,
    granularity: str,
    executor_profile: str,
) -> str:
    """Render one self-contained projection of persisted Flow and Run truth."""

    data = _payload(
        flow,
        evidence,
        comparison,
        state_dir,
        report_dir,
        granularity,
        executor_profile,
    )
    first_run = evidence[0]
    first_node = first_run["nodes"][0]
    first_events = [
        event for event in first_run["events"] if event["node_id"] == first_node["node_id"]
    ]
    duration_ms = max(
        0,
        round(
            (
                _iso_seconds(first_run["run"]["finished_at"])
                - _iso_seconds(first_run["run"]["started_at"])
            )
            * 1000
        ),
    )
    profile_counts = {"compact": 1, "balanced": 3, "fine": 5}
    profiles = "".join(
        f'<span class="profile{" is-active" if name == granularity else ""}">'
        f'{name}<b>{count}</b></span>'
        for name, count in profile_counts.items()
    )
    truth = (
        f"Agent Nodes use {html.escape(executor_profile)} E2 process evidence."
        if executor_profile != "deterministic"
        else "Agent Nodes use deterministic E1 evidence; the UI makes no model-quality claim."
    )
    return _document(
        canvas=_canvas(flow, first_run),
        design_canvas=_design_canvas(flow),
        run_buttons=_run_buttons(evidence),
        profiles=profiles,
        data_json=_safe_json(data),
        flow=flow,
        first_run=first_run,
        first_node=first_node,
        first_events=first_events,
        comparison=comparison,
        duration_ms=duration_ms,
        truth=truth,
    )


def _iso_seconds(value: str) -> float:
    from datetime import datetime

    return datetime.fromisoformat(value).timestamp()


def _document(
    *,
    canvas: str,
    design_canvas: str,
    run_buttons: str,
    profiles: str,
    data_json: str,
    flow: FlowDefinition,
    first_run: JsonObject,
    first_node: JsonObject,
    first_events: list[JsonObject],
    comparison: JsonObject,
    duration_ms: int,
    truth: str,
) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light dark">
  <title>Symphlo · Local Agent Workbench</title>
  <style>{_STYLES}</style>
</head>
<body>
  <div class="product-shell">
    <aside class="rail" aria-label="Product navigation">
      <button class="rail-brand" type="button" data-nav="home" aria-label="Symphlo Home"><span>S</span><strong>Symphlo</strong></button>
      <nav>
        <button type="button" class="nav-item is-active" data-nav="home"><span aria-hidden="true">⌂</span><strong>Home</strong></button>
        <button type="button" class="nav-item" data-nav="flows"><span aria-hidden="true">◇</span><strong>Flows</strong></button>
        <button type="button" class="nav-item" data-nav="runs"><span aria-hidden="true">▷</span><strong>Runs</strong></button>
      </nav>
      <div class="rail-status"><i></i><span>Local Alpha</span></div>
    </aside>

    <main class="workspace" id="top">
      <header class="workspace-bar">
        <div><span class="crumb">Workspace</span><strong>Agent writing lab</strong></div>
        <div class="runtime-status"><span class="live-dot"></span>Runtime ready · evidence persisted</div>
      </header>

      <section class="screen screen-home is-active" data-screen-panel="home">
        <div class="page-heading home-heading">
          <div><p class="eyebrow">Durable work above Agent loops</p><h1>What should your Agents<br>finish <em>reliably?</em></h1>
          <p>Start with the task. Symphlo turns its valuable handoffs into an observable outer loop while every Agent keeps its own inner loop.</p></div>
          <div class="hero-orbit" aria-hidden="true"><span>PLAN</span><i></i><span>WRITE</span><i></i><span>EDIT</span></div>
        </div>

        <div class="home-grid">
          <section class="task-card primary-card">
            <div class="card-label"><span>Canonical task</span><b>READY</b></div>
            <h2>Multi-Agent Writing Room</h2>
            <p>Turn one topic into an accepted article through durable Agent-role handoffs.</p>
            <form action="/api/run" method="post" class="run-form" data-run-form>
              <label>What should the Agents write?<input name="topic" maxlength="280" value="{html.escape(first_node['input_json'].get('topic', ''))}" required></label>
              <label>Observable task granularity
                <select name="granularity">
                  <option value="compact"{' selected' if len(flow.nodes) == 2 else ''}>Compact · one broad Agent role</option>
                  <option value="balanced"{' selected' if len(flow.nodes) == 4 else ''}>Balanced · plan, write, edit</option>
                  <option value="fine"{' selected' if len(flow.nodes) == 6 else ''}>Fine · five observable Agent roles</option>
                </select>
              </label>
              <button class="primary-action" type="submit"><span>Run this task</span><b>→</b></button>
              <small class="form-note">Runs locally with deterministic evidence. Bind Codex/OpenCode from the CLI when you want a real Agent executor.</small>
            </form>
          </section>

          <section class="idea-card">
            <p class="eyebrow">The two-loop model</p>
            <h2>Observe the outer loop.<br>Preserve the inner loop.</h2>
            <div class="loop-diagram"><span>Flow</span><div><b>Agent Node</b><small>private inspect → reason → act → revise</small></div><span>Artifact</span></div>
            <p class="idea-copy">Flow controls <strong>what / who / when / handoff</strong>. The Agent controls <strong>how</strong>.</p>
          </section>

          <section class="summary-card saved-card">
            <div class="card-label"><span>Saved Flow</span><b>1 FLOW</b></div>
            <h3>{html.escape(flow.title)}</h3>
            <div class="summary-stats"><div><strong>{len(flow.nodes)}</strong><span>semantic Nodes</span></div><div><strong>{len(first_run['events'])}</strong><span>accepted events</span></div><div><strong>{len(first_run['artifacts'])}</strong><span>Artifact</span></div></div>
            <button type="button" class="text-action" data-nav="flows">Open Flow design <span>→</span></button>
          </section>

          <section class="summary-card recent-card">
            <div class="card-label"><span>Recent Run</span><b class="success-pill">SUCCEEDED</b></div>
            <h3>Article accepted and persisted</h3>
            <p><code>{html.escape(first_run['run']['run_id'])}</code></p>
            <button type="button" class="text-action" data-nav="runs">Inspect Run evidence <span>→</span></button>
          </section>
        </div>
      </section>

      <section class="screen screen-flows" data-screen-panel="flows" hidden>
        <div class="page-heading compact-heading"><div><p class="eyebrow">Flow design</p><h1>Slide the task granularity.</h1><p>Externalize a phase only when observation, recovery, replacement or maintenance value earns the handoff cost.</p></div>
          <button type="button" class="secondary-action" data-nav="runs">Inspect latest Run →</button></div>
        <div class="flow-layout">
          <section class="flow-board">
            <div class="flow-board-head"><div><span>ACTIVE FLOW</span><h2>{html.escape(flow.title)}</h2></div><div class="profiles" aria-label="Task granularity">{profiles}</div></div>
            <div class="design-canvas"><div class="canvas-grid"></div><div class="design-track">{design_canvas}</div></div>
            <div class="flow-footer"><span><i></i> immutable FlowDefinition</span><code>{html.escape(flow.semantic_hash[:18])}…</code></div>
          </section>
          <aside class="boundary-panel">
            <p class="eyebrow">Boundary economics</p><h2>More Nodes are not inherently better.</h2>
            <div class="granularity-list"><article{' class="is-current"' if len(flow.nodes) == 2 else ''}><b>Compact</b><span>Keep the complete loop inside one capable Agent.</span></article><article{' class="is-current"' if len(flow.nodes) == 4 else ''}><b>Balanced</b><span>Persist the plan and draft where handoffs matter.</span></article><article{' class="is-current"' if len(flow.nodes) == 6 else ''}><b>Fine</b><span>Add recovery and replacement points for long chains.</span></article></div>
            <p class="boundary-note">Node inputs, effects, executor, events, result and Artifacts are observable. Chain-of-thought is not.</p>
          </aside>
        </div>
      </section>

      <section class="screen screen-runs" data-screen-panel="runs" hidden>
        <div class="page-heading compact-heading run-heading"><div><p class="eyebrow">Run operations</p><h1>See the work. Trust the handoff.</h1><p>Replay accepted state changes and inspect durable evidence—not private Agent reasoning.</p></div><button type="button" class="secondary-action" data-nav="home">Run another task →</button></div>
        <section class="metric-row" aria-label="Run summary">
          <div><span>Flow</span><strong>{html.escape(flow.flow_id)}</strong></div>
          <div><span>Semantic Nodes</span><strong>{len(flow.nodes)}</strong></div>
          <div><span>Ordered events</span><strong id="metric-events">{len(first_run['events'])}</strong></div>
          <div><span>Duration</span><strong id="metric-duration">{duration_ms} ms</strong></div>
          <div><span>Comparison</span><strong class="success">{html.escape(comparison['overall'])}</strong></div>
        </section>

        <section class="app-shell">
      <div class="app-toolbar">
        <div>
          <p class="toolbar-label">Run canvas</p>
          <h2>{html.escape(flow.title)}</h2>
        </div>
        <div class="toolbar-actions">
          <div class="profiles" aria-label="Task granularity">{profiles}</div>
          <div class="run-switcher" aria-label="Select persisted Run">{run_buttons}</div>
        </div>
      </div>

      <div class="control-room">
        <div class="stage-column">
          <section class="canvas" aria-label="Observable Flow Canvas">
            <div class="canvas-grid"></div>
            <div class="canvas-scroll"><div class="flow-track">{canvas}</div></div>
            <div class="canvas-legend">
              <span><i class="legend-dot succeeded"></i>succeeded</span>
              <span><i class="legend-dot running"></i>running</span>
              <span><i class="legend-dot pending"></i>pending</span>
              <span class="canvas-hint">Select a Node to inspect accepted evidence</span>
            </div>
          </section>

          <section class="timeline" aria-label="Run event replay">
            <div class="timeline-head">
              <div><p class="toolbar-label">Event replay</p><h3 id="event-title">Run completed</h3></div>
              <div class="replay-buttons">
                <button type="button" id="replay-prev" aria-label="Previous event">←</button>
                <button type="button" id="replay-play">Replay</button>
                <button type="button" id="replay-next" aria-label="Next event">→</button>
              </div>
            </div>
            <input id="replay-range" type="range" min="0" max="{len(first_run['events']) - 1}" value="{len(first_run['events']) - 1}" aria-label="Replay event cursor">
            <div class="timeline-meta"><span id="event-sequence">{len(first_run['events'])} / {len(first_run['events'])}</span><span id="event-node">run</span><time id="event-time">{html.escape(first_run['events'][-1]['recorded_at'])}</time></div>
            <div id="event-strip" class="event-strip" aria-label="Event steps"></div>
          </section>
        </div>

        <aside class="inspector" aria-label="Node Evidence Panel">
          <div class="inspector-head">
            <span class="node-kicker" id="inspector-kicker">Node 01 · {html.escape(first_node['status'])}</span>
            <h2 id="inspector-title">{html.escape(flow.nodes[0].title)}</h2>
            <span class="evidence-badge" id="inspector-evidence">{html.escape(first_node['evidence_level'])}</span>
          </div>
          <div class="tabs" role="tablist">
            <button type="button" class="tab is-active" data-tab="overview">Overview</button>
            <button type="button" class="tab" data-tab="input">Input</button>
            <button type="button" class="tab" data-tab="result">Result</button>
            <button type="button" class="tab" data-tab="events">Events</button>
          </div>
          <div class="panel-view" data-panel="overview">
            <dl class="facts">
              <div><dt>Executor</dt><dd id="inspector-executor">{html.escape(first_node['executor_id'])}@{html.escape(first_node['executor_version'])}</dd></div>
              <div><dt>Effects</dt><dd id="inspector-effects">{html.escape(' · '.join(first_node['effects_json']))}</dd></div>
              <div><dt>Accepted handoff</dt><dd id="inspector-handoff">Flow input</dd></div>
              <div><dt>Replay state</dt><dd id="inspector-status">{html.escape(first_node['status'])}</dd></div>
            </dl>
            <div id="artifact-block" class="artifact-block" hidden><span>Artifact</span><a id="artifact-link" href="#"></a><code id="artifact-hash"></code></div>
          </div>
          <div class="panel-view" data-panel="input" hidden><p class="payload-label">Accepted input</p><pre id="panel-input">{html.escape(_pretty(first_node['input_json']))}</pre></div>
          <div class="panel-view" data-panel="result" hidden><p class="payload-label">Accepted result</p><pre id="panel-result">{html.escape(_pretty(first_node['output_json']))}</pre></div>
          <div class="panel-view" data-panel="events" hidden><p class="payload-label">Node events</p><pre id="panel-events">{html.escape(_pretty(first_events))}</pre></div>
        </aside>
      </div>
        </section>
        <section class="principle-row">
          <div><span>Canvas</span><strong>where the work is</strong></div><div><span>Timeline</span><strong>when accepted state changed</strong></div><div><span>Evidence</span><strong>why the handoff is trusted</strong></div>
        </section>
      </section>
    </main>
  </div>
  <script id="app-data" type="application/json">{data_json}</script>
  <script>{_SCRIPT}</script>
</body>
</html>
"""


_STYLES = r"""
:root {
  color-scheme: dark;
  --ink: #f3f0e8;
  --muted: #98a39c;
  --panel: #121916;
  --panel-2: #17201c;
  --line: #2a3731;
  --green: #79f2b0;
  --green-deep: #153f2c;
  --amber: #ffc875;
  --blue: #91b7ff;
  --red: #ff8c84;
  --radius: 22px;
  font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: #090d0b;
  color: var(--ink);
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body { margin: 0; min-width: 320px; background: radial-gradient(circle at 75% -10%, #1d4933 0, transparent 32rem), #090d0b; }
button, input { font: inherit; }
button { color: inherit; }
.topbar { height: 68px; padding: 0 clamp(20px, 4vw, 60px); display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #1d2924; background: rgb(9 13 11 / 78%); backdrop-filter: blur(20px); position: sticky; top: 0; z-index: 30; }
.brand { display: inline-flex; gap: 10px; align-items: center; color: var(--ink); text-decoration: none; font-weight: 760; letter-spacing: -.02em; }
.brand-mark { width: 30px; height: 30px; display: grid; place-items: center; border-radius: 9px; color: #07120c; background: var(--green); box-shadow: 0 0 28px rgb(121 242 176 / 25%); }
.topbar-note { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .12em; }
.live-dot { width: 7px; height: 7px; display: inline-block; margin-right: 8px; border-radius: 50%; background: var(--green); box-shadow: 0 0 14px var(--green); }
main { max-width: 1500px; margin: 0 auto; padding: 0 clamp(20px, 4vw, 60px) 64px; }
.hero { min-height: 440px; padding: 76px 0 54px; display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(280px, .6fr); gap: 52px; align-items: end; }
.eyebrow, .toolbar-label, .payload-label { margin: 0 0 12px; color: var(--green); font-size: 11px; font-weight: 800; letter-spacing: .17em; text-transform: uppercase; }
h1 { max-width: 920px; margin: 0; font-size: clamp(3.6rem, 8vw, 8.4rem); line-height: .82; letter-spacing: -.075em; font-weight: 630; }
h1 em { color: var(--green); font-family: Georgia, serif; font-weight: 400; }
.lede { max-width: 720px; margin: 34px 0 0; color: #c5cec9; font-size: clamp(1.05rem, 1.7vw, 1.35rem); line-height: 1.65; }
.truth-card { padding: 24px; border: 1px solid #385143; border-radius: var(--radius); background: linear-gradient(145deg, rgb(27 57 42 / 75%), rgb(15 23 19 / 92%)); box-shadow: 0 28px 80px rgb(0 0 0 / 28%); }
.truth-card span { color: var(--green); font: 800 10px/1 sans-serif; text-transform: uppercase; letter-spacing: .16em; }
.truth-card strong { display: block; margin-top: 18px; font-size: 1.25rem; line-height: 1.4; }
.truth-card p { color: var(--muted); margin: 16px 0 0; line-height: 1.55; font-size: .9rem; }
.metric-row { margin-bottom: 18px; display: grid; grid-template-columns: 1.5fr repeat(4, 1fr); border: 1px solid var(--line); border-radius: 18px; background: #0e1411; overflow: hidden; }
.metric-row div { min-width: 0; padding: 17px 20px; border-right: 1px solid var(--line); }
.metric-row div:last-child { border: 0; }
.metric-row span { display: block; color: var(--muted); font-size: 10px; text-transform: uppercase; letter-spacing: .13em; }
.metric-row strong { display: block; margin-top: 7px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: .86rem; }
.metric-row .success { color: var(--green); }
.app-shell { border: 1px solid #33443c; border-radius: 28px; background: rgb(14 20 17 / 94%); box-shadow: 0 40px 110px rgb(0 0 0 / 35%); overflow: hidden; }
.app-toolbar { min-height: 92px; padding: 22px 24px; display: flex; align-items: center; justify-content: space-between; gap: 22px; border-bottom: 1px solid var(--line); }
.app-toolbar h2 { margin: 0; font-size: 1.15rem; letter-spacing: -.02em; }
.toolbar-actions, .profiles, .run-switcher { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.profiles { padding-right: 12px; border-right: 1px solid var(--line); }
.profile { display: inline-flex; align-items: center; gap: 7px; padding: 7px 10px; color: #87938c; border: 1px solid transparent; border-radius: 999px; font-size: 11px; text-transform: capitalize; }
.profile b { width: 18px; height: 18px; display: grid; place-items: center; border-radius: 50%; background: #222c27; font-size: 9px; }
.profile.is-active { color: var(--ink); border-color: #416252; background: #19261f; }
.profile.is-active b { color: #06120b; background: var(--green); }
.run-button, .replay-buttons button, .tab { border: 1px solid var(--line); background: #101713; border-radius: 10px; cursor: pointer; }
.run-button { padding: 9px 12px; color: var(--muted); font-size: 11px; }
.run-button:hover, .run-button.is-active { color: #07120c; border-color: var(--green); background: var(--green); }
.control-room { display: grid; grid-template-columns: minmax(0, 1fr) 380px; grid-template-areas: "canvas canvas" "timeline inspector"; }
.stage-column { display: contents; }
.canvas { grid-area: canvas; min-height: 430px; position: relative; overflow: hidden; border-bottom: 1px solid var(--line); background: #0b110e; }
.canvas-grid { position: absolute; inset: 0; opacity: .28; background-image: radial-gradient(#496055 1px, transparent 1px); background-size: 24px 24px; mask-image: linear-gradient(to bottom, black 50%, transparent 100%); }
.canvas-scroll { position: relative; z-index: 1; height: 370px; overflow-x: auto; overflow-y: hidden; display: flex; align-items: center; padding: 40px 34px; scrollbar-color: #314139 transparent; }
.flow-track { min-width: max-content; display: flex; align-items: center; }
.flow-node { width: 205px; min-height: 148px; padding: 18px; display: grid; grid-template-columns: 32px 1fr; gap: 12px; position: relative; text-align: left; border: 1px solid #33433b; border-radius: 18px; background: linear-gradient(150deg, #17201c, #101612); box-shadow: 0 18px 45px rgb(0 0 0 / 28%); cursor: pointer; transition: border-color .2s, transform .2s, opacity .2s, box-shadow .2s; }
.flow-node:hover { transform: translateY(-4px); border-color: #668174; }
.flow-node[aria-selected="true"] { border-color: var(--green); box-shadow: 0 0 0 1px var(--green), 0 20px 55px rgb(69 229 145 / 13%); }
.node-index { width: 30px; height: 30px; display: grid; place-items: center; color: #849189; border: 1px solid #39473f; border-radius: 9px; font: 700 10px/1 monospace; }
.node-copy { min-width: 0; display: flex; flex-direction: column; }
.node-role { color: var(--green); font-size: 10px; text-transform: uppercase; letter-spacing: .13em; }
.node-copy strong { margin-top: 8px; min-height: 42px; font-size: .98rem; line-height: 1.28; }
.node-executor { margin-top: 9px; overflow: hidden; color: var(--muted); font: 10px/1.4 ui-monospace, monospace; text-overflow: ellipsis; white-space: nowrap; }
.node-state { grid-column: 1 / -1; width: fit-content; padding: 5px 8px; color: var(--muted); border-radius: 999px; background: #202b25; font-size: 9px; font-weight: 800; text-transform: uppercase; letter-spacing: .09em; }
.flow-node.is-succeeded .node-state { color: #07150c; background: var(--green); }
.flow-node.is-running .node-state, .flow-node.is-accepted .node-state { color: #1c1303; background: var(--amber); }
.flow-node.is-ready .node-state { color: #07142b; background: var(--blue); }
.flow-node.is-failed .node-state { color: #250502; background: var(--red); }
.flow-node.is-pending { opacity: .52; }
.handoff { width: 64px; height: 42px; position: relative; display: grid; place-items: center; color: #75837b; font-size: 8px; text-transform: uppercase; letter-spacing: .08em; }
.handoff i { width: 100%; height: 1px; position: absolute; top: 23px; background: linear-gradient(90deg, #385247, var(--green)); }
.handoff i::after { content: ""; width: 7px; height: 7px; position: absolute; right: -1px; top: -3px; border-top: 1px solid var(--green); border-right: 1px solid var(--green); transform: rotate(45deg); }
.handoff span { transform: translateY(-10px); }
.canvas-legend { position: absolute; z-index: 2; left: 24px; right: 24px; bottom: 20px; display: flex; gap: 18px; align-items: center; color: var(--muted); font-size: 10px; }
.canvas-legend > span { display: flex; gap: 6px; align-items: center; }
.legend-dot { width: 7px; height: 7px; border-radius: 50%; background: #415048; }
.legend-dot.succeeded { background: var(--green); }.legend-dot.running { background: var(--amber); }.legend-dot.pending { background: #56635c; }
.canvas-hint { margin-left: auto; }
.timeline { grid-area: timeline; padding: 22px 24px 26px; border-right: 1px solid var(--line); background: #101713; }
.timeline-head { display: flex; justify-content: space-between; gap: 20px; align-items: center; }
.timeline h3 { margin: 0; font-size: .95rem; }
.replay-buttons { display: flex; gap: 6px; }
.replay-buttons button { min-width: 34px; padding: 7px 10px; color: #c6cfc9; font-size: 11px; }
.replay-buttons button:hover { border-color: var(--green); color: var(--green); }
#replay-range { width: 100%; margin: 24px 0 12px; accent-color: var(--green); }
.timeline-meta { display: grid; grid-template-columns: 80px 1fr auto; gap: 12px; color: var(--muted); font: 10px/1.4 ui-monospace, monospace; }
.event-strip { height: 24px; margin-top: 14px; display: flex; gap: 3px; align-items: center; overflow: hidden; }
.event-step { min-width: 5px; height: 5px; padding: 0; border: 0; border-radius: 999px; background: #344039; cursor: pointer; flex: 1; }
.event-step.is-past { background: #5b8d73; }.event-step.is-current { height: 11px; background: var(--green); box-shadow: 0 0 12px rgb(121 242 176 / 50%); }
.inspector { grid-area: inspector; min-width: 0; padding: 26px; background: #141c18; }
.inspector-head { min-height: 135px; }
.node-kicker { color: var(--green); font: 800 10px/1.2 ui-monospace, monospace; text-transform: uppercase; letter-spacing: .1em; }
.inspector h2 { margin: 13px 0; font-size: 1.45rem; line-height: 1.16; letter-spacing: -.035em; }
.evidence-badge { display: inline-block; padding: 5px 8px; color: #b7c5bd; border: 1px solid #3a4b42; border-radius: 999px; font: 9px/1 ui-monospace, monospace; }
.tabs { margin: 8px 0 22px; display: grid; grid-template-columns: repeat(4, 1fr); gap: 5px; }
.tab { padding: 8px 4px; color: var(--muted); font-size: 10px; }
.tab.is-active { color: #07130c; border-color: var(--green); background: var(--green); }
.facts { margin: 0; }
.facts div { padding: 14px 0; border-bottom: 1px solid #28352f; }
.facts dt { color: var(--muted); font-size: 10px; text-transform: uppercase; letter-spacing: .11em; }
.facts dd { margin: 7px 0 0; overflow-wrap: anywhere; font: 11px/1.55 ui-monospace, monospace; }
.artifact-block { margin-top: 20px; padding: 15px; border: 1px solid #345242; border-radius: 14px; background: var(--green-deep); }
.artifact-block span { display: block; color: #b8d8c7; font-size: 9px; text-transform: uppercase; letter-spacing: .12em; }
.artifact-block a { display: inline-block; margin-top: 8px; color: var(--green); font-weight: 750; }
.artifact-block code { display: block; margin-top: 8px; overflow: hidden; color: #a2b9ad; font-size: 9px; text-overflow: ellipsis; }
.panel-view pre { max-height: 385px; margin: 0; padding: 15px; overflow: auto; color: #c4d0c9; border: 1px solid #293831; border-radius: 14px; background: #0b100e; font: 10px/1.55 ui-monospace, monospace; white-space: pre-wrap; overflow-wrap: anywhere; }
[hidden] { display: none !important; }
.principle-row { margin: 20px 0 0; display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.principle-row div { padding: 20px; border: 1px solid var(--line); border-radius: 16px; background: #0e1411; }
.principle-row span { color: var(--green); font-size: 10px; text-transform: uppercase; letter-spacing: .14em; }
.principle-row strong { display: block; margin-top: 7px; font-size: .92rem; }
footer { padding: 52px 0 0; display: flex; justify-content: space-between; gap: 30px; color: var(--muted); }
footer p { margin: 0; } footer code { max-width: 48%; overflow: hidden; text-overflow: ellipsis; font-size: 9px; }
@media (max-width: 1050px) {
  .hero { grid-template-columns: 1fr; }.truth-card { max-width: 560px; }
  .control-room { grid-template-columns: 1fr; grid-template-areas: "canvas" "timeline" "inspector"; }.timeline { border-right: 0; }.inspector { border-top: 1px solid var(--line); }
  .metric-row { grid-template-columns: repeat(3, 1fr); }.metric-row div:nth-child(3) { border-right: 0; }
}
@media (max-width: 720px) {
  .topbar-note { display: none; }.hero { min-height: 0; padding-top: 58px; } h1 { font-size: clamp(3.25rem, 17vw, 5.5rem); }
  .metric-row { grid-template-columns: 1fr 1fr; }.metric-row div { border-bottom: 1px solid var(--line); }.metric-row div:nth-child(even) { border-right: 0; }
  .app-toolbar { align-items: flex-start; flex-direction: column; }.toolbar-actions { width: 100%; justify-content: space-between; }.profiles { border: 0; }
  .canvas-scroll { height: auto; min-height: 580px; overflow-y: auto; align-items: flex-start; }
  .flow-track { min-width: 100%; flex-direction: column; align-items: stretch; }.flow-node { width: 100%; }.handoff { width: 100%; height: 62px; transform: rotate(90deg); }.handoff span { display: none; }
  .canvas-legend { display: none; }.timeline-meta { grid-template-columns: 60px 1fr; }.timeline-meta time { display: none; }
  .principle-row { grid-template-columns: 1fr; } footer { flex-direction: column; } footer code { max-width: 100%; }
}

/* Clean-room product shell. The dark evidence workspace above is preserved as
   one product surface inside a neutral task-first App. */
html { background: #f3f4f6; }
body { min-height: 100vh; color: #172033; background: #f3f4f6; overflow-x: hidden; }
.product-shell { min-height: 100vh; display: grid; grid-template-columns: 218px minmax(0, 1fr); }
.rail { min-height: 100vh; padding: 22px 14px; display: flex; flex-direction: column; position: sticky; top: 0; z-index: 40; color: #dce2ee; background: linear-gradient(180deg, #162238, #111a2c 72%, #0d1524); box-shadow: 12px 0 40px rgb(17 26 44 / 12%); }
.rail button { border: 0; font: inherit; cursor: pointer; }
.rail-brand { width: 100%; padding: 3px 10px 29px; display: flex; align-items: center; gap: 12px; color: white; background: transparent; text-align: left; }
.rail-brand span { width: 38px; height: 38px; display: grid; place-items: center; flex: 0 0 auto; color: white; border-radius: 12px; background: linear-gradient(145deg, #ff806f, #e95855); box-shadow: 0 9px 25px rgb(230 82 80 / 32%); font-weight: 850; }
.rail-brand strong { font-size: 1.08rem; letter-spacing: -.02em; }
.rail nav { display: grid; gap: 6px; }
.nav-item { width: 100%; padding: 12px 13px; display: flex; align-items: center; gap: 12px; color: #93a0b6; border-radius: 11px; background: transparent; text-align: left; transition: .18s ease; }
.nav-item > span { width: 24px; font-size: 1.25rem; text-align: center; }
.nav-item strong { font-size: .82rem; font-weight: 650; }
.nav-item:hover { color: white; background: rgb(255 255 255 / 7%); }
.nav-item.is-active { color: white; background: rgb(255 255 255 / 11%); box-shadow: inset 3px 0 #ff7466; }
.rail-status { margin-top: auto; padding: 14px 12px 4px; display: flex; align-items: center; gap: 9px; color: #8997ae; font-size: .7rem; text-transform: uppercase; letter-spacing: .1em; }
.rail-status i { width: 7px; height: 7px; border-radius: 50%; background: #5ad29a; box-shadow: 0 0 12px rgb(90 210 154 / 65%); }
.workspace { width: 100%; max-width: none; min-width: 0; margin: 0; padding: 0; color: #172033; background: #f3f4f6; }
.workspace-bar { height: 66px; padding: 0 clamp(22px, 3.8vw, 58px); display: flex; align-items: center; justify-content: space-between; gap: 24px; border-bottom: 1px solid #e0e4ea; background: rgb(255 255 255 / 82%); backdrop-filter: blur(16px); }
.workspace-bar > div:first-child { display: flex; align-items: baseline; gap: 9px; }
.crumb { color: #98a0ad; font-size: .72rem; text-transform: uppercase; letter-spacing: .08em; }
.workspace-bar strong { font-size: .82rem; }
.runtime-status { color: #6e7786; font-size: .72rem; }
.workspace .live-dot { background: #38b985; box-shadow: 0 0 10px rgb(56 185 133 / 45%); }
.screen { max-width: 1460px; margin: 0 auto; padding: 48px clamp(24px, 4vw, 64px) 70px; }
.screen[hidden] { display: none !important; }
.page-heading { display: flex; justify-content: space-between; gap: 40px; }
.home-heading { min-height: 265px; align-items: center; }
.page-heading .eyebrow { color: #e45c57; }
.page-heading h1 { max-width: 980px; margin: 0; color: #172033; font-size: clamp(2.7rem, 5vw, 5.4rem); line-height: .96; letter-spacing: -.06em; font-weight: 690; }
.page-heading h1 em { color: #e65e58; font-family: Georgia, serif; font-weight: 400; }
.page-heading > div > p:last-child { max-width: 720px; margin: 22px 0 0; color: #687282; font-size: 1rem; line-height: 1.65; }
.hero-orbit { min-width: 310px; display: flex; align-items: center; justify-content: center; color: #647087; font: 800 9px/1 ui-monospace, monospace; letter-spacing: .12em; }
.hero-orbit span { width: 82px; height: 82px; display: grid; place-items: center; border: 1px solid #d8dde5; border-radius: 50%; background: white; box-shadow: 0 18px 45px rgb(37 48 69 / 9%); }
.hero-orbit span:nth-of-type(2) { color: white; border-color: #e45c57; background: #e45c57; transform: scale(1.12); }
.hero-orbit i { width: 28px; height: 1px; background: #c8ced8; }
.home-grid { display: grid; grid-template-columns: minmax(0, 1.25fr) minmax(340px, .75fr); gap: 18px; align-items: stretch; }
.task-card, .idea-card, .summary-card { border: 1px solid #e0e4e9; border-radius: 18px; background: white; box-shadow: 0 15px 42px rgb(30 42 64 / 7%); }
.task-card { grid-row: span 2; padding: 30px; }
.card-label { display: flex; align-items: center; justify-content: space-between; color: #9199a7; font-size: .66rem; font-weight: 800; letter-spacing: .11em; text-transform: uppercase; }
.card-label b { padding: 5px 8px; color: #217f5b; border-radius: 999px; background: #e7f8f0; font-size: .58rem; }
.task-card h2 { margin: 23px 0 8px; font-size: 1.8rem; letter-spacing: -.035em; }
.task-card > p { margin: 0; color: #727b8a; line-height: 1.55; }
.run-form { margin-top: 28px; display: grid; gap: 17px; }
.run-form label { display: grid; gap: 8px; color: #485366; font-size: .72rem; font-weight: 750; }
.run-form input, .run-form select { width: 100%; min-width: 0; padding: 13px 14px; color: #202a3b; border: 1px solid #d9dee6; border-radius: 10px; outline: 0; background: #fafbfc; font: inherit; font-size: .82rem; }
.run-form input:focus, .run-form select:focus { border-color: #e45c57; box-shadow: 0 0 0 3px rgb(228 92 87 / 12%); }
.primary-action { min-height: 52px; padding: 0 18px; display: flex; align-items: center; justify-content: space-between; color: white; border: 0; border-radius: 11px; background: linear-gradient(135deg, #ed6b61, #dc514f); box-shadow: 0 12px 28px rgb(220 81 79 / 23%); cursor: pointer; font-weight: 780; }
.primary-action b { font-size: 1.15rem; }.primary-action:hover { filter: brightness(1.04); transform: translateY(-1px); }
.form-note { color: #939aa7; font-size: .67rem; line-height: 1.5; }
.idea-card { padding: 28px; color: #eff3fb; border-color: #24324a; background: radial-gradient(circle at 95% 0, #2d4364, transparent 45%), #17243a; box-shadow: 0 22px 55px rgb(20 32 52 / 18%); }
.idea-card .eyebrow { color: #ff8476; }.idea-card h2 { margin: 0; font-size: 1.65rem; line-height: 1.15; letter-spacing: -.035em; }
.loop-diagram { margin: 23px 0; display: grid; grid-template-columns: auto 1fr auto; gap: 8px; align-items: center; }
.loop-diagram > span { color: #aab7ca; font: 750 9px/1 ui-monospace, monospace; text-transform: uppercase; }
.loop-diagram > div { padding: 13px; border: 1px solid #43526a; border-radius: 11px; background: rgb(255 255 255 / 7%); }
.loop-diagram b, .loop-diagram small { display: block; }.loop-diagram b { color: #ff9287; font-size: .78rem; }.loop-diagram small { margin-top: 6px; color: #aab6c8; font-size: .61rem; }
.idea-copy { margin: 0; color: #adb8ca; font-size: .76rem; line-height: 1.55; }.idea-copy strong { color: white; }
.summary-card { padding: 22px 24px; }.summary-card h3 { margin: 19px 0 14px; font-size: 1.02rem; }.summary-card p { margin: 0 0 14px; color: #727b89; }.summary-card code { font-size: .66rem; }
.summary-stats { margin: 18px 0 12px; display: grid; grid-template-columns: repeat(3, 1fr); gap: 9px; }.summary-stats div { padding: 10px; border-radius: 9px; background: #f5f7f9; }.summary-stats strong, .summary-stats span { display: block; }.summary-stats strong { font-size: 1.1rem; }.summary-stats span { margin-top: 3px; color: #8b94a2; font-size: .56rem; }
.text-action { padding: 8px 0 0; color: #d95450; border: 0; background: transparent; cursor: pointer; font-weight: 750; font-size: .72rem; }.text-action span { margin-left: 5px; }
.success-pill { color: #217f5b !important; background: #e7f8f0 !important; }
.compact-heading { min-height: 170px; align-items: flex-end; }.compact-heading h1 { font-size: clamp(2.4rem, 4vw, 4.2rem); }.compact-heading > div > p:last-child { max-width: 780px; margin-top: 15px; }
.secondary-action { flex: 0 0 auto; padding: 11px 15px; color: #263249; border: 1px solid #d2d8e1; border-radius: 10px; background: white; cursor: pointer; font-size: .72rem; font-weight: 750; box-shadow: 0 8px 22px rgb(37 48 69 / 6%); }
.flow-layout { display: grid; grid-template-columns: minmax(0, 1fr) 300px; gap: 18px; }
.flow-board, .boundary-panel { overflow: hidden; border: 1px solid #dde2e8; border-radius: 18px; background: white; box-shadow: 0 15px 45px rgb(30 42 64 / 7%); }
.flow-board-head { padding: 22px 24px; display: flex; align-items: center; justify-content: space-between; gap: 20px; border-bottom: 1px solid #e5e8ed; }.flow-board-head span { color: #e45c57; font-size: .6rem; font-weight: 850; letter-spacing: .12em; }.flow-board-head h2 { margin: 5px 0 0; font-size: 1rem; }
.screen-flows .profiles { border-color: #e2e5ea; }.screen-flows .profile { color: #7a8494; }.screen-flows .profile b { background: #eef1f4; }.screen-flows .profile.is-active { color: #283348; border-color: #f1a19a; background: #fff4f2; }.screen-flows .profile.is-active b { color: white; background: #e45c57; }
.design-canvas { min-height: 470px; padding: 48px 30px; display: flex; position: relative; align-items: center; overflow: auto; background: #f8f9fb; }.design-canvas .canvas-grid { opacity: .4; background-image: radial-gradient(#c9cfd9 1px, transparent 1px); mask-image: none; }
.design-track { min-width: max-content; margin: auto; display: flex; align-items: center; position: relative; z-index: 1; }
.design-node { width: 180px; min-height: 132px; padding: 17px; display: grid; grid-template-columns: 28px 1fr; gap: 10px; border: 1px solid #d5dae2; border-top: 3px solid #e45c57; border-radius: 13px; background: white; box-shadow: 0 13px 30px rgb(39 50 70 / 10%); }.design-node > span { width: 26px; height: 26px; display: grid; place-items: center; color: #7f8897; border-radius: 7px; background: #f0f2f5; font: 750 9px/1 ui-monospace, monospace; }.design-node div { min-width: 0; }.design-node small, .design-node strong, .design-node code { display: block; }.design-node small { color: #e45c57; font-size: .55rem; font-weight: 850; letter-spacing: .1em; text-transform: uppercase; }.design-node strong { min-height: 40px; margin-top: 7px; color: #252f41; font-size: .78rem; line-height: 1.28; }.design-node code { margin-top: 9px; overflow: hidden; color: #8992a0; font-size: .54rem; text-overflow: ellipsis; white-space: nowrap; }
.design-handoff { width: 46px; position: relative; }.design-handoff i { display: block; height: 1px; background: #abb3bf; }.design-handoff i::after { content: ""; width: 6px; height: 6px; position: absolute; right: 1px; top: -3px; border-top: 1px solid #e45c57; border-right: 1px solid #e45c57; transform: rotate(45deg); }
.flow-footer { padding: 12px 20px; display: flex; justify-content: space-between; color: #858e9b; border-top: 1px solid #e5e8ed; font-size: .62rem; }.flow-footer span { display: flex; align-items: center; gap: 7px; }.flow-footer i { width: 6px; height: 6px; border-radius: 50%; background: #39b883; }
.boundary-panel { padding: 25px; }.boundary-panel .eyebrow { color: #e45c57; }.boundary-panel h2 { margin: 0; color: #202b3d; font-size: 1.5rem; line-height: 1.16; letter-spacing: -.04em; }
.granularity-list { margin: 24px 0; display: grid; gap: 8px; }.granularity-list article { padding: 13px; border: 1px solid #e4e7ec; border-radius: 10px; }.granularity-list article.is-current { border-color: #f0aba5; background: #fff5f3; }.granularity-list b, .granularity-list span { display: block; }.granularity-list b { color: #303a4c; font-size: .72rem; }.granularity-list span { margin-top: 5px; color: #858e9c; font-size: .65rem; line-height: 1.45; }.boundary-note { padding-top: 17px; color: #697383; border-top: 1px solid #e4e7ec; font-size: .69rem; line-height: 1.55; }
.screen-runs .metric-row { background: white; border-color: #dde2e8; }.screen-runs .metric-row div { border-color: #e5e8ed; }.screen-runs .metric-row span { color: #88919e; }.screen-runs .metric-row strong { color: #283347; }.screen-runs .metric-row .success { color: #24835e; }
.screen-runs .app-shell { color: var(--ink); }.screen-runs .principle-row div { color: var(--ink); }
.fresh-note { position: fixed; right: 24px; bottom: 24px; z-index: 80; padding: 13px 16px; color: #155f45; border: 1px solid #9dd8c1; border-radius: 11px; background: #e7f8f0; box-shadow: 0 12px 35px rgb(18 60 45 / 17%); font-size: .76rem; }

@media (max-width: 1120px) {
  .product-shell { grid-template-columns: 82px minmax(0, 1fr); }.rail { padding-inline: 10px; }.rail-brand { justify-content: center; padding-inline: 0; }.rail-brand strong, .nav-item strong, .rail-status span { display: none; }.nav-item { justify-content: center; }.nav-item > span { width: auto; }
  .home-grid { grid-template-columns: 1fr 1fr; }.task-card { grid-row: auto; grid-column: 1 / -1; }.flow-layout { grid-template-columns: 1fr; }.boundary-panel { display: grid; grid-template-columns: .8fr 1.2fr; gap: 20px; }.boundary-panel .boundary-note { grid-column: 1 / -1; }
}
@media (max-width: 800px) {
  .workspace-bar { padding-inline: 22px; }.runtime-status { display: none; }.screen { padding: 34px 20px 55px; }.home-heading { min-height: 220px; }.hero-orbit { display: none; }.home-grid { grid-template-columns: 1fr; }.task-card { grid-column: auto; }.page-heading { flex-direction: column; }.compact-heading { min-height: 0; align-items: flex-start; margin-bottom: 28px; }.flow-board-head { align-items: flex-start; flex-direction: column; }.boundary-panel { display: block; }
}
@media (max-width: 560px) {
  .product-shell { grid-template-columns: 64px minmax(0, 1fr); }.rail { padding: 14px 7px; }.rail-brand span { width: 35px; height: 35px; }.nav-item { padding: 11px 8px; }
  .workspace-bar { height: 58px; padding-inline: 15px; }.workspace-bar .crumb { display: none; }.screen { padding: 27px 14px 44px; }.page-heading h1 { font-size: 2.45rem; }.home-heading { min-height: 190px; }.task-card, .idea-card { padding: 22px; }.summary-stats { grid-template-columns: 1fr 1fr 1fr; }
  .screen-runs .metric-row { grid-template-columns: 1fr 1fr; }.screen-runs .metric-row div:nth-child(2n) { border-right: 0; }.screen-runs .metric-row div { border-bottom: 1px solid #e5e8ed; }
  .design-canvas { padding-inline: 20px; }.design-node { width: 160px; }
}
"""


_SCRIPT = r"""
(() => {
  "use strict";
  const data = JSON.parse(document.getElementById("app-data").textContent);
  const query = new URLSearchParams(window.location.search);
  const initialScreen = ["home", "flows", "runs"].includes(query.get("screen")) ? query.get("screen") : "home";
  const state = {
    screen: initialScreen,
    runIndex: 0,
    nodeId: data.flow.nodes[0].node_id,
    cursor: data.runs[0].events.length - 1,
    tab: "overview",
    timer: null,
  };
  const byId = (id) => document.getElementById(id);
  const pretty = (value) => JSON.stringify(value, null, 2);
  const run = () => data.runs[state.runIndex];
  const definition = () => data.flow.nodes.find((node) => node.node_id === state.nodeId);
  const evidence = () => run().nodes.find((node) => node.node_id === state.nodeId);

  function renderScreen() {
    document.querySelectorAll("[data-screen-panel]").forEach((panel) => {
      const active = panel.dataset.screenPanel === state.screen;
      panel.hidden = !active;
      panel.classList.toggle("is-active", active);
    });
    document.querySelectorAll(".nav-item").forEach((button) => {
      button.classList.toggle("is-active", button.dataset.nav === state.screen);
    });
  }

  function navigate(screen) {
    if (!["home", "flows", "runs"].includes(screen)) return;
    state.screen = screen;
    const next = new URL(window.location.href);
    next.searchParams.set("screen", screen);
    next.searchParams.delete("fresh");
    window.history.replaceState({}, "", next);
    renderScreen();
    window.scrollTo({top: 0, behavior: "smooth"});
  }

  function replayStates() {
    const values = Object.fromEntries(data.flow.nodes.map((node) => [node.node_id, "pending"]));
    run().events.slice(0, state.cursor + 1).forEach((event) => {
      if (!event.node_id) return;
      if (event.event_type === "node.ready") values[event.node_id] = "ready";
      else if (event.event_type === "executor.started") values[event.node_id] = "running";
      else if (event.event_type === "result.accepted") values[event.node_id] = "accepted";
      else if (event.event_type === "node.succeeded") values[event.node_id] = "succeeded";
      else if (event.event_type.includes("failed")) values[event.node_id] = "failed";
    });
    return values;
  }

  function stop() {
    if (state.timer) window.clearInterval(state.timer);
    state.timer = null;
    byId("replay-play").textContent = "Replay";
  }

  function setCursor(value) {
    const last = run().events.length - 1;
    state.cursor = Math.max(0, Math.min(Number(value), last));
    render();
  }

  function renderNodes() {
    const statuses = replayStates();
    document.querySelectorAll(".flow-node").forEach((button) => {
      const status = statuses[button.dataset.nodeId];
      button.className = `flow-node is-${status}`;
      button.setAttribute("aria-selected", String(button.dataset.nodeId === state.nodeId));
      button.querySelector("[data-node-state]").textContent = status;
    });
  }

  function renderTimeline() {
    const events = run().events;
    const event = events[state.cursor];
    const range = byId("replay-range");
    range.max = String(events.length - 1);
    range.value = String(state.cursor);
    byId("event-title").textContent = event.event_type;
    byId("event-sequence").textContent = `${event.sequence} / ${events.length}`;
    byId("event-node").textContent = event.node_id || "run";
    byId("event-time").textContent = event.recorded_at;
    byId("metric-events").textContent = String(events.length);
    const strip = byId("event-strip");
    strip.replaceChildren();
    events.forEach((item, index) => {
      const step = document.createElement("button");
      step.type = "button";
      step.className = "event-step" + (index < state.cursor ? " is-past" : "") + (index === state.cursor ? " is-current" : "");
      step.title = `${item.sequence} · ${item.event_type}`;
      step.setAttribute("aria-label", step.title);
      step.addEventListener("click", () => { stop(); setCursor(index); });
      strip.append(step);
    });
  }

  function renderInspector() {
    const node = evidence();
    const def = definition();
    const index = data.flow.nodes.findIndex((item) => item.node_id === state.nodeId);
    const status = replayStates()[state.nodeId];
    byId("inspector-kicker").textContent = `Node ${String(index + 1).padStart(2, "0")} · ${status}`;
    byId("inspector-title").textContent = def.title;
    byId("inspector-evidence").textContent = node.evidence_level;
    byId("inspector-executor").textContent = `${node.executor_id}@${node.executor_version}`;
    byId("inspector-effects").textContent = node.effects_json.join(" · ");
    byId("inspector-handoff").textContent = def.input_from || "Flow input";
    byId("inspector-status").textContent = status;
    byId("panel-input").textContent = pretty(node.input_json);
    byId("panel-result").textContent = pretty(node.output_json);
    byId("panel-events").textContent = pretty(run().events.filter((event) => event.node_id === state.nodeId));

    const artifact = run().artifacts.find((item) => item.node_id === state.nodeId);
    const artifactEvent = run().events.findIndex((item) => item.node_id === state.nodeId && item.event_type === "artifact.created");
    const visible = artifact && artifactEvent >= 0 && artifactEvent <= state.cursor;
    byId("artifact-block").hidden = !visible;
    if (visible) {
      byId("artifact-link").textContent = artifact.name;
      byId("artifact-link").href = artifact.href;
      byId("artifact-hash").textContent = artifact.sha256;
    }
  }

  function renderTabs() {
    document.querySelectorAll(".tab").forEach((tab) => {
      const active = tab.dataset.tab === state.tab;
      tab.classList.toggle("is-active", active);
      tab.setAttribute("aria-selected", String(active));
    });
    document.querySelectorAll("[data-panel]").forEach((panel) => {
      panel.hidden = panel.dataset.panel !== state.tab;
    });
  }

  function renderRuns() {
    document.querySelectorAll(".run-button").forEach((button) => {
      button.classList.toggle("is-active", Number(button.dataset.runIndex) === state.runIndex);
    });
  }

  function render() {
    renderNodes();
    renderTimeline();
    renderInspector();
    renderTabs();
    renderRuns();
  }

  document.querySelectorAll(".flow-node").forEach((button) => {
    button.addEventListener("click", () => { state.nodeId = button.dataset.nodeId; render(); });
  });
  document.querySelectorAll("[data-nav]").forEach((button) => {
    button.addEventListener("click", () => navigate(button.dataset.nav));
  });
  document.querySelectorAll("[data-run-form]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (window.location.protocol !== "file:") return;
      event.preventDefault();
      window.alert("Launch `make app` to create a new Run from the App. This file view remains read-only.");
    });
  });
  document.querySelectorAll(".run-button").forEach((button) => {
    button.addEventListener("click", () => {
      stop();
      state.runIndex = Number(button.dataset.runIndex);
      state.cursor = run().events.length - 1;
      render();
    });
  });
  document.querySelectorAll(".tab").forEach((button) => {
    button.addEventListener("click", () => { state.tab = button.dataset.tab; renderTabs(); });
  });
  byId("replay-range").addEventListener("input", (event) => { stop(); setCursor(event.target.value); });
  byId("replay-prev").addEventListener("click", () => { stop(); setCursor(state.cursor - 1); });
  byId("replay-next").addEventListener("click", () => { stop(); setCursor(state.cursor + 1); });
  byId("replay-play").addEventListener("click", () => {
    if (state.timer) { stop(); return; }
    if (state.cursor >= run().events.length - 1) state.cursor = 0;
    byId("replay-play").textContent = "Pause";
    render();
    state.timer = window.setInterval(() => {
      if (state.cursor >= run().events.length - 1) { stop(); return; }
      state.cursor += 1;
      render();
    }, 520);
  });
  renderScreen();
  render();
  if (query.get("fresh") === "1") {
    const note = document.createElement("div");
    note.className = "fresh-note";
    note.textContent = "New Run completed · durable evidence is ready";
    document.body.append(note);
    window.setTimeout(() => note.remove(), 4200);
  }
})();
"""

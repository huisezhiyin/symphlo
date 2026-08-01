import {Handle, Position} from "@xyflow/react";

const labels = {
  agent: "Agent",
  tool: "Tool",
  capability: "Capability",
  evaluation: "Evaluation",
  sleep: "Sleep",
  if: "If",
  for: "For",
  llm: "LLM",
  normal: "普通",
  end: "结束",
};

export function AgentNode(props) {
  return <BaseNode {...props} kind="agent" badge="observable Agent Node" />;
}

export function CapabilityNode(props) {
  return <BaseNode {...props} kind="capability" badge="bound local capability" />;
}

export function ToolNode(props) {
  return <BaseNode {...props} kind="tool" badge="one explicit tool operation" />;
}

export function EvaluationNode(props) {
  return <BaseNode {...props} kind="evaluation" badge="pass/fail control evidence" />;
}

export function SleepNode(props) {
  return <BaseNode {...props} kind="sleep" badge="backend time.sleep" />;
}

export function IfNode({data, selected}) {
  const step = data.step || {};
  return (
    <div className={nodeClass("if", data.status, selected)}>
      <Handle type="target" position={Position.Left} />
      <div className="xy-node-head">
        <strong>If</strong>
        {data.status ? <span>{data.status}</span> : null}
      </div>
      <div className="xy-node-body">
        <p>{summaryForStep(step, data.planStep)}</p>
      </div>
      <Handle id="true" type="source" position={Position.Right} className="handle-true" style={{top: "38%"}} />
      <Handle id="false" type="source" position={Position.Right} className="handle-false" style={{top: "68%"}} />
      <div className="branch-tags">
        <span>true</span>
        <span>false</span>
      </div>
    </div>
  );
}

export function LlmNode(props) {
  return <BaseNode {...props} kind="llm" badge="backend LLM" />;
}

export function NormalNode(props) {
  return <BaseNode {...props} kind="normal" badge="backend executor" />;
}

export function EndNode(props) {
  return <BaseNode {...props} kind="end" badge="artifact" />;
}

function BaseNode({data, selected, kind, badge}) {
  const step = data.step || {};
  return (
    <div className={nodeClass(kind, data.status, selected)}>
      <Handle type="target" position={Position.Left} />
      <div className="xy-node-head">
        <strong>{labels[kind] || labels.normal}</strong>
        {data.status ? <span>{data.status}</span> : null}
      </div>
      <div className="xy-node-body">
        <p>{summaryForStep(step, data.planStep)}</p>
        {kind === "agent" && data.sessionGroup ? <small>session: {data.sessionGroup}</small> : null}
        {badge ? <em>{badge}</em> : null}
      </div>
      <Handle type="source" position={Position.Right} />
    </div>
  );
}

function summaryForStep(step, planStep = {}) {
  if (step.type === "time.sleep") {
    const seconds = step.params?.seconds ?? "-";
    return `${seconds}s · ${step.params?.reason || "等待"}`;
  }
  if (step.type === "flow.if") return step.params?.question || step.params?.condition || "判断上游结果";
  return step.prompt || planStep.prompt || planStep.title || step.id || "未命名节点";
}

function nodeClass(kind, status, selected) {
  return [
    "xy-flow-node",
    `kind-${kind}`,
    status ? `status-${status}` : "",
    selected ? "selected" : "",
  ].filter(Boolean).join(" ");
}

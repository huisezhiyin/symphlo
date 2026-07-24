const branchCondition = {
  true: "true",
  false: "false",
};

const nodeTypeByStepType = {
  "agent.task": "agent",
  "capability.task": "capability",
  "artifact.task": "end",
  "time.sleep": "sleep",
  "flow.if": "if",
  "llm.report": "llm",
  "artifact.save": "end",
};

export function flowDslToReactFlow(flow, plan = null, run = null) {
  const steps = Array.isArray(flow?.steps) ? flow.steps : [];
  const planByStep = new Map((plan?.steps || []).map((step) => [step.step_id, step]));
  const statusByStep = new Map((run?.steps || []).map((step) => [step.step_id, step.status]));
  const fallbackPositions = fallbackLayout(steps);
  const nodes = steps.map((step, index) => {
    const planStep = planByStep.get(step.id) || {};
    const position = step.ui?.position || fallbackPositions.get(step.id) || {x: 80 + index * 230, y: 120};
    return {
      id: step.id,
      type: nodeTypeByStepType[step.type] || "normal",
      position,
      data: {
        step,
        planStep,
        status: statusByStep.get(step.id) || "",
        selected: false,
        sessionGroup: sessionGroupForStep(flow, step),
      },
    };
  });
  const edges = [];
  steps.forEach((step, stepIndex) => {
    dependenciesForStep(step).forEach((dependencyId, dependencyIndex) => {
      const sourceHandle = sourceHandleForStep(step, dependencyId);
      edges.push({
        id: `edge_${dependencyId}_${step.id}_${stepIndex}_${dependencyIndex}`,
        source: dependencyId,
        target: step.id,
        sourceHandle,
        data: {condition: step.when || "", branch: sourceHandle || ""},
        label: sourceHandle || undefined,
        type: "deletable",
      });
    });
  });
  return {nodes, edges};
}

export function reactFlowToFlowDsl(nodes, edges, previousFlow) {
  const nextFlow = structuredClone(previousFlow || {});
  const nodeIds = new Set(nodes.map((node) => node.id));
  const steps = Array.isArray(nextFlow.steps) ? nextFlow.steps.filter((step) => nodeIds.has(step.id)) : [];
  const nodeById = new Map(nodes.map((node) => [node.id, node]));
  const incomingByTarget = new Map();
  edges.forEach((edge) => {
    if (!nodeIds.has(edge.source) || !nodeIds.has(edge.target)) return;
    if (!edge.source || !edge.target) return;
    if (!incomingByTarget.has(edge.target)) incomingByTarget.set(edge.target, []);
    incomingByTarget.get(edge.target).push(edge);
  });

  nextFlow.steps = steps.map((step) => {
    const nextStep = structuredClone(step);
    const node = nodeById.get(step.id);
    if (node?.position) {
      nextStep.ui = {
        ...(nextStep.ui || {}),
        position: {
          x: Math.round(node.position.x),
          y: Math.round(node.position.y),
        },
      };
    }
    const incoming = incomingByTarget.get(step.id) || [];
    if (incoming.length) {
      nextStep.from = incoming.length === 1 ? incoming[0].source : incoming.map((edge) => edge.source);
      const conditionalEdge = incoming.find((edge) => branchCondition[edge.sourceHandle]);
      if (conditionalEdge) {
        nextStep.when = `steps.${conditionalEdge.source}.output.condition_met == ${branchCondition[conditionalEdge.sourceHandle]}`;
      } else {
        delete nextStep.when;
      }
    } else {
      delete nextStep.from;
      delete nextStep.when;
    }
    delete nextStep.depends_on;
    return nextStep;
  });
  if (nextFlow.execution?.session_policy?.groups) {
    nextFlow.execution.session_policy.groups = nextFlow.execution.session_policy.groups
      .map((group) => ({...group, steps: (group.steps || []).filter((stepId) => nodeIds.has(stepId))}))
      .filter((group) => group.steps.length);
  }
  return nextFlow;
}

export function defaultPositionForNewNode(nodes) {
  if (!nodes.length) return {x: 120, y: 120};
  const maxX = Math.max(...nodes.map((node) => node.position?.x || 0));
  const yValues = nodes.map((node) => node.position?.y || 120);
  const avgY = yValues.reduce((sum, y) => sum + y, 0) / yValues.length;
  return {x: maxX + 260, y: Math.max(80, Math.round(avgY))};
}

export function dependenciesForStep(step) {
  const value = step?.from ?? step?.depends_on;
  if (!value) return [];
  return Array.isArray(value) ? value : [value];
}

export function sourceHandleForStep(step, dependencyId) {
  const when = String(step?.when || "");
  if (!when.includes(".output.condition_met") || !when.includes(`steps.${dependencyId}.`)) return null;
  if (when.includes("== true") || when.includes("!= false")) return "true";
  if (when.includes("== false") || when.includes("!= true")) return "false";
  return null;
}

function fallbackLayout(steps) {
  const byId = new Map(steps.map((step) => [step.id, step]));
  const depthById = new Map();
  const laneById = new Map();
  const depthFor = (step) => {
    if (depthById.has(step.id)) return depthById.get(step.id);
    const dependencies = dependenciesForStep(step).map((id) => byId.get(id)).filter(Boolean);
    const depth = dependencies.length ? Math.max(...dependencies.map(depthFor)) + 1 : 0;
    depthById.set(step.id, depth);
    return depth;
  };
  steps.forEach((step, index) => {
    depthFor(step);
    const branch = branchFromWhen(step);
    laneById.set(step.id, branch === "true" ? -1 : branch === "false" ? 1 : 0);
    if (!branch && index > 0) laneById.set(step.id, 0);
  });
  const positions = new Map();
  steps.forEach((step, index) => {
    const depth = depthById.get(step.id) || 0;
    const lane = laneById.get(step.id) || 0;
    positions.set(step.id, {
      x: 100 + depth * 260,
      y: 120 + lane * 150 + (lane ? 0 : (index % 3) * 22),
    });
  });
  return positions;
}

function branchFromWhen(step) {
  const when = String(step?.when || "");
  if (when.includes("== true") || when.includes("!= false")) return "true";
  if (when.includes("== false") || when.includes("!= true")) return "false";
  return "";
}

function sessionGroupForStep(flow, step) {
  if (step.session_group) return String(step.session_group);
  const groups = flow?.execution?.session_policy?.groups || [];
  const group = groups.find((item) => Array.isArray(item.steps) && item.steps.includes(step.id));
  return group?.id || "";
}

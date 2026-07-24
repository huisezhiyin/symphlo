import {useCallback, useEffect, useMemo, useRef, useState} from "react";
import {
  addEdge,
  applyEdgeChanges,
  applyNodeChanges,
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
} from "@xyflow/react";
import {
  defaultPositionForNewNode,
  flowDslToReactFlow,
  reactFlowToFlowDsl,
} from "./adapters.js";
import {
  EndNode,
  IfNode,
  LlmNode,
  NormalNode,
  SleepNode,
  AgentNode,
  CapabilityNode,
} from "./nodeTypes/FlowNodes.jsx";
import {DeletableEdge} from "./edgeTypes/DeletableEdge.jsx";

const nodeTypes = {
  agent: AgentNode,
  capability: CapabilityNode,
  sleep: SleepNode,
  if: IfNode,
  llm: LlmNode,
  normal: NormalNode,
  end: EndNode,
};

const edgeTypes = {
  deletable: DeletableEdge,
};

const palette = [
  {kind: "agent", label: "Agent"},
  {kind: "capability", label: "Capability"},
  {kind: "end", label: "结束"},
];

export function FlowCanvasRoot() {
  return (
    <ReactFlowProvider>
      <FlowCanvasApp />
    </ReactFlowProvider>
  );
}

function FlowCanvasApp() {
  const bridge = () => window.flowCanvasBridge;
  const [nodes, setNodes] = useState([]);
  const [edges, setEdges] = useState([]);
  const [flowId, setFlowId] = useState("");
  const nodesRef = useRef(nodes);
  const edgesRef = useRef(edges);
  const flowRef = useRef(null);

  useEffect(() => { nodesRef.current = nodes; }, [nodes]);
  useEffect(() => { edgesRef.current = edges; }, [edges]);

  const commitGraph = useCallback((nextNodes, nextEdges, reason) => {
    const currentFlow = bridge()?.getFlow?.();
    if (!currentFlow) return;
    const nextFlow = reactFlowToFlowDsl(nextNodes, nextEdges, currentFlow);
    flowRef.current = nextFlow;
    bridge()?.setFlow?.(nextFlow, reason);
  }, []);

  const deleteEdge = useCallback((edgeId) => {
    setEdges((currentEdges) => {
      const nextEdges = currentEdges.filter((edge) => edge.id !== edgeId);
      commitGraph(nodesRef.current, nextEdges, "edge-delete");
      return nextEdges;
    });
  }, [commitGraph]);

  const loadFromBridge = useCallback(() => {
    const flow = bridge()?.getFlow?.();
    flowRef.current = flow || null;
    setFlowId(flow?.id || "");
    const graph = flowDslToReactFlow(flow, bridge()?.getPlan?.(), bridge()?.getRun?.());
    setNodes(graph.nodes);
    setEdges(graph.edges);
  }, []);

  useEffect(() => {
    loadFromBridge();
    window.addEventListener("flow-console:flow-updated", loadFromBridge);
    window.addEventListener("flow-console:run-updated", loadFromBridge);
    const onDeleteEdge = (event) => {
      if (event.detail?.edgeId) deleteEdge(event.detail.edgeId);
    };
    window.addEventListener("flow-canvas:delete-edge", onDeleteEdge);
    return () => {
      window.removeEventListener("flow-console:flow-updated", loadFromBridge);
      window.removeEventListener("flow-console:run-updated", loadFromBridge);
      window.removeEventListener("flow-canvas:delete-edge", onDeleteEdge);
    };
  }, [deleteEdge, loadFromBridge]);

  const onNodesChange = useCallback((changes) => {
    setNodes((currentNodes) => {
      const nextNodes = applyNodeChanges(changes, currentNodes);
      const removedNodeIds = new Set(changes.filter((change) => change.type === "remove").map((change) => change.id));
      const didRemove = removedNodeIds.size > 0;
      const shouldCommitPosition = changes.some((change) => change.type === "position" && change.dragging === false);
      if (didRemove) {
        const nextEdges = edgesRef.current.filter((edge) => !removedNodeIds.has(edge.source) && !removedNodeIds.has(edge.target));
        setEdges(nextEdges);
        commitGraph(nextNodes, nextEdges, "node-delete");
      } else if (shouldCommitPosition) {
        commitGraph(nextNodes, edgesRef.current, "node-position");
      }
      return nextNodes;
    });
  }, [commitGraph]);

  const onEdgesChange = useCallback((changes) => {
    setEdges((currentEdges) => {
      const nextEdges = applyEdgeChanges(changes, currentEdges);
      if (changes.some((change) => change.type === "remove")) {
        commitGraph(nodesRef.current, nextEdges, "edge-delete");
      }
      return nextEdges;
    });
  }, [commitGraph]);

  const onConnect = useCallback((connection) => {
    setEdges((currentEdges) => {
      const nextEdges = addEdge({
        ...connection,
        id: `edge_${connection.source}_${connection.target}_${Date.now()}`,
        type: "deletable",
        label: connection.sourceHandle || undefined,
        data: {branch: connection.sourceHandle || ""},
      }, currentEdges);
      commitGraph(nodesRef.current, nextEdges, "edge-create");
      return nextEdges;
    });
  }, [commitGraph]);

  const onEdgeDoubleClick = useCallback((event, edge) => {
    event.preventDefault();
    setEdges((currentEdges) => {
      const nextEdges = currentEdges.filter((item) => item.id !== edge.id);
      commitGraph(nodesRef.current, nextEdges, "edge-delete");
      return nextEdges;
    });
  }, [commitGraph]);

  const selectNode = useCallback((event, node) => {
    bridge()?.selectStep?.(node.id);
  }, []);

  const addNodeFromPalette = useCallback(async (kind) => {
    if (kind === "poll_reply") {
      await bridge()?.addNode?.(kind);
      loadFromBridge();
      return;
    }
    const currentFlow = bridge()?.getFlow?.();
    if (!currentFlow) return;
    const dependency = nodesRef.current.length ? nodesRef.current[nodesRef.current.length - 1].id : undefined;
    const step = bridge()?.createStep?.(kind, dependency);
    if (!step) return;
    const position = defaultPositionForNewNode(nodesRef.current);
    step.ui = {...(step.ui || {}), position};
    const nextFlow = {
      ...currentFlow,
      steps: [...(currentFlow.steps || []), step],
    };
    await bridge()?.setFlow?.(nextFlow, "palette-add");
    bridge()?.selectStep?.(step.id);
    loadFromBridge();
  }, [loadFromBridge]);

  const empty = !nodes.length;
  const minimapNodeColor = useCallback((node) => {
    if (node.type === "agent") return "#2563eb";
    if (node.type === "capability") return "#7c3aed";
    if (node.type === "if") return "#b54708";
    if (node.type === "sleep") return "#667085";
    return "#98a2b3";
  }, []);

  const toolbar = useMemo(() => (
    <div className="xy-palette" aria-label="Node palette">
      {palette.map((item) => (
        <button key={item.kind} type="button" onClick={() => addNodeFromPalette(item.kind)}>
          {item.label}
        </button>
      ))}
    </div>
  ), [addNodeFromPalette]);

  if (!flowId) {
    return (
      <div className="xy-canvas-shell empty">
        <div className="xy-empty">等待 Flow</div>
      </div>
    );
  }

  return (
    <div className="xy-canvas-shell">
      {toolbar}
      {empty ? <div className="xy-empty">添加第一个节点开始搭建。</div> : null}
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onEdgeDoubleClick={onEdgeDoubleClick}
        onNodeClick={selectNode}
        fitView
        fitViewOptions={{padding: 0.18}}
        minZoom={0.25}
        defaultEdgeOptions={{type: "deletable"}}
      >
        <Background color="#d9e1ea" gap={28} />
        <Controls />
        <MiniMap nodeColor={minimapNodeColor} pannable zoomable />
      </ReactFlow>
    </div>
  );
}

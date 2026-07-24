import {BaseEdge, EdgeLabelRenderer, getSmoothStepPath} from "@xyflow/react";

export function DeletableEdge({id, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, markerEnd, label}) {
  const [edgePath, labelX, labelY] = getSmoothStepPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });
  return (
    <>
      <BaseEdge id={id} path={edgePath} markerEnd={markerEnd} />
      <EdgeLabelRenderer>
        <button
          type="button"
          className="xy-edge-delete"
          aria-label="删除连线"
          title={label ? `删除 ${label} 连线` : "删除连线"}
          style={{transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`}}
          onClick={(event) => {
            event.preventDefault();
            event.stopPropagation();
            window.dispatchEvent(new CustomEvent("flow-canvas:delete-edge", {detail: {edgeId: id}}));
          }}
        >
          x
        </button>
      </EdgeLabelRenderer>
    </>
  );
}

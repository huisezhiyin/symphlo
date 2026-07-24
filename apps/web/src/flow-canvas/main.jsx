import React from "react";
import {createRoot} from "react-dom/client";
import "@xyflow/react/dist/style.css";
import "./styles.css";
import {FlowCanvasRoot} from "./FlowCanvasApp.jsx";

const mount = document.getElementById("canvas-content");

if (mount) {
  createRoot(mount).render(<FlowCanvasRoot />);
}

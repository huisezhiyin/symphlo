import {defineConfig} from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  publicDir: "public",
  build: {
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: {
      input: "src/flow-canvas/main.jsx",
      output: {
        entryFileNames: "flow-console/assets/flow-canvas.js",
        assetFileNames: "flow-console/assets/flow-canvas.css",
        chunkFileNames: "flow-console/assets/flow-canvas-[hash].js",
      },
    },
  },
});

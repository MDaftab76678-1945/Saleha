import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

// Aliases mirror the "paths" entries in tsconfig.json: the @saleha/* workspace
// packages are consumed straight from their TypeScript sources rather than a
// built dist/, so Vite has to resolve them the same way the type-checker does.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@saleha/core": fileURLToPath(new URL("../../packages/core/src/index.ts", import.meta.url)),
      "@saleha/ui": fileURLToPath(new URL("../../packages/ui/src/index.ts", import.meta.url)),
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    strictPort: true,
  },
});

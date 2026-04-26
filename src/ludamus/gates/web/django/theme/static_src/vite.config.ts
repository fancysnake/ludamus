import { resolve } from "node:path";

import { defineConfig } from "vite";

export default defineConfig({
  base: "/static/vite/",
  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    cors: {
      origin: /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/,
    },
  },
  build: {
    outDir: resolve(__dirname, "../../../../../static/vite"),
    emptyOutDir: true,
    manifest: "manifest.json",
    rollupOptions: {
      input: resolve(__dirname, "src/index.ts"),
    },
  },
});

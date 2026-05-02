import { resolve } from "node:path";

import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

export default defineConfig({
  base: "/static/vite/",
  plugins: [tailwindcss()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    cors: {
      origin: /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/,
    },
  },
  build: {
    outDir: resolve(__dirname, "../static/vite"),
    emptyOutDir: true,
    manifest: "manifest.json",
    rollupOptions: {
      input: {
        index: resolve(__dirname, "src/index.css"),
        modal: resolve(__dirname, "src/modal.ts"),
        tabs: resolve(__dirname, "src/tabs.ts"),
        timetable: resolve(__dirname, "src/timetable.ts"),
      },
    },
  },
});

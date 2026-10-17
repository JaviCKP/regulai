/// <reference types="vitest/config" />
import { fileURLToPath, URL } from "node:url"

import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

// Django serves the build from regulai/static/chat-app and resolves every entry,
// chunk and stylesheet through manifest.json (not .vite/: the installer bundle
// skips dot-directories). A relative base lets chunks load under any STATIC_URL.
export default defineConfig({
  base: "./",
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  build: {
    outDir: fileURLToPath(new URL("../../regulai/static/chat-app", import.meta.url)),
    emptyOutDir: true,
    manifest: "manifest.json",
    sourcemap: false,
    target: "es2022",
    assetsInlineLimit: 0,
    rollupOptions: {
      input: "src/main.tsx",
    },
  },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
    setupFiles: ["src/test/setup.ts"],
    restoreMocks: true,
  },
})

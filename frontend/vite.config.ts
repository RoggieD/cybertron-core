import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const configDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(configDir, "..");
const certFile = path.join(repoRoot, "certs", "cybertron-core.pem");
const keyFile = path.join(repoRoot, "certs", "cybertron-core-key.pem");

export default defineConfig(({ command }) => ({
  plugins: [react()],

  server: command === "serve" ? {
    host: "0.0.0.0",
    port: 5173,
    https: {
      cert: fs.readFileSync(certFile),
      key: fs.readFileSync(keyFile),
    },

    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },

      "/ws": {
        target: "ws://127.0.0.1:8000",
        ws: true,
      },
    },
  } : undefined,
}));

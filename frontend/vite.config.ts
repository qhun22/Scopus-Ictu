import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    // Public domain is reached through a Cloudflare Tunnel pointed at this
    // dev server; Vite otherwise rejects requests with an unrecognized Host
    // header (DNS-rebinding protection).
    allowedHosts: ["scopus-ictu.xyz"],
    proxy: {
      "/api": {
        // Override with VITE_API_PROXY_TARGET (e.g. the demo backend on 8001); default unchanged.
        target: process.env.VITE_API_PROXY_TARGET ?? "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
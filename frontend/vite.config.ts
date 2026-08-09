import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
      "@contracts": path.resolve(__dirname, "../contracts/api")
    }
  },
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000"
    },
    fs: {
      allow: [path.resolve(__dirname), path.resolve(__dirname, "../contracts")]
    }
  }
});
